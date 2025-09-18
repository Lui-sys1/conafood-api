import os
from flask import Flask, send_from_directory, jsonify, request
import psycopg2

# ----------------------------
# Inicializar Flask
# ----------------------------
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

# ----------------------------
# Configuración DB con fallback (Render o local)
# ----------------------------
DB_HOST = os.environ.get("DB_HOST", "dpg-d34rvonfte5s73adba80-a.oregon-postgres.render.com")
DB_NAME = os.environ.get("DB_NAME", "conafood")
DB_USER = os.environ.get("DB_USER", "luis5531")
DB_PASS = os.environ.get("DB_PASS", "q16ddEGzzySuQJeWHHx6iG4GO0rht9kG")
DB_PORT = int(os.environ.get("DB_PORT", 5432))

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

# ----------------------------
# Rutas principales
# ----------------------------

@app.route("/")
@app.route("/panel")
def panel():
    # Sirve el panel de cafetería
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "panel_cafeteria.html")

@app.route("/pedidos", methods=["GET"])
def obtener_pedidos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vista_pedidos ORDER BY fecha DESC;")
    pedidos = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([
        {
            "id_pedido": p[0],
            "usuario": p[1],
            "producto": p[2],
            "cantidad": p[3],
            "estado": p[4],
            "fecha": p[5].strftime("%Y-%m-%d %H:%M:%S")
        }
        for p in pedidos
    ])

@app.route("/pedidos/<int:pedido_id>", methods=["PATCH"])
def actualizar_pedido(pedido_id):
    nuevo_estado = request.json.get("estado")
    if nuevo_estado not in ["pendiente", "en_preparacion", "entregado"]:
        return jsonify({"error": "Estado inválido"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET estado=%s WHERE id_pedido=%s", (nuevo_estado, pedido_id))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Pedido actualizado correctamente"})

# ----------------------------
# Ejecutar servidor
# ----------------------------
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
