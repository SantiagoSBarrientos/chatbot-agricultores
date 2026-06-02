from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

conversaciones = {}

PREGUNTAS = [
    "👋 ¡Hola! Bienvenido al registro de agricultores.\n\n¿Cuál es su nombre completo?",
    "¿En qué municipio vive?",
    "¿En qué vereda vive?",
    "¿Qué tipo de cultivo tiene? (ej: plátano, cacao, maíz...)",
    "¿Cuántas hectáreas tiene de ese cultivo?",
    "¿Cuál es su número de teléfono?"
]

CAMPOS = ["nombre", "municipio", "vereda", "cultivo", "hectareas", "telefono"]

@app.route("/webhook", methods=["POST"])
def webhook():
    numero = request.form.get("From")
    mensaje = request.form.get("Body", "").strip()
    resp = MessagingResponse()
    msg = resp.message()

    if numero not in conversaciones:
        conversaciones[numero] = {"paso": 0, "datos": {}}

    estado = conversaciones[numero]
    paso = estado["paso"]

    if paso < len(PREGUNTAS):
        if paso > 0:
            campo = CAMPOS[paso - 1]
            estado["datos"][campo] = mensaje
        msg.body(PREGUNTAS[paso])
        estado["paso"] += 1

    elif paso == len(PREGUNTAS):
        campo = CAMPOS[paso - 1]
        estado["datos"][campo] = mensaje
        try:
            supabase.table("agricultores").insert(estado["datos"]).execute()
            msg.body("✅ ¡Gracias! Sus datos han sido registrados exitosamente. 🌱")
        except Exception as e:
            msg.body("❌ Hubo un error guardando sus datos. Por favor intente de nuevo.")
        del conversaciones[numero]

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
