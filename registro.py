from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import smtplib
from email.mime.text import MIMEText
import logging
import time
from mysql.connector import pooling, Error

# --- Configuración logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App ---
app = Flask(__name__)
CORS(app)

# --- Diccionario temporal para códigos ---
verification_codes = {}

# --- Configuración de correo ---
EMAIL_ADDRESS = "conafood8@gmail.com"
EMAIL_PASSWORD = "bvpjxtptpzmfupwd"

# --- Configuración pool de conexiones ---
dbconfig = {
    "host": "localhost",
    "user": "Luis.5531",
    "password": "Ab231850026-7",
    "database": "conalepfood"
}

try:
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        **dbconfig
    )
    logging.info("Pool de conexiones creado correctamente")
except Error as e:
    logging.error(f"Error creando pool de conexiones: {e}")
    raise e

def get_db_connection(retries=3, delay=2):
    for attempt in range(retries):
        try:
            conn = connection_pool.get_connection()
            if conn.is_connected():
                return conn
        except Error as e:
            logging.error(f"Error conexión MySQL (intento {attempt+1}): {e}")
            time.sleep(delay)
    raise ConnectionError("No se pudo conectar a la base de datos después de varios intentos.")

def send_email(to_email, code):
    msg = MIMEText(f"Tu código de verificación es: {code}")
    msg['Subject'] = "Código de verificación ConalepFood"
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

        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify(error="El usuario ya existe"), 400

        cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return jsonify(error="El correo ya está registrado"), 400

        cursor.execute(
            "INSERT INTO usuarios (username, password, correo, numero) VALUES (%s, %s, %s, %s)",
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
        try:
            cursor.close()
            db.close()
        except:
            pass

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
            cursor.execute("UPDATE usuarios SET verificado = 1 WHERE username = %s", (username,))
            db.commit()
            verification_codes.pop(username, None)
            return jsonify(message="Cuenta verificada correctamente!")
        except Exception as e:
            logging.error("Error al verificar cuenta", exc_info=True)
            return jsonify(error="Error del servidor al verificar"), 500
        finally:
            try:
                cursor.close()
                db.close()
            except:
                pass

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
        try:
            cursor.close()
            db.close()
        except:
            pass

# --- Ejecutar la app ---
if __name__ == '__main__':
    app.run(debug=True)
