import os
import psycopg
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import smtplib
from email.mime.text import MIMEText
import logging

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)

# --- DATABASE ---
DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if not DB_URL:
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
        logging.info("Tabla usuarios lista")
    except Exception as e:
        logging.error(f"Error creando tabla: {e}")

ensure_tables()

# --- CÓDIGOS DE VERIFICACIÓN TEMPORALES ---
verification_codes = {}

# --------------------------------------------------------
# ✅ FUNCIÓN PARA ENVIAR CORREO USANDO **BREVO SMTP**
# --------------------------------------------------------
def send_verification_email(to_email, code):
    try:
        smtp_host = "smtp-relay.brevo.com"
        smtp_port = 587
        smtp_user = "9c5a73001@smtp-brevo.com"
        smtp_pass = "LTVBUX301nvdctNF"     # TU PASSWORD SMTP

        msg = MIMEText(f"Tu código de verificación es: {code}")
        msg["Subject"] = "Código de verificación ConaFood"
        msg["From"] = smtp_user
        msg["To"] = to_email

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()

        logging.info(f"Correo enviado a {to_email}")
        return True

    except Exception as e:
        logging.error(f"Error SMTP: {e}")
        return False


# --- Rutas ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    correo = data.get("correo")
    numero = data.get("numero")

    if not all([username, password, correo, numero]):
        return jsonify({"error": "Faltan datos"}), 400

    code = str(random.randint(100000, 999999))

    verification_codes[username] = {
        "code": code,
        "password": password,
        "correo": correo,
        "numero": numero
    }

    enviado = send_verification_email(correo, code)

    if not enviado:
        return jsonify({"error": "No se pudo enviar el correo."}), 500

    return jsonify({"message": "Código enviado"}), 200


@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    username = data.get("username")
    code = data.get("codigo")

    if username not in verification_codes:
        return jsonify({"error": "Código expirado"}), 404

    if verification_codes[username]["code"] != code:
        return jsonify({"error": "Código incorrecto"}), 400

    try:
        info = verification_codes[username]
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuarios (username, password, correo, numero, verificado)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (username, info["password"], info["correo"], info["numero"]))
        del verification_codes[username]
        return jsonify({"message": "Usuario verificado"}), 200

    except Exception as e:
        logging.error(f"DB error: {e}")
        return jsonify({"error": "Error en la base de datos"}), 500


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
                WHERE username = %s AND password = %s AND verificado = TRUE
            """, (username, password))

            user = cursor.fetchone()

        if user:
            return jsonify({"message": f"Bienvenido {username}"}), 200
        else:
            return jsonify({"error": "Credenciales incorrectas"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
