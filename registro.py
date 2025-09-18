import os
import psycopg
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import smtplib
from email.mime.text import MIMEText
import logging

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App ---
app = Flask(__name__)
CORS(app)

# --- Configuración DB ---
DB_HOST = os.getenv("DB_HOST", "dpg-d34rvonfte5s73adba80-a.oregon-postgres.render.com")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "conafood")
DB_USER = os.getenv("DB_USER", "luis5531")
DB_PASSWORD = os.getenv("DB_PASSWORD", "q16ddEGzzySuQJeWHHx6iG4GO0rht9kG")

def get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True
    )

# --- Almacenamiento temporal de códigos ---
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

# --- Rutas de usuario ---
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
    verification_codes[username] = {"code": code, "password": password, "correo": correo, "numero": numero}
    send_verification_email(correo, code)
    return jsonify({"message": "Código de verificación enviado"}), 200

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
                "INSERT INTO usuarios (username, password, correo, numero, verificado) VALUES (%s, %s, %s, %s, TRUE)",
                (username, verification_codes[username]["password"], verification_codes[username]["correo"], verification_codes[username]["numero"])
            )
        del verification_codes[username]
        return jsonify({"message": "Usuario creado correctamente"}), 200
    except Exception as e:
        logging.error(f"Error creando usuario: {e}")
        return jsonify({"error": "Error creando usuario"}), 500

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
        logging.error(f"Error en login: {e}")
        return jsonify({"error": "Error conectando a la base de datos"}), 500

# --- Rutas de páginas ---
@app.route("/")
def show_index():
    return render_template("index.html")

@app.route("/menu.html")
def show_menu():
    return render_template("menu.html")

@app.route("/panel")
def panel():
    return render_template("panel_cafeteria.html")

# --- API de pedidos ---
@app.route("/pedidos", methods=["GET"])
def obtener_pedidos():
    try:
        conn = get_db_connection()
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute("SELECT * FROM vista_pedidos ORDER BY fecha DESC;")
            pedidos = cursor.fetchall()
        return jsonify(pedidos)
    except Exception as e:
        logging.error(f"Error obteniendo pedidos: {e}")
        return jsonify({"error": "No se pudieron obtener los pedidos"}), 500

@app.route("/pedidos/<int:pedido_id>", methods=["PATCH"])
def actualizar_pedido(pedido_id):
    nuevo_estado = request.json.get("estado")
    if nuevo_estado not in ["pendiente", "en_preparacion", "entregado"]:
        return jsonify({"error": "Estado inválido"}), 400
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE pedidos SET estado=%s WHERE id_pedido=%s", (nuevo_estado, pedido_id))
        return jsonify({"message": "Pedido actualizado"})
    except Exception as e:
        logging.error(f"Error actualizando pedido: {e}")
        return jsonify({"error": "No se pudo actualizar el pedido"}), 500

# --- Ejecutar servidor ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
