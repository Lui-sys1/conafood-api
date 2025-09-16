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

# --- Diccionarios temporales ---
verification_codes = {}
pending_users = {}

# --- Configuración de correo ---
def enviar_correo(destinatario, codigo):
    remitente = 'conafood8@gmail.com'
    password = 'bvpjxtptpzmf upwd'  # ⚠️ Usa variable de entorno en Render
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

# --- Conexión a MySQL ---
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),      # Cambia en Render
        user=os.getenv("DB_USER", "root"),           # Cambia en Render
        password=os.getenv("DB_PASS", ""),           # Cambia en Render
        database=os.getenv("DB_NAME", "conalepfood") # Tu BD
    )

# --- Paso 1: Pre-registro ---
@app.route('/pre_register', methods=['POST'])
def pre_register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    correo = data.get('correo')
    numero = data.get('numero')

    if not username or not password or not correo or not numero:
        return jsonify(error="Todos los campos son obligatorios"), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Verificar si ya existen
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify(error="El usuario ya existe"), 400

        cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return jsonify(error="El correo ya está registrado"), 400

        # Generar código y guardar en memoria
        code = str(random.randint(100000, 999999))
        verification_codes[correo] = code
        pending_users[correo] = {
            "username": username,
            "password": password,
            "numero": numero
        }

        if not enviar_correo(correo, code):
            return jsonify(error="Error al enviar correo"), 500

        return jsonify(message="Código enviado al correo. Verifica tu cuenta.")
    except Exception as e:
        logging.error("Error en pre-registro", exc_info=True)
        return jsonify(error="Error interno en el servidor"), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()

# --- Paso 2: Verificación y creación de usuario ---
@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    correo = data.get('correo')
    code = data.get('codigo')

    if not correo or not code:
        return jsonify(error="Faltan datos"), 400

    if correo not in verification_codes or verification_codes[correo] != code:
        return jsonify(error="Código incorrecto."), 400

    try:
        # Recuperar datos pendientes
        user_data = pending_users.get(correo)
        if not user_data:
            return jsonify(error="No hay registro pendiente para este correo"), 400

        db = get_db_connection()
        cursor = db.cursor()

        # Insertar usuario ya verificado
        cursor.execute(
            "INSERT INTO usuarios (username, password, correo, numero, verificado) VALUES (%s, %s, %s, %s, %s)",
            (user_data['username'], user_data['password'], correo, user_data['numero'], 1)
        )
        db.commit()

        # Limpiar temporales
        verification_codes.pop(correo, None)
        pending_users.pop(correo, None)

        return jsonify(message="Cuenta verificada y creada con éxito!")
    except Exception as e:
        logging.error("Error al verificar cuenta", exc_info=True)
        return jsonify(error="Error en el servidor al verificar"), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()

# --- Login ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify(error="Faltan usuario o contraseña"), 400

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT password FROM usuarios WHERE username = %s", (username,))
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

# --- Ver usuarios (solo para pruebas) ---
@app.route('/usuarios', methods=['GET'])
def get_users():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT username, correo, numero, verificado FROM usuarios")
        rows = cursor.fetchall()

        usuarios = []
        for row in rows:
            usuarios.append({
                "username": row[0],
                "correo": row[1],
                "numero": row[2],
                "verificado": row[3]
            })
        return jsonify(usuarios)
    except Exception as e:
        logging.error("Error al obtener usuarios", exc_info=True)
        return jsonify(error="Error en el servidor"), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()

# --- HTML ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

# --- Ejecutar app ---
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
