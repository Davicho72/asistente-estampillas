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

# 🔧 LECTURA DE CLAVES (igual que antes)
EBAY_APP_ID = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CERT_ID = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID", "")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLA = os.getenv("AIRTABLE_TABLA", "")

EBAY_SITIO = "3"
CATEGORIA_EBAY = "260"
MONEDA_EBAY = "GBP"
CAMPO_PUBLICAR = "Publicar en eBay"

# 🔧 FUNCIONES (TODAS IGUALES, SIN CAMBIOS)
def llamar_mistral(mensajes, temperatura=0.0, max_tokens=800):
    if not MISTRAL_API_KEY:
        return "ERROR: MISTRAL_API_KEY no configurada"
    cabeceras = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    mensajes_formateados = []
    for m in mensajes:
        mensajes_formateados.append({"role": m["role"], "content": [{"type": "text", "text": m["content"]}] if isinstance(m["content"], str) else m["content"]})
    datos = {"model": MISTRAL_MODEL, "messages": mensajes_formateados, "temperature": temperatura, "max_tokens": max_tokens}
    try:
        resp = requests.post(MISTRAL_URL, headers=cabeceras, json=datos, timeout=90)
        return resp.json()["choices"][0]["message"]["content"] if resp.ok else f"ERROR API: {resp.status_code}"
    except Exception as e:
        return f"Error conexión: {str(e)}"

def obtener_token_ebay():
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_REFRESH_TOKEN]): return None
    auth_b64 = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    cabeceras = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"}
    datos = {"grant_type": "refresh_token", "refresh_token": EBAY_REFRESH_TOKEN, "scope": "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.item"}
    try:
        resp = requests.post("https://api.ebay.com/identity/v1/oauth2/token", headers=cabeceras, data=datos, timeout=30)
        return resp.json()["access_token"] if resp.ok else None
    except: return None

def publicar_en_ebay(datos):
    tok = obtener_token_ebay()
    if not tok: return False, "Sin token de eBay"
    try:
        precio = float(re.sub(r"[^0-9.]", "", str(datos.get("sale_price_gbp", "0.5")).strip().replace(",", ".")))
    except: precio = 0.5
    if precio <= 0: return False, "Precio inválido"
    titulo = f"Estampilla {datos['country']} {datos['year'] or ''} - {datos['condition']}"[:80]
    desc = f"""País: {datos['country']}
Año: {datos['year'] or 'Sin dato'}
Valor facial: {datos['face_value'] or 'Sin dato'}
Estado: {datos['condition'] or 'Sin dato'}
Detalles: {datos['description'] or 'Sin detalles'}
Envío desde Reino Unido."""
    xml = f"""<?xml version="1.0"?>
    <AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
        <RequesterCredentials><eBayAuthToken>{tok}</eBayAuthToken></RequesterCredentials>
        <Item><Title>{titulo}</Title><Description>{desc}</Description><Category>{CATEGORIA_EBAY}</Category>
        <StartPrice currencyID="{MONEDA_EBAY}">{precio}</StartPrice><Quantity>1</Quantity><ListingDuration>GTC</ListingDuration>
        <Country>GB</Country><Currency>{MONEDA_EBAY}</Currency><Location>Reino Unido</Location>
        <ReturnPolicy><ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption><RefundOption>MoneyBack</RefundOption>
        <ReturnsWithinOption>Days_30</ReturnsWithinOption><ShippingCostPaidByOption>Buyer</ShippingCostPaidByOption></ReturnPolicy></Item>
    </AddFixedPriceItemRequest>"""
    cab = {"X-EBAY-API-CALL-NAME":"AddFixedPriceItem","X-EBAY-API-APP-NAME":EBAY_APP_ID,"X-EBAY-API-DEV-NAME":EBAY_DEV_ID,
           "X-EBAY-API-CERT-NAME":EBAY_CERT_ID,"X-EBAY-API-SITEID":EBAY_SITIO,"X-EBAY-API-COMPATIBILITY-LEVEL":"967",
           "Authorization":f"Bearer {tok}","Content-Type":"text/xml"}
    try:
        r = requests.post("https://api.ebay.com/ws/api.dll", data=xml.encode("utf-8"), headers=cab, timeout=60)
        if r.status_code!=200: return False, f"Error {r.status_code}"
        ns={"ebay":"urn:ebay:apis:eBLBaseComponents"}
        idv=ET.fromstring(r.text).find("ebay:ItemID",ns)
        return (True,f"✅ Publicado | ID: {idv.text}") if idv is not None else (True,"✅ Publicado")
    except Exception as e: return False, str(e)

CONECTADO=False
try:
    api=Api(AIRTABLE_API_KEY)
    tabla=api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLA)
    CONECTADO=True
except: pass

def cargar_base():
    if not CONECTADO: return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","Publicar en eBay","ID eBay","image_b64"])
    try:
        return pd.DataFrame([{**{"id":f.get("id")},**f} for f in [r["fields"] for r in tabla.all()]])
    except: return pd.DataFrame()

def guardar_seleccionadas(lista):
    if not CONECTADO or not lista: return f"Guardadas: 0"
    guardados=0
    for r in lista:
        fecha=datetime.now().isoformat(timespec="seconds")+"Z"
        try: precio=float(re.sub(r"[^0-9.]", "", str(r.get("sale_price_gbp","0.5")).strip().replace(",",".")))
        except: precio=0.5
        anio=str(r.get("year","")).strip() if r.get("year") not in (None,"","-") else ""
        reg=tabla.create({
            "saved_date":fecha,"country":r["country"],"year":anio,"Face_value":r["face_value"],
            "condition":r["condition"],"sale_price_gbp":precio,"description":r["description"],
            "Publicar en eBay":False,"image_b64":r["image_b64"]
        }, typecast=True)
        img_b64=r.get("image_b64")
        if img_b64:
            try: tabla.upload_attachment(reg["id"],"Imagen","estampilla.jpg",base64.b64decode(img_b64),"image/jpeg")
            except: pass
        guardados+=1
    return f"✅ Guardadas: {guardados}"

def publicar_seleccionadas(lista):
    if not lista: return f"Publicadas: 0"
    pub=0
    mensajes=[]
    for r in lista:
        anio=str(r.get("year","")).strip() if r.get("year") not in (None,"","-") else ""
        datos={"country":r["country"],"year":anio,"face_value":r["face_value"],"condition":r["condition"],"sale_price_gbp":r["sale_price_gbp"],"description":r["description"]}
        ok,res=publicar_en_ebay(datos)
        if ok:
            mensajes.append(f"✅ {res}")
            if CONECTADO:
                fecha=datetime.now().isoformat(timespec="seconds")+"Z"
                try: precio=float(re.sub(r"[^0-9.]", "", str(r.get("sale_price_gbp","0.5")).strip().replace(",",".")))
                except: precio=0.5
                tabla.create({"saved_date":fecha,"country":datos["country"],"year":anio,"Face_value":datos["face_value"],
                              "condition":datos["condition"],"sale_price_gbp":precio,"description":datos["description"],
                              "Publicar en eBay":False,"ID eBay":res,"image_b64":r["image_b64"]}, typecast=True)
            pub+=1
        else:
            mensajes.append(f"❌ No publicado: {res}")
    mensajes.append(f"Total publicadas: {pub}")
    return "\n".join(mensajes)

def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo=Image.new("RGB",img.size,(255,255,255))
        fondo.paste(img,mask=img.split()[3] if img.mode=="RGBA" else None)
        img=fondo
    elif img.mode!="RGB": img=img.convert("RGB")
    img=img.resize((350,int(img.height*350/img.width)),Image.Resampling.BILINEAR)
    b=io.BytesIO();img.save(b,"JPEG",quality=70);return base64.b64encode(b.getvalue()).decode()

def extraer_json(texto):
    m=re.search(r'\[.*\]|\{.*\}',texto,re.DOTALL);return json.loads(m.group()) if m else None

def analizar_estampa(img,b64):
    ins="Devuelve JSON: [{country,year,face_value,condition,sale_price_gbp(numero ≥0.5),description}]."
    for _ in range(3):
        try:
            time.sleep(1.5)
            res=llamar_mistral([{"role":"user","content":[{"type":"text","text":ins},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
            d=extraer_json(res);return d if isinstance(d,list) else [d]
        except: time.sleep(2)
    return [{"country":"Desconocido","year":"-","face_value":"-","condition":"-","sale_price_gbp":0.50,"description":"Error análisis"}]

# 🖥️ INTERFAZ GRADIO CON CÁMARA DIRECTA A TRASERA
with gr.Blocks(title="Asistente Estampillas") as demo:
    auth = gr.State(False)
    gr.Markdown("# 📮 Asistente de Estampillas")

    # PANTALLA DE ACCESO
    with gr.Group(visible=False) as pantalla_acceso:
        clave_in = gr.Textbox(label="Contraseña", type="password")
        btn_acceso = gr.Button("Ingresar", variant="primary")
        msj_acceso = gr.Markdown()

    # PANTALLA PRINCIPAL
    with gr.Group(visible=False) as pantalla_principal:
        estado_conexion = gr.Markdown("✅ Conectado a Airtable" if CONECTADO else "⚠️ Sin conexión Airtable")

        gr.Markdown("## 🚀 Publicar desde Airtable")
        btn_revisar = gr.Button("🔍 Revisar y publicar", variant="primary")
        msj_publicar = gr.Markdown()

        gr.Markdown("## 📤 Cargar o tomar estampillas")
        modo = gr.Radio(["📂 Galería", "📸 Tomar foto"], value="📸 Tomar foto", label="Elige cómo subir")
        
        # ✅ CÁMARA DIRECTA A TRASERA + 1080p
        camara = gr.Image(
            sources=["webcam"],
            type="pil",
            webcam_props={"facingMode": "environment", "width": {"ideal":1280}, "height": {"ideal":720}},
            label="📸 Cámara trasera (automática)",
            visible=True
        )
        galeria = gr.File(file_types=["image"], file_count="multiple", label="Selecciona imágenes", visible=False)

        btn_procesar = gr.Button("🔍 Analizar estampilla", variant="primary")
        salida_datos = gr.Markdown()
        precio_out = gr.Number(label="Precio GBP", value=0.50, minimum=0.50, step=0.05)
        desc_out = gr.Textbox(label="Descripción", lines=2)
        guardar_chk = gr.Checkbox(label="Guardar", value=True)
        publicar_chk = gr.Checkbox(label="Marcar para eBay", value=False)
        btn_guardar = gr.Button("📥 Guardar seleccionadas")
        btn_pub = gr.Button("📤 Publicar seleccionadas")
        msj_accion = gr.Markdown()

        gr.Markdown("## 📚 Catálogo")
        df_display = gr.Dataframe(value=cargar_base(), interactive=False)
        btn_descargar = gr.Button("📥 Descargar CSV")
        archivo_csv = gr.File(label="Descarga", visible=False)

        gr.Markdown("## 🌍 Buscar referencias")
        btn_buscar = gr.Button("Buscar casas de venta")
        salida_busqueda = gr.Markdown()

    # LÓGICA DE ACCESO
    def verificar_clave(c):
        if c == CLAVE_CORRECTA:
            return True, gr.update(visible=False), gr.update(visible=True), ""
        elif c:
            return False, gr.update(visible=True), gr.update(visible=False), "❌ Contraseña incorrecta"
        return False, gr.update(visible=True), gr.update(visible=False), ""

    btn_acceso.click(verificar_clave, clave_in, [auth, pantalla_acceso, pantalla_principal, msj_acceso])

    # CAMBIO DE MODO
    def cambiar_modo(m):
        return gr.update(visible=(m=="📸 Tomar foto")), gr.update(visible=(m=="📂 Galería"))
    modo.change(cambiar_modo, modo, [camara, galeria])

    # PROCESAR IMAGEN
    def procesar_imagen(img, archivos):
        lista_img = []
        if img: lista_img.append(img)
        if archivos: lista_img.extend([Image.open(f.name) for f in archivos])
        if not lista_img: return "", 0.5, "", ""
        salida = []
        reg_temp = []
        for idx, im in enumerate(lista_img, 1):
            b64 = reducir_imagen(im)
            datos = analizar_estampa(im, b64)
            for d in datos:
                pais = d.get("country","Desconocido")
                anio = d.get("year","-")
                val = d.get("face_value","-")
                est = d.get("condition","-")
                prec = d.get("sale_price_gbp",0.5)
                desc = d.get("description","")
                salida.append(f"**Imagen {idx}**\n**País:** {pais}\n**Año:** {anio}\n**Valor facial:** {val}\n**Estado:** {est}")
                try: prec = float(re.sub(r"[^0-9.]","",str(prec).strip().replace(",",".")))
                except: prec = 0.5
                reg_temp.append({"country":pais,"year":anio,"face_value":val,"condition":est,"sale_price_gbp":prec,"description":desc,"image_b64":b64})
        gr.session_state["reg_temp"] = reg_temp
        return "\n\n".join(salida), max(prec,0.5), desc, reg_temp

    btn_procesar.click(procesar_imagen, [camara, galeria], [salida_datos, precio_out, desc_out, msj_accion])

    # ACCIONES
    def accion_guardar(prec, desc, g, p):
        regs = gr.session_state.get("reg_temp", [])
        for r in regs:
            r["sale_price_gbp"] = prec
            r["description"] = desc
        if g: res = guardar_seleccionadas(regs)
        else: res = "Nada guardado"
        return res
    btn_guardar.click(accion_guardar, [precio_out, desc_out, guardar_chk, publicar_chk], msj_accion)

    def accion_publicar(prec, desc, g, p):
        regs = gr.session_state.get("reg_temp", [])
        for r in regs:
            r["sale_price_gbp"] = prec
            r["description"] = desc
        if p: res = publicar_seleccionadas(regs)
        else: res = "Nada publicado"
        return res
    btn_pub.click(accion_publicar, [precio_out, desc_out, guardar_chk, publicar_chk], msj_accion)

    def descargar_csv():
        df = cargar_base()
        nombre = f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv"
        ruta = f"/tmp/{nombre}"
        df.drop(columns=["image_b64"], errors="ignore").to_csv(ruta, index=False, encoding="utf-8")
        return gr.update(value=ruta, visible=True)
    btn_descargar.click(descargar_csv, outputs=archivo_csv)

    def buscar_referencias():
        res = llamar_mistral([{"role":"user","content":"Lista casas de subasta y tiendas serias de estampillas con sitio web y contacto, actualizado 2026."}],0.1,1200)
        return res
    btn_buscar.click(buscar_referencias, outputs=salida_busqueda)

    # Mostrar pantalla de acceso al inicio
    gr.on(lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[pantalla_acceso, pantalla_principal])

if __name__ == "__main__":
    demo.launch()