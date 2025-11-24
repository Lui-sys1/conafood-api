import os
import psycopg
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import logging

# Brevo API
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# --------------------------------------------------------
# LOGGING
# --------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --------------------------------------------------------
# FLASK
# --------------------------------------------------------
app = Flask(__name__)
CORS(app)

# --------------------------------------------------------
# BASE DE DATOS (Render)
# --------------------------------------------------------
DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if not DB_URL:
        logging.error("Falta DATABASE_URL en Render")
        raise RuntimeError("DATABASE_URL no está definida")

    return psycopg.connect(DB_URL, autocommit=True)

# Crear tabla automáticamente
def ensure_tables():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    correo VARCHAR(255) NOT NULL,
                    numero VARCHAR(50) NOT NULL,
                    verificado BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        logging.info("Tabla 'usuarios' verificada/creada correctamente.")
    except Exception as e:
        logging.error(f"Error creando/verificando tabla 'usuarios': {e}")

ensure_tables()

# --------------------------------------------------------
# Códigos temporales
# --------------------------------------------------------
verification_codes = {}

# --------------------------------------------------------
# FUNCIÓN PARA ENVIAR CORREO CON BREVO
# --------------------------------------------------------
def send_verification_email(to_email, code):
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        logging.error("BREVO_API_KEY no está definida")
        return False, "BREVO_API_KEY no definida"

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key

    api_client = sib_api_v3_sdk.ApiClient(configuration)
    email_api = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

    email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        sender={"email": "no-reply@conafood.com", "name": "ConaFood"},
        subject="Código de verificación ConaFood",
        html_content=f"<p>Tu código es: <strong>{code}</strong></p>"
    )

    try:
        email_api.send_transac_email(email)
        logging.info(f"Correo enviado a: {to_email}")
        return True, None
    except ApiException as e:
        logging.error(f"Error BREVO API: {e}")
        return False, str(e)

# --------------------------------------------------------
# RUTAS
# --------------------------------------------------------

@app.route("/")
def show_index():
    return render_template("index.html")

@app.route("/menu.html")
def show_menu():
    return render_template("menu.html")


@app.route("/db-check")
def db_check():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --------------------------------------------------------
# REGISTRO
# --------------------------------------------------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    correo = data.get("correo")
    numero = data.get("numero")

    if not all([username, password, correo, numero]):
        return jsonify({"error": "Faltan datos"}), 400

    # Código de 6 dígitos
    code = str(random.randint(100000, 999999))

    verification_codes[username] = {
        "code": code,
        "password": password,
        "correo": correo,
        "numero": numero
    }

    # Enviar correo
    ok, err = send_verification_email(correo, code)
    if not ok:
        return jsonify({
            "error": "No se pudo enviar el correo.",
            "detail": err
        }), 500

    return jsonify({"message": "Código de verificación enviado"}), 200


# --------------------------------------------------------
# VERIFICAR
# --------------------------------------------------------
@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    username = data.get("username")
    code = data.get("codigo")

    if username not in verification_codes:
        return jsonify({"error": "Usuario no encontrado o código expirado"}), 404

    if verification_codes[username]["code"] != code:
        return jsonify({"error": "Código incorrecto"}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuarios (username, password, correo, numero, verificado)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                username,
                verification_codes[username]["password"],
                verification_codes[username]["correo"],
                verification_codes[username]["numero"],
                True
            ))
        del verification_codes[username]
        return jsonify({"message": "Usuario creado correctamente"}), 200

    except Exception as e:
        logging.error(f"Error creando usuario: {e}")
        return jsonify({"error": "Error creando usuario"}), 500


# --------------------------------------------------------
# LOGIN
# --------------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        conn = get_db_connection()
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute("""
                SELECT * FROM usuarios
                WHERE username = %s
                  AND password = %s
                  AND verificado = TRUE
            """, (username, password))

            user = cursor.fetchone()

            if user:
                return jsonify({"message": f"Bienvenido {username}"}), 200
            else:
                return jsonify({"error": "Usuario o contraseña incorrecta o no verificado"}), 401

    except Exception as e:
        logging.error(f"Error en login: {e}")
        return jsonify({"error": "Error BD: " + str(e)}), 500


# --------------------------------------------------------
# INICIO SERVIDOR
# --------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
