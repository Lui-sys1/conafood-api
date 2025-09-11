from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
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

# --- Variables de entorno para correo ---
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "correo@ejemplo.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "clave123")

# --- Función para conexión SQLite ---
def get_db_connection():
    conn = sqlite3.connect("conafood.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- Crear tabla si no existe ---
with get_db_connection() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            correo TEXT UNIQUE,
            numero TEXT,
            verificado INTEGER DEFAULT 0
        )
    """)
    db.commit()

# --- Endpoint raíz ---
@app.route('/index.html')
def menu():
    return render_template('index.html')


# --- Función para enviar correos ---
def send_email(to_email, code):
    msg = MIMEText(f"Tu código de verificación es: {code}")
    msg['Subject'] = "Código de verificación Conafood"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logging.info(f"Correo enviado a {to_email}")
        return True
    except Exception as e:
        logging.error(f"Error enviando correo: {e}")
        return False

# --- Endpoint de registro ---
@app.route('/register', methods=['POST'])
def register():
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

        cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        if cursor.fetchone():
            return jsonify(error="El usuario ya existe"), 400

        cursor.execute("SELECT * FROM usuarios WHERE correo = ?", (correo,))
        if cursor.fetchone():
            return jsonify(error="El correo ya está registrado"), 400

        cursor.execute(
            "INSERT INTO usuarios (username, password, correo, numero) VALUES (?, ?, ?, ?)",
            (username, password, correo, numero)
        )
        db.commit()

        code = str(random.randint(100000, 999999))
        verification_codes[username] = code

        if not send_email(correo, code):
            return jsonify(error="Error al enviar correo"), 500

        return jsonify(message="Registro exitoso! Revisa tu correo para el código.")
    except Exception as e:
        logging.error("Error en registro", exc_info=True)
        return jsonify(error=f"Error interno en el servidor: {str(e)}"), 500
    finally:
        cursor.close()
        db.close()

# --- Endpoint de verificación ---
@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    username = data.get('username')
    code = data.get('codigo')

    if not username or not code:
        return jsonify(error="Faltan datos"), 400

    if username not in verification_codes:
        return jsonify(error="No se encontró un código para este usuario"), 400

    if verification_codes[username] == code:
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("UPDATE usuarios SET verificado = 1 WHERE username = ?", (username,))
            db.commit()
            verification_codes.pop(username, None)
            return jsonify(message="Cuenta verificada correctamente!")
        except Exception as e:
            logging.error("Error al verificar cuenta", exc_info=True)
            return jsonify(error="Error del servidor al verificar"), 500
        finally:
            cursor.close()
            db.close()

    return jsonify(error="Código incorrecto."), 400

# --- Endpoint de login ---
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
        cursor.execute("SELECT password FROM usuarios WHERE username = ?", (username,))
        row = cursor.fetchone()

        if row and row[0] == password:
            return jsonify(message="Login exitoso!")
        else:
            return jsonify(error="Usuario o contraseña incorrectos"), 400
    except Exception as e:
        logging.error("Error en login", exc_info=True)
        return jsonify(error="Error en el servidor"), 500
    finally:
        cursor.close()
        db.close()

# --- Endpoint para ver todos los usuarios ---
@app.route('/usuarios', methods=['GET'])
def get_users():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT username, correo, numero, verificado FROM usuarios")
        rows = cursor.fetchall()
        cursor.close()
        db.close()

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

# --- Ejecutar la app ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
