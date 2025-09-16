from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import random
import smtplib
from email.mime.text import MIMEText
import logging
import os

# --- Configuración logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App ---
app = Flask(__name__)
CORS(app)

# --- Diccionario temporal para códigos ---
verification_codes = {}

# --- Configuración de correo ---
def enviar_correo(destinatario, codigo):
    remitente = os.getenv("EMAIL_USER", "conafood8@gmail.com")
    password = os.getenv("EMAIL_PASS", "bvpjxtptpzmf upwd")
    asunto = 'Código de verificación ConaFood'
    mensaje = f'Tu código de verificación es: {codigo}'

    msg = MIMEText(mensaje)
    msg['Subject'] = asunto
    msg['From'] = remitente
    msg['To'] = destinatario

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(remitente, password)
            server.send_message(msg)
        print("Correo enviado correctamente a", destinatario)
        return True
    except Exception as e:
        print("Error al mandar el correo:", e)
        return False

# --- Función para conexión MySQL ---
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )

# --- Crear tabla si no existe ---
try:
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            password VARCHAR(255),
            correo VARCHAR(100) UNIQUE,
            numero VARCHAR(20),
            verificado TINYINT DEFAULT 0
        )
    """)
    db.commit()
finally:
    if cursor: cursor.close()
    if db: db.close()

# --- Endpoints API ---

# Registro: envía código de verificación primero
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    correo = data.get('correo')
    numero = data.get('numero')

    if not username or not password or not correo or not numero:
        return jsonify(error="Todos los campos son obligatorios"), 400

    # Generar código de verificación antes de crear usuario
    code = str(random.randint(100000, 999999))
    verification_codes[username] = {
        "code": code,
        "username": username,
        "password": password,
        "correo": correo,
        "numero": numero
    }

    if enviar_correo(correo, code):
        return jsonify(message="Código de verificación enviado. Verifica tu correo para completar el registro.")
    else:
        return jsonify(error="Error al enviar correo"), 500

# Verificación y creación del usuario
@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    username = data.get('username')
    code = data.get('codigo')

    if not username or not code:
        return jsonify(error="Faltan datos"), 400

    if username not in verification_codes:
        return jsonify(error="No se encontró un código para este usuario"), 400

    if verification_codes[username]["code"] != code:
        return jsonify(error="Código incorrecto"), 400

    # Crear usuario en la BD
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        user = verification_codes[username]
        cursor.execute("SELECT * FROM usuarios WHERE username = %s OR correo = %s", (user["username"], user["correo"]))
        if cursor.fetchone():
            return jsonify(error="El usuario o correo ya existe"), 400

        cursor.execute(
            "INSERT INTO usuarios (username, password, correo, numero, verificado) VALUES (%s, %s, %s, %s, 1)",
            (user["username"], user["password"], user["correo"], user["numero"])
        )
        db.commit()
        verification_codes.pop(username)
        return jsonify(message="Usuario creado y verificado correctamente!")
    except Exception as e:
        logging.error("Error al crear usuario", exc_info=True)
        return jsonify(error="Error del servidor al crear usuario"), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()

# Login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify(error="Faltan usuario o contraseña"), 400

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT password FROM usuarios WHERE username = %s AND verificado = 1", (username,))
        row = cursor.fetchone()
        if row and row[0] == password:
            return jsonify(message="Login exitoso!")
        else:
            return jsonify(error="Usuario o contraseña incorrectos"), 400
    except Exception as e:
        logging.error("Error en login", exc_info=True)
        return jsonify(error="Error en el servidor"), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()

# Obtener usuarios
@app.route('/usuarios', methods=['GET'])
def get_users():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT username, correo, numero, verificado FROM usuarios")
        rows = cursor.fetchall()
        usuarios = [{"username": r[0], "correo": r[1], "numero": r[2], "verificado": r[3]} for r in rows]
        return jsonify(usuarios)
    except Exception as e:
        logging.error("Error al obtener usuarios", exc_info=True)
        return jsonify(error="Error en el servidor"), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()

# HTML
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

# Ejecutar app
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
