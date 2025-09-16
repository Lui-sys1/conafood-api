import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2 import sql
import random
import smtplib
from email.mime.text import MIMEText
import logging

# --- Configuración logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App ---
app = Flask(__name__)
CORS(app)

# --- Conexión a PostgreSQL ---
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "dpg-d34rvonfte5s73adba80-a.oregon-postgres.render.com"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME", "conafood"),
        user=os.getenv("DB_USER", "luis5531"),
        password=os.getenv("DB_PASS", "q16ddEGzzySuQJeWHHx6iG4GO0rht9kG")
    )

# --- Diccionario temporal para códigos de verificación ---
verification_codes = {}

# --- Función para enviar correo ---
def send_verification_email(to_email, code):
    try:
        # Configura tu servidor SMTP aquí
        smtp_server = 'smtp.example.com'
        smtp_port = 587
        smtp_user = 'tu-correo@example.com'
        smtp_pass = 'tu-password'

        msg = MIMEText(f'Tu código de verificación es: {code}')
        msg['Subject'] = 'Código de verificación ConaFood'
        msg['From'] = smtp_user
        msg['To'] = to_email

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_email], msg.as_string())
        server.quit()
        logging.info(f'Correo enviado a {to_email}')
    except Exception as e:
        logging.error(f'Error enviando correo: {e}')

# --- Crear tabla usuarios si no existe ---
def create_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                correo TEXT UNIQUE,
                numero TEXT,
                verificado INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f'Error creando tabla: {e}')

create_tables()

# --- Registro ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    correo = data.get('correo')
    numero = data.get('numero')

    if not all([username, password, correo, numero]):
        return jsonify({'error': 'Faltan datos'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Verificar si usuario o correo ya existen
        cursor.execute("SELECT * FROM usuarios WHERE username = %s OR correo = %s", (username, correo))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Usuario o correo ya existe'}), 400

        # Generar código de verificación
        code = str(random.randint(100000, 999999))
        verification_codes[username] = {'code': code, 'data': {'username': username, 'password': password, 'correo': correo, 'numero': numero}}

        # Enviar correo
        send_verification_email(correo, code)

        cursor.close()
        conn.close()
        return jsonify({'message': 'Código de verificación enviado'}), 200
    except Exception as e:
        logging.error(f'Error en register: {e}')
        return jsonify({'error': 'Error en el servidor'}), 500

# --- Verificación ---
@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    username = data.get('username')
    code = data.get('codigo')

    if username not in verification_codes:
        return jsonify({'error': 'Usuario no encontrado o código expirado'}), 400

    if verification_codes[username]['code'] != code:
        return jsonify({'error': 'Código incorrecto'}), 400

    user_data = verification_codes.pop(username)['data']

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (username, password, correo, numero, verificado)
            VALUES (%s, %s, %s, %s, 1)
        """, (user_data['username'], user_data['password'], user_data['correo'], user_data['numero']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Usuario verificado y creado'}), 200
    except Exception as e:
        logging.error(f'Error en verify: {e}')
        return jsonify({'error': 'Error en el servidor'}), 500

# --- Login ---
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s AND verificado = 1", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return jsonify({'message': f'Bienvenido {username}'}), 200
        else:
            return jsonify({'error': 'Usuario o contraseña incorrectos, o no verificado'}), 400
    except Exception as e:
        logging.error(f'Error en login: {e}')
        return jsonify({'error': 'Error en el servidor'}), 500

# --- Ejecutar app ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
# Nota: Asegúrate de configurar correctamente el servidor SMTP y las variables de entorno para la base de datos.