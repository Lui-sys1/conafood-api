import smtplib
from email.mime.text import MIMEText
import os
import random

# Configuración del servidor SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # TLS
EMAIL_ADDRESS = "conafood8@gmail.com"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  # variable de entorno

def generar_codigo():
    """Genera un código aleatorio de 6 dígitos"""
    return str(random.randint(100000, 999999))

def enviar_codigo(destinatario):
    codigo = generar_codigo()
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
        return codigo  # retorna el código para validación interna
    except Exception as e:
        print("Error al enviar correo:", e)
        return None

# Ejemplo de uso
codigo_generado = enviar_codigo("luis.espejel.hernandez@hotmail.com")
print("Código generado internamente:", codigo_generado)
