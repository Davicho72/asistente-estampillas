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

# 🔒 CONTRASEÑA DE ACCESO
CLAVE_CORRECTA = "AhoraNorbury2026"

# 🔧 LECTURA DE CLAVES
EBAY_APP_ID = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CERT_ID = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID", "")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"

# 🔧 API MISTRAL
def llamar_mistral(mensajes, temperatura=0.0, max_tokens=800):
    if not MISTRAL_API_KEY:
        return "ERROR: MISTRAL_API_KEY no configurada en Secrets"
    cabeceras = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    mensajes_formateados = []
    for m in mensajes:
        if isinstance(m["content"], str):
            mensajes_formateados.append({"role": m["role"], "content": [{"type": "text", "text": m["content"]}]})
        else:
            mensajes_formateados.append(m)
    datos = {
        "model": MISTRAL_MODEL,
        "messages": mensajes_formateados,
        "temperature": temperatura,
        "max_tokens": max_tokens
    }
    try:
        respuesta = requests.post(MISTRAL_URL, headers=cabeceras, json=datos, timeout=90)
        if not respuesta.ok:
            return f"ERROR API: {respuesta.status_code} - {respuesta.text[:300]}"
        return respuesta.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error conexión: {str(e)}"

# 🔧 CONFIGURACIÓN EBAY
EBAY_SITIO = "3"
CATEGORIA_EBAY = "260"
MONEDA_EBAY = "GBP"
CAMPO_PUBLICAR = "Publicar en eBay"

def obtener_token_ebay():
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_REFRESH_TOKEN]):
        return None
    credenciales = f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode("utf-8")
    auth_b64 = base64.b64encode(credenciales).decode("utf-8")
    cabeceras = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    datos = {
        "grant_type": "refresh_token",
        "refresh_token": EBAY_REFRESH_TOKEN,
        "scope": "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.item https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/sell.fulfillment"
    }
    try:
        respuesta = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            headers=cabeceras,
            data=datos,
            timeout=30
        )
        if not respuesta.ok:
            return None
        return respuesta.json()["access_token"]
    except:
        return None

def publicar_en_ebay(datos):
    EBAY_TOKEN = obtener_token_ebay()
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_DEV_ID, EBAY_TOKEN]):
        return False, "Faltan claves de eBay o no se pudo generar el token"
    try:
        precio_texto = str(datos.get("sale_price_gbp", "0.5")).strip().replace(",", ".")
        precio_solo_numeros = re.sub(r"[^0-9.]", "", precio_texto)
        precio_num = float(precio_solo_numeros) if precio_solo_numeros else 0.5
    except:
        precio_num = 0.5
    if precio_num <= 0:
        return False, "Precio en GBP no válido"
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
    descripcion = f"""Estampilla auténtica y original.
País: {datos['country']}
Año: {datos.get('year','No especificado')}
Valor facial: {datos.get('face_value','No especificado')}
Estado: {datos.get('condition','No especificado')}
Detalles: {datos.get('description','Sin detalles adicionales')}

Envío seguro y rápido desde Reino Unido."""
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
            return False, f"Error HTTP {resp.status_code}"
        ns = {"ebay": "urn:ebay:apis:eBLBaseComponents"}
        raiz = ET.fromstring(resp.text)
        id_anuncio = raiz.find("ebay:ItemID", ns)
        if id_anuncio is not None and id_anuncio.text:
            return True, f"✅ Publicado | ID: {id_anuncio.text}"
        return True, "✅ Publicado correctamente"
    except Exception as e:
        return False, f"Fallo: {str(e)}"

# 🔧 AIRTABLE
CONECTADO_AIRTABLE = False
try:
    api_airtable = Api(os.getenv("AIRTABLE_API_KEY"))
    tabla_airtable = api_airtable.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLA"))
    CONECTADO_AIRTABLE = True
except:
    pass

def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo=Image.new("RGB",img.size,(255,255,255))
        fondo.paste(img,mask=img.split()[3] if img.mode=="RGBA" else None)
        img=fondo
    elif img.mode!="RGB":
        img=img.convert("RGB")
    img=img.resize((350,int(img.height*(350/img.width))), Image.Resampling.BILINEAR)
    buf=io.BytesIO()
    img.save(buf,format="JPEG",quality=70,optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def extraer_json(texto):
    m=re.search(r'\[.*\]|\{.*\}',texto,re.DOTALL)
    return json.loads(m.group()) if m else None

def analizar_estampa(img,b64):
    instruccion="Identifica solo datos seguros. Devuelve JSON: [{country,year,face_value,condition,sale_price_gbp(numero),description}]. Precio min 0.50 GBP."
    for _ in range(3):
        try:
            time.sleep(1.5)
            res=llamar_mistral([{"role":"user","content":[{"type":"text","text":instruccion},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
            d=extraer_json(res)
            return d if isinstance(d,list) else [d]
        except:
            time.sleep(2)
    return [{"country":"Desconocido","year":"-","face_value":"-","condition":"-","sale_price_gbp":0.50,"description":"Error análisis"}]

# 🎨 INTERFAZ GRADIO — MISMA APARIENCIA, MISMOS TEXTOS Y BOTONES
with gr.Blocks(css="""
* {box-sizing:border-box !important;}
.gradio-container {max-width:100% !important; margin:0 !important; padding:0.5rem !important;}
button {width:100% !important; min-height:48px !important; font-size:16px !important; margin:0.4rem 0 !important;}
.gr-textbox, .gr-textarea, .gr-checkbox, .gr-image, .gr-file, .gr-radio {width:100% !important; font-size:15px !important;}
h1 {font-size:22px !important;} h2 {font-size:20px !important;} h3 {font-size:18px !important;}
""", title="Asistente Estampillas") as demo:

    # ESTADOS
    estado_auth = gr.State(False)
    estado_camara = gr.State(False)
    estado_ver_catalogo = gr.State(False)

    # 🔒 PANTALLA DE ACCESO
    with gr.Column() as pantalla_acceso:
        gr.Markdown("### 🔒 Acceso restringido")
        gr.Markdown("Aplicación privada: ingresa la contraseña para continuar.")
        entrada_clave = gr.Textbox(type="password", label="Contraseña")
        btn_entrar = gr.Button("Ingresar")
        msg_acceso = gr.Markdown()

    # 🖥️ PANTALLA PRINCIPAL
    with gr.Column(visible=False) as pantalla_principal:
        gr.Markdown("# 📮 Asistente de Estampillas")
        if CONECTADO_AIRTABLE:
            gr.Markdown("✅ Conectado a Airtable")

        gr.Markdown("## 🚀 Publicar desde Airtable")
        btn_publicar_airtable = gr.Button("🔍 Revisar y publicar")

        gr.Markdown("## 📤 Cargar o tomar estampillas")
        modo_subida = gr.Radio(["📂 Galería", "📸 Tomar foto"], label="Elige cómo subir:")
        archivos = gr.File(file_types=["image"], file_count="multiple", label="Selecciona imágenes")
        btn_abrir_cam = gr.Button("📸 Abrir cámara")
        btn_cerrar_cam = gr.Button("❌ Cerrar cámara")

        btn_guardar = gr.Button("📥 Guardar seleccionadas en Airtable")
        btn_publicar = gr.Button("📤 Publicar seleccionadas en eBay")

        gr.Markdown("## 📚 Catálogo guardado")
        btn_ver_catalogo = gr.Button("Ver / Ocultar catálogo")

        gr.Markdown("## 🌍 Buscar compradores y contactos")
        btn_buscar = gr.Button("Buscar ahora")

        gr.Markdown("## 💬 Otras consultas")
        tipo_pregunta = gr.Radio(["✍️ Texto", "🎤 Voz"], label="¿Cómo preguntas?")
        entrada_pregunta = gr.Textbox(label="Escribe tu consulta", lines=3)
        btn_enviar = gr.Button("Enviar consulta")

        btn_descargar = gr.Button("📥 Descargar CSV")

    # LÓGICA ACCESO
    def verificar_acceso(clave):
        if clave == CLAVE_CORRECTA:
            return gr.update(visible=False), gr.update(visible=True), ""
        elif clave:
            return gr.update(), gr.update(), "❌ Contraseña incorrecta"
        return gr.update(), gr.update(), ""

    btn_entrar.click(verificar_acceso, entrada_clave, [pantalla_acceso, pantalla_principal, msg_acceso])

# ✅ ARRANQUE CORRECTO PARA RENDER
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 10000))
    )