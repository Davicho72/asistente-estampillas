import streamlit as st
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
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso restringido")
    st.info("Aplicación privada: ingresa la contraseña para continuar.")
    clave = st.text_input("Contraseña", type="password")
    if clave == "AhoraNorbury2026":
        st.session_state.autenticado = True
        st.rerun()
    elif clave:
        st.error("❌ Contraseña incorrecta")
    st.stop()

# 🔧 LECTURA DE CLAVES
EBAY_APP_ID = st.secrets.get("EBAY_CLIENT_ID", "")
EBAY_CERT_ID = st.secrets.get("EBAY_CLIENT_SECRET", "")
EBAY_DEV_ID = st.secrets.get("EBAY_DEV_ID", "")
EBAY_REFRESH_TOKEN = st.secrets.get("EBAY_REFRESH_TOKEN", "")

# CONFIGURACIÓN GENERAL
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Asistente personal para tu colección de estampillas"}
)

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests; default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:;">

<link rel="icon" type="image/png" href="PON_EL_ENLACE_DE_TU_ICONO_AQUI">
<link rel="apple-touch-icon" href="PON_EL_ENLACE_DE_TU_ICONO_AQUI">
<meta name="theme-color" content="#2c3e50">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="description" content="Gestiona, analiza y vende tu colección de estampillas">

<style>
html, body, .stApp {width:100%!important;max-width:100%!important;overflow-x:hidden!important;margin:0!important;padding:0.5rem!important;}
* {box-sizing:border-box!important;}
.stButton>button {width:100%!important;min-height:48px!important;font-size:16px!important;margin:0.4rem 0!important;}
.stFileUploader, .stCameraInput, .stTextArea, .stCheckbox {width:100%!important;font-size:15px!important;}
h1 {font-size:22px!important;}h2 {font-size:20px!important;}h3 {font-size:18px!important;}
img, .stDataFrame, .stTable {max-width:100%!important;height:auto!important;}
[data-testid="stSidebar"] {display:none!important;}
</style>
""", unsafe_allow_html=True)

# 🔧 API MISTRAL
MISTRAL_API_KEY = st.secrets.get("MISTRAL_API_KEY") or os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"

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

# 🔧 CONFIGURACIÓN Y FUNCIÓN DE TOKEN EBAY
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
            st.error(f"Error al generar token: {respuesta.status_code} - {respuesta.text[:300]}")
            return None
        return respuesta.json()["access_token"]
    except Exception as e:
        st.error(f"Error de conexión al generar token: {str(e)}")
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

    titulo = f"Estampilla {datos['country']} {datos['year'] or ''} - {datos['condition']}"[:80]
    descripcion = f"""Estampilla auténtica y original.
País: {datos['country']}
Año: {datos['year'] or 'No especificado'}
Valor facial: {datos['face_value'] or 'No especificado'}
Estado: {datos['condition'] or 'No especificado'}
Detalles: {datos['description'] or 'Sin detalles adicionales'}

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
            return False, f"Error HTTP {resp.status_code}: {resp.text[:250]}"
        ns = {"ebay": "urn:ebay:apis:eBLBaseComponents"}
        raiz = ET.fromstring(resp.text)
        errores = raiz.findall("ebay:Errors", ns)
        if errores:
            mensajes = []
            for err in errores:
                msg = err.find("ebay:LongMessage", ns)
                cod = err.find("ebay:ErrorCode", ns)
                if msg is not None:
                    mensajes.append(f"{cod.text if cod else ''} → {msg.text}")
            return False, " | ".join(mensajes[:2])
        id_anuncio = raiz.find("ebay:ItemID", ns)
        if id_anuncio is not None and id_anuncio.text:
            return True, f"✅ Publicado | ID: {id_anuncio.text}"
        return True, "✅ Publicado correctamente"
    except Exception as e:
        return False, f"Fallo: {str(e)}"

# CONEXIÓN A AIRTABLE
CONECTADO_AIRTABLE = False
try:
    api_airtable = Api(st.secrets.get("AIRTABLE_API_KEY") or os.getenv("AIRTABLE_API_KEY"))
    tabla_airtable = api_airtable.table(
        st.secrets.get("AIRTABLE_BASE_ID") or os.getenv("AIRTABLE_BASE_ID"),
        st.secrets.get("AIRTABLE_TABLA") or os.getenv("AIRTABLE_TABLA")
    )
    CONECTADO_AIRTABLE = True
except Exception:
    pass

def publicar_desde_airtable():
    if not CONECTADO_AIRTABLE:
        st.warning("Sin conexión a Airtable")
        return
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        st.warning("Completa las claves de eBay primero")
        return
    st.info("Revisando registros...")
    registros = tabla_airtable.all()
    publicados = 0
    omitidos = 0
    errores = []
    for reg in registros:
        campos = reg["fields"]
        if not bool(campos.get(CAMPO_PUBLICAR, False)):
            omitidos +=1
            continue
        datos = {
            "country": campos.get("country", "Desconocido"),
            "year": campos.get("year", ""),
            "face_value": campos.get("Face_value", ""),
            "condition": campos.get("condition", ""),
            "sale_price_gbp": campos.get("sale_price_gbp", "0.5"),
            "description": campos.get("description", "")
        }
        ok, res = publicar_en_ebay(datos)
        if ok:
            st.success(f"✅ Publicado — {res}")
            tabla_airtable.update(reg["id"], {CAMPO_PUBLICAR: False, "ID eBay": res})
            publicados +=1
        else:
            errores.append(f"Registro {reg['id']}: {res}")
    st.info(f"Revisados:{len(registros)} | Publicados:{publicados} | Omitidos:{omitidos}")
    for e in errores: st.warning(e)

def cargar_base_datos():
    if not CONECTADO_AIRTABLE:
        return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","Publicar en eBay","ID eBay","image_b64"])
    try:
        return pd.DataFrame([{
            "id":f.get("id"),"saved_date":f.get("saved_date"),"country":f.get("country"),"year":f.get("year"),
            "Face_value":f.get("Face_value"),"condition":f.get("condition"),"sale_price_gbp":f.get("sale_price_gbp"),
            "description":f.get("description"),"Publicar en eBay":bool(f.get("Publicar en eBay",False)),"ID eBay":f.get("ID eBay",""),"image_b64":f.get("image_b64")
        } for f in [r["fields"] for r in tabla_airtable.all()]])
    except Exception:
        return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","Publicar en eBay","ID eBay","image_b64"])

def guardar_seleccionadas(lista):
    if not CONECTADO_AIRTABLE or not lista:
        st.warning("Sin conexión o sin datos")
        return
    try:
        guardados=0
        for r in lista:
            fecha=datetime.now().isoformat(timespec="seconds")+"Z"
            try:
                precio_texto = str(r.get("sale_price_gbp", "0.5")).strip().replace(",", ".")
                precio_solo_numeros = re.sub(r"[^0-9.]", "", precio_texto)
                precio = float(precio_solo_numeros) if precio_solo_numeros else 0.5
            except: precio=0.5

            # Limpieza segura del año
            anio_bruto = r.get("year", "")
            anio_limpio = str(anio_bruto).strip() if anio_bruto not in (None, "", "-") else ""

            # 1. Creamos registro primero
            registro = tabla_airtable.create({
                "saved_date":fecha,
                "country":r["country"],
                "year": anio_limpio,
                "Face_value":r["face_value"],
                "condition":r["condition"],
                "sale_price_gbp":precio,
                "description":r["description"],
                "Publicar en eBay":False,
                "image_b64":r["image_b64"]
            }, typecast=True)

            # 2. Subimos imagen al campo Adjunto "Imagen"
            img_b64 = r.get("image_b64")
            if img_b64:
                try:
                    datos_bin = base64.b64decode(img_b64)
                    tabla_airtable.upload_attachment(
                        record_id=registro["id"],
                        field="Imagen",
                        filename="estampilla.jpg",
                        content=datos_bin,
                        content_type="image/jpeg"
                    )
                except Exception as e:
                    st.warning(f"Imagen guardada en código, no en vista: {str(e)}")

            guardados+=1
        st.success(f"Guardadas:{guardados}")
    except Exception as e: st.error(f"Error:{str(e)}")

def publicar_seleccionadas(lista):
    if not EBAY_APP_ID or not EBAY_CERT_ID or not lista:
        st.warning("Faltan claves o datos")
        return
    publicadas=0
    for r in lista:
        anio_bruto = r.get("year", "")
        anio_limpio = str(anio_bruto).strip() if anio_bruto not in (None, "", "-") else ""

        datos={
            "country":r.get("country","Desconocido"),
            "year": anio_limpio,
            "face_value":r.get("face_value",""),
            "condition":r.get("condition",""),
            "sale_price_gbp":r.get("sale_price_gbp","0.5"),
            "description":r.get("description","")
        }
        ok,res=publicar_en_ebay(datos)
        if ok:
            st.success(f"✅ {res}")
            if CONECTADO_AIRTABLE:
                fecha=datetime.now().isoformat(timespec="seconds")+"Z"
                try:
                    precio_texto = str(r.get("sale_price_gbp", "0.5")).strip().replace(",", ".")
                    precio_solo_numeros = re.sub(r"[^0-9.]", "", precio_texto)
                    precio = float(precio_solo_numeros) if precio_solo_numeros else 0.5
                except: precio=0.5
                tabla_airtable.create({
                    "saved_date":fecha,
                    "country":datos["country"],
                    "year": anio_limpio,
                    "Face_value":datos["face_value"],
                    "condition":datos["condition"],
                    "sale_price_gbp":precio,
                    "description":datos["description"],
                    "Publicar en eBay":False,
                    "ID eBay":res,
                    "image_b64":r["image_b64"]
                }, typecast=True)
            publicadas+=1
        else: st.warning(f"No publicado:{res}")
    st.info(f"Publicadas:{publicadas}")

def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo=Image.new("RGB",img.size,(255,255,255))
        fondo.paste(img,mask=img.split()[3] if img.mode=="RGBA" else None)
        img=fondo
    elif img.mode!="RGB": img=img.convert("RGB")
    img=img.resize((350,int(img.height*(350/img.width))),Image.Resampling.BILINEAR)
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
        except: time.sleep(2)
    return [{"country":"Desconocido","year":"-","face_value":"-","condition":"-","sale_price_gbp":0.50,"description":"Error análisis"}]

# INTERFAZ PRINCIPAL
st.title("📮 Asistente de Estampillas")
if CONECTADO_AIRTABLE: st.success("Conectado a Airtable")
df=cargar_base_datos()
if "activar_camara"not in st.session_state: st.session_state.activar_camara=False
if "ver_catalogo"not in st.session_state: st.session_state.ver_catalogo=False

st.header("🚀 Publicar desde Airtable")
if st.button("🔍 Revisar y publicar"): publicar_desde_airtable()

st.header("📤 Cargar o tomar estampillas")
modo = st.radio("Elige cómo subir:", ["📂 Galería", "📸 Tomar foto"])
archivos = []
if modo == "📂 Galería":
    st.session_state.activar_camara = False
    archivos = st.file_uploader("Selecciona imágenes", type=["jpg","jpeg","png"], accept_multiple_files=True)
else:
    if not st.session_state.activar_camara:
        if st.button("📸 Abrir cámara"):
            st.session_state.activar_camara = True
            st.rerun()
    else:
        foto = st.camera_input("Toma la estampilla")
        if foto:
            archivos.append(foto)
        if st.button("❌ Cerrar cámara"):
            st.session_state.activar_camara = False
            st.rerun()

if archivos:
    seleccionadas_guardar = []
    seleccionadas_publicar = []
    for i, a in enumerate(archivos,1):
        st.subheader(f"📷 Imagen {i}")
        img = Image.open(a)
        st.image(img, width=300)
        with st.spinner("Analizando datos..."):
            b64 = reducir_imagen(img)
            estampas = analizar_estampa(img, b64)
            st.success(f"{len(estampas)} estampillas detectadas:")
            for n, d in enumerate(estampas,1):
                st.subheader(f"Estampilla {n}")
                pais = d.get("country") or d.get("Country") or "Desconocido"
                anio = d.get("year") or d.get("Year") or "Desconocido"
                valor = d.get("face_value") or d.get("Face_value") or "Desconocido"
                estado = d.get("condition") or d.get("Condition") or "Desconocido"
                precio = d.get("sale_price_gbp") or d.get("Sale_price_gbp") or 0.5
                desc = d.get("description") or d.get("Description") or "Sin detalles"

                try:
                    precio_texto = str(precio).strip().replace(",", ".")
                    precio_solo_numeros = re.sub(r"[^0-9.]", "", precio_texto)
                    precio_num = float(precio_solo_numeros) if precio_solo_numeros else 0.5
                except:
                    precio_num = 0.5

                st.write(f"- País: {pais}")
                st.write(f"- Año: {anio}")
                st.write(f"- Valor facial: {valor}")
                st.write(f"- Estado: {estado}")
                precio_num = st.number_input(
                    "Precio de venta en GBP",
                    value=max(precio_num, 0.5),
                    min_value=0.5,
                    step=0.05,
                    format="%.2f",
                    key=f"precio_{i}_{n}"
                )
                st.write(f"- Descripción: {desc}")
                desc = st.text_area("Editar descripción", desc, key=f"desc_{i}_{n}")

                guardar = st.checkbox(f"Guardar en Airtable", value=True, key=f"guardar_{i}_{n}")
                publicar = st.checkbox(f"Marcar para eBay", value=False, key=f"publicar_{i}_{n}")

                datos_estampa = {
                    "country": pais, "year": anio, "face_value": valor,
                    "condition": estado, "sale_price_gbp": precio_num,
                    "description": desc, "publicar_en_ebay": publicar, "image_b64": b64
                }
                if guardar:
                    seleccionadas_guardar.append(datos_estampa)
                if publicar:
                    seleccionadas_publicar.append(datos_estampa)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Guardar seleccionadas en Airtable"):
            guardar_seleccionadas(seleccionadas_guardar)
            df = cargar_base_datos()
    with col2:
        if st.button("📤 Publicar seleccionadas en eBay"):
            publicar_seleccionadas(seleccionadas_publicar)
            df = cargar_base_datos()

st.header("📚 Catálogo guardado")
if st.button("Ver / Ocultar catálogo"):
    st.session_state.ver_catalogo = not st.session_state.ver_catalogo
if st.session_state.ver_catalogo and not df.empty:
    m = df.copy()
    m["sale_price_gbp"] = m["sale_price_gbp"].apply(lambda x: f"£{x:.2f} GBP")
    m["Publicar en eBay"] = m["Publicar en eBay"].apply(lambda x: "✅ Sí" if x else "❌ No")
    m["Imagen"] = m["image_b64"].apply(lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None)
    st.dataframe(m[["id","saved_date","country","year","Face_value","condition","sale_price_gbp","Publicar en eBay","ID eBay","description","Imagen"]],
        column_config={"Imagen": st.column_config.ImageColumn(width="small")}, hide_index=True)

st.header("🌍 Buscar compradores y contactos")
if st.button("Buscar ahora"):
    if df.empty:
        st.warning("Primero carga y guarda al menos una estampilla.")
    else:
        with st.spinner("Obteniendo datos..."):
            try:
                respuesta = llamar_mistral([{
                    "role":"user",
                    "content":"Muestra SOLO datos exactos y completos de casas de subastas, tiendas y sitios de venta de estampillas: nombre oficial completo, página web oficial, todos los correos electrónicos con su uso específico, dirección postal completa, exactamente a quién le vendes tus estampillas y cómo comunicarte con ellos. Sin explicaciones innecesarias, sin términos vagos, solo información concreta actualizada al 2026."
                }], temperatura=0.1, max_tokens=1500)
                st.success("Datos exactos obtenidos:")
                st.markdown(respuesta)
            except Exception as e:
                st.error(f"No se pudo consultar: {str(e)}")

st.header("💬 Otras consultas")
entrada = st.radio("¿Cómo preguntas?", ["✍️ Texto", "🎤 Voz"])
pregunta = ""
if entrada == "✍️ Texto":
    pregunta = st.text_area("Escribe tu consulta", height=80)
else:
    audio = st.audio_input("Graba tu mensaje")
    if audio:
        pregunta = transcribir_audio(audio)
        st.write(f"Transcripción: {pregunta}")

if st.button("Enviar consulta") and pregunta:
    with st.spinner("Procesando..."):
        respuesta = llamar_mistral([{"role":"user","content":f"Responde sobre estampillas: {pregunta}"}], temperatura=0.7, max_tokens=600)
        st.success("Respuesta:")
        st.write(respuesta)

st.download_button("📥 Descargar CSV",
    data=df.drop(columns=["image_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv")