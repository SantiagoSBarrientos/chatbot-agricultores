from flask import Flask, request, send_from_directory, Response
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

conversaciones = {}

PREGUNTAS = [
    "👋 ¡Hola! Bienvenido al registro de agricultores.\n\nEscriba reiniciar en cualquier momento para empezar de nuevo.\n\n¿Cuál es su nombre completo?",
    "¿En qué municipio vive?",
    "¿En qué barrio, vereda o corregimiento vive?",
    "¿Qué tipo de cultivo tiene? (ej: plátano, cacao, maíz...)",
    "¿Cuántas hectáreas tiene? (solo el número, ej: 2.5)",
    "¿Cuál es su número de teléfono? (solo números, ej: 3001234567)"
]

CAMPOS = ["nombre", "municipio", "vereda", "cultivo", "hectareas", "telefono"]


def twiml(texto):
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{texto}</Message></Response>',
        mimetype="text/xml"
    )


def validar(paso, valor):
    if paso == 4:
        try:
            float(valor.replace(",", "."))
        except:
            return False, "⚠️ Por favor escriba solo el número de hectáreas. Ejemplo: 2.5"
        return True, ""
    if paso == 5:
        digits = valor.replace("+", "").replace(" ", "")
        if not digits.isdigit() or len(digits) < 7:
            return False, "⚠️ Por favor escriba un número de teléfono válido. Ejemplo: 3001234567"
        return True, ""
    if len(valor) < 2:
        return False, "⚠️ La respuesta es muy corta. Por favor intente de nuevo."
    return True, ""


@app.route("/panel")
def panel():
    return send_from_directory(".", "panel.html")


@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    verify_token = os.getenv("VERIFY_TOKEN")
    if mode == "subscribe" and token == verify_token:
        return challenge, 200
    return "Token invalido", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    mensaje = request.form.get("Body", "").strip()
    numero = request.form.get("From", "").replace("whatsapp:", "")

    print(f"Mensaje recibido - numero: {numero}, mensaje: {mensaje}", flush=True)

    if not mensaje or not numero:
        return twiml("")

    if mensaje.lower() in ["reiniciar", "empezar", "inicio", "reset", "hola"] or mensaje.lower().startswith("join"):
        conversaciones[numero] = {"paso": 0, "datos": {}}
        if mensaje.lower().startswith("join"):
            return twiml(PREGUNTAS[0])

    if numero not in conversaciones:
        conversaciones[numero] = {"paso": 0, "datos": {}}

    estado = conversaciones[numero]
    paso = estado["paso"]

    if paso < len(PREGUNTAS):
        if paso > 0:
            campo = CAMPOS[paso - 1]
            valido, error_msg = validar(paso - 1, mensaje)
            if not valido:
                return twiml(error_msg + "\n\n" + PREGUNTAS[paso - 1])
            estado["datos"][campo] = mensaje

        respuesta = PREGUNTAS[paso]
        estado["paso"] += 1
        return twiml(respuesta)

    elif paso == len(PREGUNTAS):
        campo = CAMPOS[paso - 1]
        valido, error_msg = validar(paso - 1, mensaje)
        if not valido:
            return twiml(error_msg + "\n\n" + PREGUNTAS[paso - 1])
        estado["datos"][campo] = mensaje

        datos = estado["datos"]
        resumen = (
            f"Resumen de su registro:\n\n"
            f"Nombre: {datos.get('nombre')}\n"
            f"Municipio: {datos.get('municipio')}\n"
            f"Sector: {datos.get('vereda')}\n"
            f"Cultivo: {datos.get('cultivo')}\n"
            f"Hectareas: {datos.get('hectareas')}\n"
            f"Telefono: {datos.get('telefono')}\n\n"
            f"Los datos son correctos?\nEscriba SI para confirmar o NO para empezar de nuevo."
        )
        estado["paso"] += 1
        return twiml(resumen)

    elif paso == len(PREGUNTAS) + 1:
        if mensaje.upper() == "SI":
            try:
                supabase.table("agricultores").insert(estado["datos"]).execute()
                del conversaciones[numero]
                return twiml("✅ Gracias! Sus datos han sido registrados exitosamente.\n\nEscriba hola si desea registrar otro agricultor.")
            except Exception as e:
                print(f"Error Supabase: {e}", flush=True)
                return twiml("❌ Hubo un error guardando sus datos. Por favor escriba reiniciar para intentar de nuevo.")
        elif mensaje.upper() == "NO":
            conversaciones[numero] = {"paso": 1, "datos": {}}
            return twiml(PREGUNTAS[0])
        else:
            return twiml("Por favor escriba SI para confirmar o NO para empezar de nuevo.")

    return twiml("Escriba hola para comenzar.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
