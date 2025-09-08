from flask import Flask, request, jsonify
from random import randint
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "conafood8@gmail.com"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

codigos_temporales = {}  # guarda códigos por usuario temporalmente

def enviar_codigo(destinatario, codigo):
    mensaje = MIMEText(f"Tu código de verificación es: {codigo}")
    mensaje["Subject"] = "Código de verificación ConalepFood"
    mensaje["From"] = EMAIL_ADDRESS
    mensaje["To"] = destinatario
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(mensaje)
        print(f"Código enviado a {destinatario} ✅")
    except Exception as e:
        print("Error al enviar correo:", e)

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    usuario = data.get("username")
    correo = data.get("correo")
    codigo = str(randint(100000, 999999))
    codigos_temporales[usuario] = codigo
    enviar_codigo(correo, codigo)
    return jsonify({"message": "Código enviado"}), 200

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json()
    usuario = data.get("username")
    codigo = data.get("codigo")
    if codigos_temporales.get(usuario) == codigo:
        del codigos_temporales[usuario]  # se borra el código usado
        return jsonify({"message": "Cuenta verificada"}), 200
    return jsonify({"error": "Código incorrecto"}), 400

if __name__ == "__main__":
    app.run(debug=True)
