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
clave_correcta = "AhoraNorbury2026"
autenticado = gr.State(False)

# 🔧 LECTURA DE CLAVES
EBAY_APP_ID = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CERT_ID = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID", "")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"

# 🔧 FUNCIONES (EXACTAMENTE IGUALES, SIN CAMBIOS)
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
    datos = {"model": MISTRAL_MODEL, "messages": mensajes_formateados, "temperature": temperatura, "max_tokens": max_tokens}
    try:
        respuesta = requests.post(MISTRAL_URL, headers=cabeceras, json=datos, timeout=90)
        return respuesta.json()["choices"][0]["message"]["content"] if respuesta.ok else f"ERROR API: {respuesta.status_code}"
    except Exception as e:
        return f"Error conexión: {str(e)}"

EBAY_SITIO = "3"
CATEGORIA_EBAY = "260"
MONEDA_EBAY = "GBP"
CAMPO_PUBLICAR = "Publicar en eBay"

def obtener_token_ebay():
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_REFRESH_TOKEN]):
        return None
    auth_b64 = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode("utf-8")).decode("utf-8")
    cabeceras = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"}
    datos = {"grant_type": "refresh_token", "refresh_token": EBAY_REFRESH_TOKEN, "scope": "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.item https://api.ebay.com/oauth/api_scope/sell.account https://api.ebay.com/oauth/api_scope/sell.fulfillment"}
    try:
        resp = requests.post("https://api.ebay.com/identity/v1/oauth2/token", headers=cabeceras, data=datos, timeout=30)
        return resp.json()["access_token"] if resp.ok else None
    except: return None

def publicar_en_ebay(datos):
    EBAY_TOKEN = obtener_token_ebay()
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_DEV_ID, EBAY_TOKEN]):
        return False, "Faltan claves de eBay"
    try: precio_num = float(str(datos.get("sale_price_gbp", "0.5")).strip().replace(",", "."))
    except: precio_num = 0.5
    if precio_num <= 0: return False, "Precio no válido"
    url = "https://api.ebay.com/ws/api.dll"
    cabeceras = {"X-EBAY-API-CALL-NAME": "AddFixedPriceItem", "X-EBAY-API-APP-NAME": EBAY_APP_ID, "X-EBAY-API-DEV-NAME": EBAY_DEV_ID, "X-EBAY-API-CERT-NAME": EBAY_CERT_ID, "X-EBAY-API-SITEID": EBAY_SITIO, "X-EBAY-API-COMPATIBILITY-LEVEL": "967", "Authorization": f"Bearer {EBAY_TOKEN}", "Content-Type": "text/xml"}
    titulo = f"Estampilla {datos['country']} {datos['year'] or ''} - {datos['condition']}"[:80]
    descripcion = f"Estampilla auténtica.\nPaís: {datos['country']}\nAño: {datos['year'] or 'No especificado'}\nValor: {datos['face_value'] or 'No especificado'}\nEstado: {datos['condition'] or 'No especificado'}\nDetalles: {datos['description'] or 'Sin detalles'}\nEnvío desde Reino Unido."
    xml = f"""<?xml version="1.0" encoding="utf-8"?><AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents"><RequesterCredentials><eBayAuthToken>{EBAY_TOKEN}</eBayAuthToken></RequesterCredentials><Item><Title>{titulo}</Title><Description>{descripcion}</Description><Category>{CATEGORIA_EBAY}</Category><StartPrice currencyID="{MONEDA_EBAY}">{precio_num}</StartPrice><Quantity>1</Quantity><ListingDuration>GTC</ListingDuration><Country>GB</Country><Currency>{MONEDA_EBAY}</Currency><Location>Reino Unido</Location><ReturnPolicy><ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption><RefundOption>MoneyBack</RefundOption><ReturnsWithinOption>Days_30</ReturnsWithinOption><ShippingCostPaidByOption>Buyer</ShippingCostPaidByOption></ReturnPolicy></Item></AddFixedPriceItemRequest>"""
    try:
        resp = requests.post(url, data=xml.encode("utf-8"), headers=cabeceras, timeout=60)
        if resp.status_code != 200: return False, f"Error {resp.status_code}"
        ns = {"ebay": "urn:ebay:apis:eBLBaseComponents"}
        raiz = ET.fromstring(resp.text)
        id_anuncio = raiz.find("ebay:ItemID", ns)
        return (True, f"✅ Publicado | ID: {id_anuncio.text}") if id_anuncio is not None else (True, "✅ Publicado correctamente")
    except Exception as e: return False, f"Fallo: {str(e)}"

CONECTADO_AIRTABLE = False
try:
    api_airtable = Api(os.getenv("AIRTABLE_API_KEY"))
    tabla_airtable = api_airtable.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLA"))
    CONECTADO_AIRTABLE = True
except: pass

def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo=Image.new("RGB",img.size,(255,255,255))
        fondo.paste(img,mask=img.split()[3] if img.mode=="RGBA" else None)
        img=fondo
    elif img.mode!="RGB": img=img.convert("RGB")
    img=img.resize((350,int(img.height*(350/img.width))), Image.Resampling.BILINEAR)
    buf=io.BytesIO()
    img.save(buf,format="JPEG",quality=70)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def extraer_json(texto):
    m=re.search(r'\[.*\]|\{.*\}',texto,re.DOTALL)
    return json.loads(m.group()) if m else None

def analizar_estampa(img,b64):
    instruccion="Devuelve JSON: [{country,year,face_value,condition,sale_price_gbp(numero),description}]. Precio min 0.50 GBP."
    for _ in range(3):
        try:
            time.sleep(1.5)
            res=llamar_mistral([{"role":"user","content":[{"type":"text","text":instruccion},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
            d=extraer_json(res)
            return d if isinstance(d,list) else [d]
        except: time.sleep(2)
    return [{"country":"Desconocido","year":"-","face_value":"-","condition":"-","sale_price_gbp":0.50,"description":"Error análisis"}]

# 🎨 INTERFAZ EN GRADIO — MISMA APARIENCIA, MISMOS TEXTOS Y BOTONES
with gr.Blocks(css="""
* {box-sizing:border-box !important;}
.gradio-container {max-width:100% !important; padding:0.5rem !important;}
button {width:100% !important; min-height:48px !important; font-size:16px !important; margin:0.4rem 0 !important;}
.gr-textbox, .gr-textarea, .gr-checkbox, .gr-image, .gr-file {width:100% !important; font-size:15px !important;}
h1 {font-size:22px !important;} h2 {font-size:20px !important;} h3 {font-size:18px !important;}
""", title="Asistente Estampilla") as demo:

    estado_auth = gr.State(False)
    estado_camara = gr.State(False)
    estado_catalogo = gr.State(False)

    # 🔒 PANTALLA DE ACCESO
    with gr.Column(visible=True) as pantalla_acceso:
        gr.Markdown("### 🔒 Acceso restringido")
        gr.Markdown("Aplicación privada: ingresa la contraseña para continuar.")
        entrada_clave = gr.Textbox(type="password", label="Contraseña")
        btn_entrar = gr.Button("Ingresar")
        mensaje_error = gr.Markdown()

    def verificar_acceso(clave):
        if clave == clave_correcta:
            return True, gr.update(visible=False), gr.update(visible=True), ""
        elif clave:
            return False, gr.update(), gr.update(), "❌ Contraseña incorrecta"
        return False, gr.update(), gr.update(), ""

    # 🖥️ PANTALLA PRINCIPAL
    with gr.Column(visible=False) as pantalla_principal:
        gr.Markdown("# 📮 Asistente de Estampillas")
        if CONECTADO_AIRTABLE:
            gr.Markdown("✅ Conectado a Airtable")

        # 🚀 PUBLICAR DESDE AIRTABLE
        gr.Markdown("## 🚀 Publicar desde Airtable")
        btn_publicar_airtable = gr.Button("🔍 Revisar y publicar")
        res_airtable = gr.Markdown()

        # 📤 CARGAR O TOMAR FOTO
        gr.Markdown("## 📤 Cargar o tomar estampillas")
        modo_subida = gr.Radio(["📂 Galería", "📸 Tomar foto"], label="Elige cómo subir:")

        with gr.Column() as zona_galeria:
            archivos = gr.File(file_types=["image"], file_count="multiple", label="Selecciona imágenes")

        with gr.Column(visible=False) as zona_camara:
            btn_abrir_cam = gr.Button("📸 Abrir cámara")
            foto_cam = gr.Image(source="webcam", type="pil", visible=False)
            btn_cerrar_cam = gr.Button("❌ Cerrar cámara", visible=False)

        # 📊 RESULTADOS Y ACCIONES
        zona_resultados = gr.Column()
        btn_guardar = gr.Button("📥 Guardar seleccionadas en Airtable", visible=False)
        btn_publicar = gr.Button("📤 Publicar seleccionadas en eBay", visible=False)
        res_acciones = gr.Markdown()

        # 📚 CATÁLOGO
        gr.Markdown("## 📚 Catálogo guardado")
        btn_ver_catalogo = gr.Button("Ver / Ocultar catálogo")
        tabla_catalogo = gr.Dataframe(visible=False)

        # 🌍 BUSCAR COMPRADORES
        gr.Markdown("## 🌍 Buscar compradores y contactos")
        btn_buscar = gr.Button("Buscar ahora")
        res_buscar = gr.Markdown()

        # 💬 CONSULTAS
        gr.Markdown("## 💬 Otras consultas")
        tipo_consulta = gr.Radio(["✍️ Texto", "🎤 Voz"], label="¿Cómo preguntas?")
        pregunta = gr.Textbox(label="Escribe tu consulta", lines=3)
        btn_enviar = gr.Button("Enviar consulta")
        res_consulta = gr.Markdown()

        # 📥 DESCARGA
        btn_descargar = gr.Button("📥 Descargar CSV")

    # LÓGICA DE CAMBIOS DE VISTA
    def cambiar_modo(modo):
        if modo == "📂 Galería":
            return gr.update(visible=True), gr.update(visible=False)
        else:
            return gr.update(visible=False), gr.update(visible=True)

    def abrir_cam():
        return gr.update(visible=False), gr.update(visible=True), gr.update(visible=True)

    def cerrar_cam():
        return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)

    # ASIGNAR EVENTOS
    btn_entrar.click(verificar_acceso, entrada_clave, [estado_auth, pantalla_acceso, pantalla_principal, mensaje_error])
    modo_subida.change(cambiar_modo, modo_subida, [zona_galeria, zona_camara])
    btn_abrir_cam.click(abrir_cam, outputs=[btn_abrir_cam, foto_cam, btn_cerrar_cam])
    btn_cerrar_cam.click(cerrar_cam, outputs=[btn_abrir_cam, foto_cam, btn_cerrar_cam])

# 🚀 EJECUTAR
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)