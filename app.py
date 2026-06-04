from flask import Flask, request, send_from_directory
import requests
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

conversaciones = {}

PREGUNTAS = [
    "👋 ¡Hola! Bienvenido al registro de agricultores.\n\nEscriba *reiniciar* en cualquier momento para empezar de nuevo.\n\n¿Cuál es su nombre completo?",
    "¿En qué municipio vive?",
    "¿En qué barrio, vereda o corregimiento vive?",
    "¿Qué tipo de cultivo tiene? (ej: plátano, cacao, maíz...)",
    "¿Cuántas hectáreas tiene? (solo el número, ej: 2.5)",
    "¿Cuál es su número de teléfono? (solo números, ej: 3001234567)"
]

CAMPOS = ["nombre", "municipio", "vereda", "cultivo", "hectareas", "telefono"]


def enviar_mensaje(numero, texto):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }
    requests.post(url, headers=headers, json=payload)


def validar(paso, valor):
    if len(valor) < 2:
        return False, "⚠️ La respuesta es muy corta. Por favor intente de nuevo."
    if paso == 4:
        try:
            float(valor)
        except:
            return False, "⚠️ Por favor escriba solo el número de hectáreas. Ejemplo: 2.5"
    if paso == 5:
        if not valor.replace("+", "").replace(" ", "").isdigit() or len(valor.replace("+", "").replace(" ", "")) < 7:
            return False, "⚠️ Por favor escriba un número de teléfono válido. Ejemplo: 3001234567"
    return True, ""


@app.route("/panel")
def panel():
    return send_from_directory(".", "panel.html")


@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token invalido", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True)

    if not data:
        return "ok", 200

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return "ok", 200

        message = value["messages"][0]
        numero = message["from"]
        mensaje = message["text"]["body"].strip()

    except (KeyError, IndexError):
        return "ok", 200

    if mensaje.lower() in ["reiniciar", "empezar", "inicio", "reset", "hola"]:
        conversaciones[numero] = {"paso": 0, "datos": {}}

    if numero not in conversaciones:
        conversaciones[numero] = {"paso": 0, "datos": {}}

    estado = conversaciones[numero]
    paso = estado["paso"]

    if paso < len(PREGUNTAS):
        if paso > 0:
            campo = CAMPOS[paso - 1]
            valido, error_msg = validar(paso - 1, mensaje)
            if not valido:
                enviar_mensaje(numero, error_msg + "\n\n" + PREGUNTAS[paso - 1])
                return "ok", 200
            estado["datos"][campo] = mensaje

        enviar_mensaje(numero, PREGUNTAS[paso])
        estado["paso"] += 1

    elif paso == len(PREGUNTAS):
        campo = CAMPOS[paso - 1]
        valido, error_msg = validar(paso - 1, mensaje)
        if not valido:
            enviar_mensaje(numero, error_msg + "\n\n" + PREGUNTAS[paso - 1])
            return "ok", 200
        estado["datos"][campo] = mensaje

        datos = estado["datos"]
        resumen = (
            f"📋 *Resumen de su registro:*\n\n"
            f"👤 Nombre: {datos.get('nombre')}\n"
            f"🏘️ Municipio: {datos.get('municipio')}\n"
            f"📍 Sector: {datos.get('vereda')}\n"
            f"🌱 Cultivo: {datos.get('cultivo')}\n"
            f"📐 Hectáreas: {datos.get('hectareas')}\n"
            f"📱 Teléfono: {datos.get('telefono')}\n\n"
            f"¿Los datos son correctos?\nEscriba *SI* para confirmar o *NO* para empezar de nuevo."
        )
        enviar_mensaje(numero, resumen)
        estado["paso"] += 1

    elif paso == len(PREGUNTAS) + 1:
        if mensaje.upper() == "SI":
            try:
                supabase.table("agricultores").insert(estado["datos"]).execute()
                enviar_mensaje(numero, "✅ ¡Gracias! Sus datos han sido registrados exitosamente. 🌱\n\nEscriba *hola* si desea registrar otro agricultor.")
            except Exception as e:
                enviar_mensaje(numero, "❌ Hubo un error guardando sus datos. Por favor escriba *reiniciar* para intentar de nuevo.")
            del conversaciones[numero]
        elif mensaje.upper() == "NO":
            conversaciones[numero] = {"paso": 1, "datos": {}}
            enviar_mensaje(numero, PREGUNTAS[0])
            conversaciones[numero]["paso"] = 1
        else:
            enviar_mensaje(numero, "Por favor escriba *SI* para confirmar o *NO* para empezar de nuevo.")

    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
