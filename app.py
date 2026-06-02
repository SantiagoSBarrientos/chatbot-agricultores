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
    "👋 ¡Hola! Bienvenido al registro de agricultores.\n\nEscriba *reiniciar* en cualquier momento para empezar de nuevo.\n\n¿Cuál es su nombre completo?",
    "¿En qué municipio vive?",
    "¿En qué vereda vive?",
    "¿Qué tipo de cultivo tiene? (ej: plátano, cacao, maíz...)",
    "¿Cuántas hectáreas tiene? (solo el número, ej: 2.5)",
    "¿Cuál es su número de teléfono? (solo números, ej: 3001234567)"
]

CAMPOS = ["nombre", "municipio", "vereda", "cultivo", "hectareas", "telefono"]

def validar(paso, valor):
    if len(valor) < 2:
        return False, "⚠️ La respuesta es muy corta. Por favor intente de nuevo."
    if paso == 4:
        try:
            float(valor)
        except:
            return False, "⚠️ Por favor escriba solo el número de hectáreas. Ejemplo: 2.5"
    if paso == 5:
        if not valor.replace("+","").replace(" ","").isdigit() or len(valor.replace("+","").replace(" ","")) < 7:
            return False, "⚠️ Por favor escriba un número de teléfono válido. Ejemplo: 3001234567"
    return True, ""

@app.route("/webhook", methods=["POST"])
def webhook():
    numero = request.form.get("From")
    mensaje = request.form.get("Body", "").strip()
    resp = MessagingResponse()
    msg = resp.message()

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
                msg.body(error_msg + "\n\n" + PREGUNTAS[paso - 1])
                return str(resp)
            estado["datos"][campo] = mensaje

        if paso < len(PREGUNTAS):
            msg.body(PREGUNTAS[paso])
            estado["paso"] += 1

    elif paso == len(PREGUNTAS):
        campo = CAMPOS[paso - 1]
        valido, error_msg = validar(paso - 1, mensaje)
        if not valido:
            msg.body(error_msg + "\n\n" + PREGUNTAS[paso - 1])
            return str(resp)
        estado["datos"][campo] = mensaje

        datos = estado["datos"]
        resumen = (
            f"📋 *Resumen de su registro:*\n\n"
            f"👤 Nombre: {datos.get('nombre')}\n"
            f"🏘️ Municipio: {datos.get('municipio')}\n"
            f"🌾 Vereda: {datos.get('vereda')}\n"
            f"🌱 Cultivo: {datos.get('cultivo')}\n"
            f"📐 Hectáreas: {datos.get('hectareas')}\n"
            f"📱 Teléfono: {datos.get('telefono')}\n\n"
            f"¿Los datos son correctos?\nEscriba *SI* para confirmar o *NO* para empezar de nuevo."
        )
        msg.body(resumen)
        estado["paso"] += 1

    elif paso == len(PREGUNTAS) + 1:
        if mensaje.upper() == "SI":
            try:
                supabase.table("agricultores").insert(estado["datos"]).execute()
                msg.body("✅ ¡Gracias! Sus datos han sido registrados exitosamente. 🌱\n\nEscriba *hola* si desea registrar otro agricultor.")
            except Exception as e:
                msg.body("❌ Hubo un error guardando sus datos. Por favor escriba *reiniciar* para intentar de nuevo.")
            del conversaciones[numero]
        elif mensaje.upper() == "NO":
            del conversaciones[numero]
            conversaciones[numero] = {"paso": 0, "datos": {}}
            msg.body(PREGUNTAS[0])
            conversaciones[numero]["paso"] = 1
        else:
            msg.body("Por favor escriba *SI* para confirmar o *NO* para empezar de nuevo.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
