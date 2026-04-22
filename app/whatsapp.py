import os
import requests
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from app.responses import responder_chat

router = APIRouter()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")


@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(challenge or "")

    return PlainTextResponse("Error de verificacion", status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return JSONResponse({"status": "ignored"})

        mensaje_data = value["messages"][0]
        numero = mensaje_data["from"]

# Ajuste para números móviles de Argentina en entorno de prueba de Meta
        if numero.startswith("549"):
            numero = "54" + numero[3:]

        if mensaje_data.get("type") != "text":
            enviar_mensaje(numero, "Por ahora solo puedo procesar mensajes de texto.")
            return JSONResponse({"status": "ok"})

        texto = mensaje_data["text"]["body"].strip()

        respuesta = responder_chat(texto)
        enviar_mensaje(numero, respuesta)

        return JSONResponse({"status": "ok"})

    except Exception as e:
        print("Error en webhook:", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=200)


print("NUMERO RECIBIDO:", mensaje_data["from"])
print("NUMERO AJUSTADO:", numero)

def enviar_mensaje(numero: str, mensaje: str):
    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {
            "body": mensaje
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=20)
    print("WhatsApp send status:", response.status_code, response.text)