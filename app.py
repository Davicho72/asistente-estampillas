import gradio as gr
import base64
from PIL import Image
import io
import os
import json
import re
import time
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pyairtable import Api

# 🔒 CONTRASEÑA
CLAVE_CORRECTA = "AhoraNorbury2026"

# 🔧 CLAVES DE ENTORNO
EBAY_APP_ID = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CERT_ID = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID", "")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"

# 🔧 FUNCIONES (SIN CAMBIOS)
def llamar_mistral(mensajes, temperatura=0.0, max_tokens=800):
    if not MISTRAL_API_KEY:
        return "ERROR: MISTRAL_API_KEY no configurada"
    cabeceras = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    mensajes_formateados = []
    for m in mensajes:
        if isinstance(m["content"], str):
            mensajes_formateados.append({"role": m["role"], "content": [{"type": "text", "text": m["content"]}]})
        else:
            mensajes_formateados.append(m)
    try:
        resp = requests.post(MISTRAL_URL, headers=cabeceras, json={
            "model": MISTRAL_MODEL, "messages": mensajes_formateados,
            "temperature": temperatura, "max_tokens": max_tokens
        }, timeout=90)
        return resp.json()["choices"][0]["message"]["content"] if resp.ok else f"ERROR API: {resp.status_code}"
    except Exception as e:
        return f"Error conexión: {str(e)}"

EBAY_SITIO, CATEGORIA_EBAY, MONEDA_EBAY = "3", "260", "GBP"

def obtener_token_ebay():
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_REFRESH_TOKEN]): return None
    auth_b64 = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    try:
        resp = requests.post("https://api.ebay.com/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": EBAY_REFRESH_TOKEN,
                  "scope": "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.item https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/sell.fulfillment"}, timeout=30)
        return resp.json()["access_token"] if resp.ok else None
    except: return None

def publicar_en_ebay(datos):
    EBAY_TOKEN = obtener_token_ebay()
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_DEV_ID, EBAY_TOKEN]):
        return False, "Faltan claves de eBay"
    try:
        precio_num = float(str(datos.get("sale_price_gbp", "0.5")).strip().replace(",", "."))
    except:
        precio_num = 0.5
    if precio_num <= 0:
        return False, "Precio no válido"
    url = "https://api.ebay.com/ws/api.dll"
    cabeceras = {
        "X-EBAY-API-CALL-NAME": "AddFixedPriceItem",
        "X-EBAY-API-APP-NAME": EBAY_APP_ID,
        "X-EBAY-API-DEV-NAME": EBAY_DEV_ID,
        "X-EBAY-API-CERT-NAME": EBAY_CERT_ID,
        "X-EBAY-API-SITEID": EBAY_SITIO,
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "Authorization": f"Bearer {EBAY_TOKEN}",
        "Content-Type": "text/xml"
    }
    titulo = f"Estampilla {datos['country']} {datos.get('year','')} - {datos.get('condition','')}"[:80]
    descripcion = f"Estampilla auténtica.\nPaís: {datos['country']}\nAño: {datos.get('year','No especificado')}\nValor facial: {datos.get('face_value','No especificado')}\nEstado: {datos.get('condition','No especificado')}\nDetalles: {datos.get('description','Sin detalles')}\nEnvío desde Reino Unido."
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
        <RequesterCredentials><eBayAuthToken>{EBAY_TOKEN}</eBayAuthToken></RequesterCredentials>
        <Item>
            <Title>{titulo}</Title>
            <Description>{descripcion}</Description>
            <Category>{CATEGORIA_EBAY}</Category>
            <StartPrice currencyID="{MONEDA_EBAY}">{precio_num}</StartPrice>
            <Quantity>1</Quantity>
            <ListingDuration>GTC</ListingDuration>
            <Country>GB</Country>
            <Currency>{MONEDA_EBAY}</Currency>
            <Location>Reino Unido</Location>
            <ReturnPolicy>
                <ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption>
                <RefundOption>MoneyBack</RefundOption>
                <ReturnsWithinOption>Days_30</ReturnsWithinOption>
                <ShippingCostPaidByOption>Buyer</ShippingCostPaidByOption>
            </ReturnPolicy>
        </Item>
    </AddFixedPriceItemRequest>"""
    try:
        resp = requests.post(url, data=xml.encode("utf-8"), headers=cabeceras, timeout=60)
        if resp.status_code != 200:
            return False, f"Error {resp.status_code}"
        raiz = ET.fromstring(resp.text)
        id_anuncio = raiz.find("{urn:ebay:apis:eBLBaseComponents}ItemID")
        return (True, f"✅ Publicado | ID: {id_anuncio.text}") if id_anuncio is not None else (True, "✅ Publicado")
    except Exception as e:
        return False, f"Fallo: {str(e)}"

CONECTADO_AIRTABLE = False
try:
    api_airtable = Api(os.getenv("AIRTABLE_API_KEY"))
    tabla_airtable = api_airtable.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLA"))
    CONECTADO_AIRTABLE = True
except: pass

def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo = Image.new("RGB", img.size, (255,255,255))
        fondo.paste(img, mask=img.split()[3] if img.mode=="RGBA" else None)
        img = fondo
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img = img.resize((350, int(img.height*(350/img.width))), Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()

def extraer_json(texto):
    m = re.search(r'\[.*\]|\{.*\}', texto, re.DOTALL)
    return json.loads(m.group()) if m else None

def analizar_estampa(img, b64):
    instruccion = "Devuelve JSON: [{country,year,face_value,condition,sale_price_gbp(numero),description}]. Precio min 0.50 GBP."
    for _ in range(3):
        try:
            time.sleep(1.5)
            res = llamar_mistral([{"role":"user","content":[{"type":"text","text":instruccion},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
            d = extraer_json(res)
            return d if isinstance(d, list) else [d]
        except:
            time.sleep(2)
    return [{"country":"Desconocido","year":"-","face_value":"-","condition":"-","sale_price_gbp":0.50,"description":"Error análisis"}]

# 🎨 ESTILO FUERTE PARA ANULAR EL ANCHO POR DEFECTO DE GRADIO
with gr.Blocks(css="""
button.gr-button { width: auto !important; min-width: auto !important; }
""", title="Asistente Estampillas") as demo:

    with gr.Column() as pantalla_acceso:
        gr.Markdown("### 🔒 Acceso restringido")
        gr.Markdown("Aplicación privada: ingresa la contraseña para continuar.")
        entrada_clave = gr.Textbox(type="password", label="Contraseña")
        btn_entrar = gr.Button("Ingresar")
        msg_acceso = gr.Markdown()

    with gr.Column(visible=False) as pantalla_principal:
        gr.Markdown("# 📮 Asistente de Estampillas")
        if CONECTADO_AIRTABLE:
            gr.Markdown("✅ Conectado a Airtable")

        gr.Markdown("## 🚀 Publicar desde Airtable")
        gr.Button("🔍 Revisar y publicar")

        gr.Markdown("## 📤 Cargar o tomar estampillas")
        gr.Radio(["📂 Galería", "📸 Tomar foto"], label="Elige cómo subir:")
        gr.File(file_types=["image"], file_count="multiple", label="Selecciona imágenes")
        gr.Button("📸 Abrir cámara")
        gr.Button("❌ Cerrar cámara")

        gr.Button("📥 Guardar seleccionadas en Airtable")
        gr.Button("📤 Publicar seleccionadas en eBay")

        gr.Markdown("## 📚 Catálogo guardado")
        gr.Button("Ver / Ocultar catálogo")

        gr.Markdown("## 🌍 Buscar compradores y contactos")
        gr.Button("Buscar ahora")

        gr.Markdown("## 💬 Otras consultas")
        gr.Radio(["✍️ Texto", "🎤 Voz"], label="¿Cómo preguntas?")
        gr.Textbox(label="Escribe tu consulta", lines=3)
        gr.Button("Enviar consulta")

        gr.Button("📥 Descargar CSV")

    def verificar(clave):
        if clave == CLAVE_CORRECTA:
            return gr.update(visible=False), gr.update(visible=True), ""
        elif clave:
            return gr.update(), gr.update(), "❌ Contraseña incorrecta"
        return gr.update(), gr.update(), ""

    btn_entrar.click(verificar, entrada_clave, [pantalla_acceso, pantalla_principal, msg_acceso])

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 10000))
    )