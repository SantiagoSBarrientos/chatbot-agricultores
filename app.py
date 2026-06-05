from flask import Flask, request, send_from_directory, Response
import os
import requests as http_requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

conversaciones = {}

BIENVENIDA = (
    "🌱 *¡Bienvenido al Sistema de Registro de Agricultores de Urabá!* 🌿\n\n"
    "Hola! Soy tu asistente virtual y voy a ayudarte a registrarte en nuestra base de datos.\n\n"
    "📋 Solo necesito hacerte *6 preguntas rápidas* y listo!\n\n"
    "💡 _En cualquier momento escribe *REINICIAR* para empezar de nuevo._\n\n"
    "✏️ Empecemos... ¿Cuál es tu *nombre completo*?"
)

PREGUNTAS = [
    BIENVENIDA,
    "🏘️ ¿En qué *municipio* vives?\n\n_(Ej: Apartadó, Turbo, Carepa, Chigorodó...)_",
    "📍 ¿En qué *barrio, vereda o corregimiento* vives?\n\n_(Ej: Vereda La Esperanza, Barrio El Centro...)_",
    "🌾 ¿Qué tipo de *cultivo* tienes?\n\n_(Ej: plátano 🍌, cacao 🍫, maíz 🌽, yuca...)_",
    "📐 ¿Cuántas *hectáreas* tienes?\n\n_(Solo el número, ej: 2.5)_",
    "📱 ¿Cuál es tu *número de teléfono*?\n\n_(Solo números, ej: 3001234567)_"
]

CAMPOS = ["nombre", "municipio", "vereda", "cultivo", "hectareas", "telefono"]

EMOJIS_CAMPO = {
    "nombre": "👤",
    "municipio": "🏘️",
    "vereda": "📍",
    "cultivo": "🌾",
    "hectareas": "📐",
    "telefono": "📱"
}


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def validar(paso, valor):
    if paso == 4:
        try:
            float(valor.replace(",", "."))
        except:
            return False, "⚠️ *Hectáreas inválidas*\n\nPor favor escribe solo el número.\n_Ejemplo: 2.5_"
        return True, ""
    if paso == 5:
        digits = valor.replace("+", "").replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 7:
            return False, "⚠️ *Teléfono inválido*\n\nPor favor escribe solo los números.\n_Ejemplo: 3001234567_"
        return True, ""
    if len(valor.strip()) < 2:
        return False, "⚠️ *Respuesta muy corta*\n\nPor favor intenta de nuevo con más detalle."
    return True, ""


def construir_resumen(datos):
    lineas = []
    for campo in CAMPOS:
        emoji = EMOJIS_CAMPO.get(campo, "•")
        valor = datos.get(campo, "-")
        lineas.append(f"{emoji} *{campo.capitalize()}:* {valor}")
    return (
        "📋 *Resumen de tu registro:*\n\n"
        + "\n".join(lineas)
        + "\n\n¿Los datos son correctos?\n\n"
        "✅ Escribe *SI* para confirmar\n"
        "❌ Escribe *NO* para empezar de nuevo"
    )


def es_reinicio(msg):
    return msg.lower() in ["reiniciar", "empezar", "inicio", "reset", "hola", "hi", "buenas", "buenos dias", "buenas tardes", "buenas noches"] or msg.lower().startswith("join")


# ─── LÓGICA PRINCIPAL ─────────────────────────────────────────────────────────

def procesar_mensaje(numero, mensaje):
    mensaje = mensaje.strip()

    if es_reinicio(mensaje):
        conversaciones[numero] = {"paso": 0, "datos": {}}
        return PREGUNTAS[0]

    if numero not in conversaciones:
        conversaciones[numero] = {"paso": 0, "datos": {}}

    estado = conversaciones[numero]
    paso = estado["paso"]

    if paso < len(PREGUNTAS):
        if paso > 0:
            campo = CAMPOS[paso - 1]
            valido, error_msg = validar(paso - 1, mensaje)
            if not valido:
                return error_msg + "\n\n" + PREGUNTAS[paso - 1]
            estado["datos"][campo] = mensaje.strip()

        respuesta = PREGUNTAS[paso]
        estado["paso"] += 1

        if paso > 0:
            progreso = f"_Pregunta {paso} de {len(PREGUNTAS) - 1} ✓_\n\n"
            respuesta = progreso + respuesta

        return respuesta

    elif paso == len(PREGUNTAS):
        campo = CAMPOS[paso - 1]
        valido, error_msg = validar(paso - 1, mensaje)
        if not valido:
            return error_msg + "\n\n" + PREGUNTAS[paso - 1]
        estado["datos"][campo] = mensaje.strip()
        estado["paso"] += 1
        return construir_resumen(estado["datos"])

    elif paso == len(PREGUNTAS) + 1:
        if mensaje.upper() == "SI":
            try:
                supabase.table("agricultores").insert(estado["datos"]).execute()
                del conversaciones[numero]
                return (
                    "🎉 *¡Registro exitoso!*\n\n"
                    "✅ Tus datos han sido guardados correctamente en nuestro sistema.\n\n"
                    "🌱 Gracias por ser parte de la comunidad de agricultores de Urabá.\n\n"
                    "_Escribe *hola* si deseas registrar otro agricultor._"
                )
            except Exception as e:
                print(f"Error Supabase: {e}", flush=True)
                return (
                    "❌ *Error al guardar*\n\n"
                    "Hubo un problema técnico. Por favor escribe *REINICIAR* para intentar de nuevo."
                )
        elif mensaje.upper() == "NO":
            conversaciones[numero] = {"paso": 1, "datos": {}}
            return "🔄 *Empecemos de nuevo*\n\n" + PREGUNTAS[0]
        else:
            return "❓ Por favor escribe *SI* para confirmar o *NO* para empezar de nuevo."

    return "👋 Escribe *hola* para comenzar tu registro."


# ─── TWILIO ───────────────────────────────────────────────────────────────────

def twiml(texto):
    texto_xml = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{texto_xml}</Message></Response>',
        mimetype="text/xml"
    )


# ─── WEBHOOK UNIFICADO ────────────────────────────────────────────────────────

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
    # Detectar si viene de Twilio (form data) o Meta (JSON)
    if request.form.get("Body") is not None:
        # TWILIO
        mensaje = request.form.get("Body", "").strip()
        numero = request.form.get("From", "").replace("whatsapp:", "")

        print(f"[TWILIO] De: {numero} | Msg: {mensaje}", flush=True)

        if not mensaje or not numero:
            return twiml("")

        respuesta = procesar_mensaje(numero, mensaje)
        return twiml(respuesta)

    else:
        # META CLOUD API
        try:
            data = request.json
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return "OK", 200

            msg = messages[0]
            numero = msg.get("from")
            tipo = msg.get("type")

            if tipo == "text":
                mensaje = msg["text"]["body"].strip()
            elif tipo == "interactive":
                mensaje = msg["interactive"].get("button_reply", {}).get("title", "")
            else:
                enviar_meta(numero, "🌱 Por favor envía un mensaje de texto para continuar tu registro.")
                return "OK", 200

            print(f"[META] De: {numero} | Msg: {mensaje}", flush=True)
            respuesta = procesar_mensaje(numero, mensaje)
            enviar_meta(numero, respuesta)

        except Exception as e:
            print(f"[META] Error: {e}", flush=True)

        return "OK", 200


def enviar_meta(numero, texto):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto, "preview_url": False}
    }
    resp = http_requests.post(url, headers=headers, json=payload)
    print(f"[META] Enviado a {numero} | Status: {resp.status_code}", flush=True)


# ─── PANEL ────────────────────────────────────────────────────────────────────

@app.route("/panel")
def panel():
    return send_from_directory(".", "panel.html")


@app.route("/privacy")
def privacy():
    return send_from_directory(".", "privacy.html")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
