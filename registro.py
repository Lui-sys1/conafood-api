import os
import psycopg
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import smtplib
from email.mime.text import MIMEText
import logging

# --- Configuración logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App ---
app = Flask(__name__)
CORS(app)

# --- Configuración DB PostgreSQL ---
DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg.connect(DB_URL, autocommit=True)


# --- Almacenamiento temporal de códigos de verificación ---
verification_codes = {}

# --- Función para enviar correo ---
def send_verification_email(to_email, code):
    try:
        smtp_host = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "conafood8@gmail.com"
        smtp_pass = "bvpjxtptpzmfupwd"
        
        msg = MIMEText(f"Tu código de verificación es: {code}")
        msg['Subject'] = "Código de verificación ConaFood"
        msg['From'] = smtp_user
        msg['To'] = to_email

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logging.info(f"Código enviado a {to_email}")
    except Exception as e:
        logging.error(f"Error enviando correo: {e}")

# --- Ruta para servir index ---
@app.route("/")
def show_index():
    return render_template("index.html")

# --- Ruta para servir menu ---
@app.route("/menu.html")
def show_menu():
    return render_template("menu.html")
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
    verification_codes[username] = {"code": code, "password": password, "correo": correo, "numero": numero}

    # Enviar código por correo
    send_verification_email(correo, code)

    return jsonify({"message": "Código de verificación enviado"}), 200

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

    # Crear usuario en DB con verificado = TRUE
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (username, password, correo, numero, verificado) VALUES (%s, %s, %s, %s, %s)",
                (
                    username,
                    verification_codes[username]["password"],
                    verification_codes[username]["correo"],
                    verification_codes[username]["numero"],
                    True
                )
            )
        # Eliminar de almacenamiento temporal
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
                "SELECT * FROM usuarios WHERE username=%s AND password=%s AND verificado=TRUE",
                (username, password)
            )
            user = cursor.fetchone()

        if user:
            return jsonify({"message": f"Bienvenido {username}"}), 200
        else:
            return jsonify({"error": "Usuario o contraseña incorrecta o no verificado"}), 401
    except Exception as e:
        # 👇 PARA DEPURAR: manda el error real al frontend
        logging.error(f"Error en login: {e}")
        return jsonify({"error": f"Error BD: {str(e)}"}), 500
