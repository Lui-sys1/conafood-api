import smtplib
from email.mime.text import MIMEText
import os

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "conafood8@gmail.com"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  # ya configurada

def enviar_codigo(destinatario, codigo):
    mensaje = MIMEText(f"Tu código de verificación es: {codigo}")
    mensaje["Subject"] = "Código de verificación ConalepFood"
    mensaje["From"] = EMAIL_ADDRESS
    mensaje["To"] = destinatario

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(mensaje)
    print("Correo enviado correctamente a", destinatario)
