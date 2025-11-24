import os
import psycopg
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import smtplib
from email.mime.text import MIMEText
import logging

# --- Configuración logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Flask App ---
app = Flask(__name__)
CORS(app)

# --- Configuración DB PostgreSQL ---
DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if not DB_URL:
        logging.error("DATABASE_URL no está definida")
        raise RuntimeError("DATABASE_URL no está definida")
    return psycopg.connect(DB_URL, autocommit=True)

# Crear tabla si no existe
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
        logging.error(f"Error creando/verificando tabla usuarios: {e}")
ensure_tables()

# --- Almacenamiento temporal de códigos de verificación ---
verification_codes = {}

# --- Función para enviar correo ---
def send_verification_email(to_email, code) -> bool:
    try:
        smtp_host = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "conafood8@gmail.com"
        smtp_pass = "register"  # aquí deberías usar tu contraseña de aplicación de Gmail

        msg = MIMEText(f"Tu código de verificación es: {code}")
        msg["Subject"] = "Código de verificación ConaFood"
        msg["From"] = smtp_user
        msg["To"] = to_email

        # timeout para que no se quede trabado
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logging.info(f"Código enviado a {to_email}")
        return True
    except Exception as e:
        logging.error(f"Error enviando correo: {e}")
        return False


# --- Rutas estáticas ---
@app.route("/")
def show_index():
    return render_template("index.html")

@app.route("/menu.html")
def show_menu():
    return render_template("menu.html")

# --- Ruta para probar DB ---
@app.route("/db-check")
def db_check():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.error(f"DB CHECK ERROR: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# --- Ruta para registrar usuario (solo envía código) ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    correo = data.get("correo")
    numero = data.get("numero")

    if not all([username, password, correo, numero]):
        return jsonify({"error": "Faltan datos"}), 400

    # Generar código aleatorio de 6 dígitos
    code = str(random.randint(100000, 999999))

    verification_codes[username] = {
        "code": code,
        "password": password,
        "correo": correo,
        "numero": numero,
    }

    # Intentar enviar correo, pero NO bloquear si falla
    ok = send_verification_email(correo, code)
    if not ok:
        logging.warning("No se pudo enviar el correo, pero continuamos para pruebas.")

    # IMPORTANTE: devolvemos también el código para que lo veas en el front (solo pruebas)
    return jsonify({
        "message": "Código de verificación generado (revisa tu correo o usa el código mostrado en pruebas).",
        "code": code
    }), 200




# --- Ruta para verificar usuario y crear en DB ---
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
            cursor.execute(
                """
                INSERT INTO usuarios (username, password, correo, numero, verificado)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    username,
                    verification_codes[username]["password"],
                    verification_codes[username]["correo"],
                    verification_codes[username]["numero"],
                    True,
                ),
            )
        del verification_codes[username]
        return jsonify({"message": "Usuario creado correctamente"}), 200
    except Exception as e:
        logging.error(f"Error creando usuario: {e}")
        return jsonify({"error": "Error creando usuario"}), 500

# --- Ruta login ---
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        conn = get_db_connection()
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute(
                """
                SELECT * FROM usuarios
                WHERE username = %s
                  AND password = %s
                  AND verificado = TRUE
                """,
                (username, password),
            )
            user = cursor.fetchone()

        if user:
            return jsonify({"message": f"Bienvenido {username}"}), 200
        else:
            return jsonify({"error": "Usuario o contraseña incorrecta o no verificado"}), 401
    except Exception as e:
        logging.error(f"Error en login: {e}")
        # De momento devolvemos el error real para depurar
        return jsonify({"error": f"Error BD: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
