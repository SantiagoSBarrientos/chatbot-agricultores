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
    "📋 Solo necesito hacerte *7 preguntas rápidas* y listo!\n\n"
    "💡 _En cualquier momento escribe *REINICIAR* para empezar de nuevo._\n\n"
    "✏️ Empecemos... ¿Cuál es tu *nombre completo*?"
)

ASOCIACIONES = [
    "Asocpraur",
    "Asociación de Urabá",
    "Aprocesu",
    "Asociación Abibe",
    "Cooperativa Proasiv",
    "Otros",
]

# Pasos:
# 0 → mostrar bienvenida y pedir nombre
# 1 → guardar nombre, pedir municipio
# 2 → guardar municipio, pedir vereda
# 3 → guardar vereda, pedir cultivo
# 4 → guardar cultivo, pedir hectáreas
# 5 → guardar hectáreas, pedir asociación (botones)
# 6 → guardar asociación (o pedir nombre si eligió Otros), pedir teléfono
# 7 → guardar teléfono, mostrar resumen
# 8 → confirmar SI/NO

CAMPOS = ["nombre", "municipio", "vereda", "cultivo", "hectareas", "asociacion", "telefono"]

PREGUNTAS = [
    "🏘️ ¿En qué *municipio* vives?\n\n_(Ej: Apartadó, Turbo, Carepa, Chigorodó...)_",
    "📍 ¿En qué *barrio, vereda o corregimiento* vives?\n\n_(Ej: Vereda La Esperanza, Barrio El Centro...)_",
    "🌾 ¿Qué tipo de *cultivo* tienes?\n\n_(Ej: plátano 🍌, cacao 🍫, maíz 🌽, yuca...)_",
    "📐 ¿Cuántas *hectáreas* tienes?\n\n_(Solo el número, ej: 2.5)_",
    "📱 ¿Cuál es tu *número de teléfono*?\n\n_(Solo números, ej: 3001234567)_",
]

EMOJIS_CAMPO = {
    "nombre": "👤",
    "municipio": "🏘️",
    "vereda": "📍",
    "cultivo": "🌾",
    "hectareas": "📐",
    "asociacion": "🤝",
    "telefono": "📱",
}


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def validar_hectareas(valor):
    try:
        float(valor.replace(",", "."))
        return True, ""
    except:
        return False, "⚠️ *Hectáreas inválidas*\n\nPor favor escribe solo el número.\n_Ejemplo: 2.5_"


def validar_telefono(valor):
    digits = valor.replace("+", "").replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) < 7:
        return False, "⚠️ *Teléfono inválido*\n\nPor favor escribe solo los números.\n_Ejemplo: 3001234567_"
    return True, ""


def validar_texto(valor):
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
    return msg.lower() in [
        "reiniciar", "empezar", "inicio", "reset", "hola", "hi",
        "buenas", "buenos dias", "buenas tardes", "buenas noches"
    ] or msg.lower().startswith("join")


def texto_asociaciones():
    opciones = "\n".join([f"{i+1}. {a}" for i, a in enumerate(ASOCIACIONES)])
    return (
        "🤝 ¿A qué *asociación* perteneces?\n\n"
        f"{opciones}\n\n"
        "_Responde con el número de tu opción_"
    )


# ─── LÓGICA PRINCIPAL ─────────────────────────────────────────────────────────

def procesar_mensaje(numero, mensaje):
    mensaje = mensaje.strip()

    if es_reinicio(mensaje):
        conversaciones[numero] = {"paso": 0, "datos": {}, "esperando_otro": False}
        return BIENVENIDA

    if numero not in conversaciones:
        conversaciones[numero] = {"paso": 0, "datos": {}, "esperando_otro": False}
        return BIENVENIDA

    estado = conversaciones[numero]
    paso = estado["paso"]

    # ── Paso 0: usuario acaba de recibir bienvenida, responde con su nombre
    if paso == 0:
        valido, error = validar_texto(mensaje)
        if not valido:
            return error + "\n\n✏️ ¿Cuál es tu *nombre completo*?"
        estado["datos"]["nombre"] = mensaje
        estado["paso"] = 1
        return "_Pregunta 1 de 7 ✓_\n\n" + PREGUNTAS[0]  # pedir municipio

    # ── Paso 1: guardar municipio, pedir vereda
    elif paso == 1:
        valido, error = validar_texto(mensaje)
        if not valido:
            return error + "\n\n" + PREGUNTAS[0]
        estado["datos"]["municipio"] = mensaje
        estado["paso"] = 2
        return "_Pregunta 2 de 7 ✓_\n\n" + PREGUNTAS[1]

    # ── Paso 2: guardar vereda, pedir cultivo
    elif paso == 2:
        valido, error = validar_texto(mensaje)
        if not valido:
            return error + "\n\n" + PREGUNTAS[1]
        estado["datos"]["vereda"] = mensaje
        estado["paso"] = 3
        return "_Pregunta 3 de 7 ✓_\n\n" + PREGUNTAS[2]

    # ── Paso 3: guardar cultivo, pedir hectáreas
    elif paso == 3:
        valido, error = validar_texto(mensaje)
        if not valido:
            return error + "\n\n" + PREGUNTAS[2]
        estado["datos"]["cultivo"] = mensaje
        estado["paso"] = 4
        return "_Pregunta 4 de 7 ✓_\n\n" + PREGUNTAS[3]

    # ── Paso 4: guardar hectáreas, pedir asociación
    elif paso == 4:
        valido, error = validar_hectareas(mensaje)
        if not valido:
            return error + "\n\n" + PREGUNTAS[3]
        estado["datos"]["hectareas"] = mensaje
        estado["paso"] = 5
        return "_Pregunta 5 de 7 ✓_\n\n" + texto_asociaciones()

    # ── Paso 5: guardar asociación
    elif paso == 5:
        # Si estaba esperando nombre libre (eligió Otros)
        if estado.get("esperando_otro"):
            valido, error = validar_texto(mensaje)
            if not valido:
                return error + "\n\n✏️ Escribe el nombre de tu asociación:"
            estado["datos"]["asociacion"] = mensaje
            estado["esperando_otro"] = False
            estado["paso"] = 6
            return "_Pregunta 6 de 7 ✓_\n\n" + PREGUNTAS[4]  # pedir teléfono

        # Si viene de botón interactivo ya trae el título directamente
        if mensaje in ASOCIACIONES:
            seleccion = mensaje
        else:
            # Intentar por número
            try:
                idx = int(mensaje) - 1
                if 0 <= idx < len(ASOCIACIONES):
                    seleccion = ASOCIACIONES[idx]
                else:
                    return "⚠️ Opción inválida.\n\n" + texto_asociaciones()
            except:
                return "⚠️ Por favor responde con el *número* de tu opción.\n\n" + texto_asociaciones()

        if seleccion == "Otros":
            estado["esperando_otro"] = True
            estado["paso"] = 5  # quedarse en mismo paso
            return "✏️ Escribe el nombre de tu asociación:"
        else:
            estado["datos"]["asociacion"] = seleccion
            estado["esperando_otro"] = False
            estado["paso"] = 6
            return "_Pregunta 6 de 7 ✓_\n\n" + PREGUNTAS[4]  # pedir teléfono

    # ── Paso 5 con esperando_otro: guardar nombre libre de asociación
    # (se maneja arriba, pero por si acaso esperando_otro está activo)

    # ── Paso 6: guardar teléfono, mostrar resumen
    elif paso == 6:
        valido, error = validar_telefono(mensaje)
        if not valido:
            return error + "\n\n" + PREGUNTAS[4]
        estado["datos"]["telefono"] = mensaje
        estado["paso"] = 7
        return "_Pregunta 7 de 7 ✓_\n\n" + construir_resumen(estado["datos"])

    # ── Paso 7: confirmación SI/NO
    elif paso == 7:
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
            conversaciones[numero] = {"paso": 0, "datos": {}, "esperando_otro": False}
            return "🔄 *Empecemos de nuevo*\n\n" + BIENVENIDA
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
                if not mensaje:
                    mensaje = msg["interactive"].get("list_reply", {}).get("title", "")
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
