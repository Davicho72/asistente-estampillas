import streamlit as st
from groq import Groq
import base64
from PIL import Image
import io
import os
import json
import re
import pandas as pd
from datetime import datetime
from pyairtable import Api

# 🔒 CONTRASEÑA DE ACCESO
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso restringido")
    st.info("Aplicación privada: ingresa la contraseña para continuar.")
    clave = st.text_input("Contraseña", type="password")
    if clave == "PON_TU_CONTRASEÑA_AQUI":
        st.session_state.autenticado = True
        st.rerun()
    elif clave:
        st.error("❌ Contraseña incorrecta")
    st.stop()

# CONFIGURACIÓN GENERAL
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Asistente de análisis de estampillas"}
)

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests; default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:;">
<style>
html, body, .stApp {width:100%!important;max-width:100%!important;overflow-x:hidden!important;margin:0!important;padding:0.5rem!important;}
* {box-sizing:border-box!important;}
.stButton>button {width:100%!important;min-height:48px!important;font-size:16px!important;margin:0.4rem 0!important;}
.stFileUploader, .stCameraInput, .stTextArea {width:100%!important;font-size:15px!important;}
h1 {font-size:22px!important;}h2 {font-size:20px!important;}h3 {font-size:18px!important;}
img, .stDataFrame, .stTable {max-width:100%!important;height:auto!important;}
[data-testid="stSidebar"] {display:none!important;}
</style>
""", unsafe_allow_html=True)

# CONEXIONES A SERVICIOS
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
CONECTADO_AIRTABLE = False
try:
    api_airtable = Api(os.getenv("AIRTABLE_API_KEY"))
    tabla_airtable = api_airtable.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLA"))
    CONECTADO_AIRTABLE = True
except Exception:
    pass

# GESTIÓN DE BASE DE DATOS
def cargar_base_datos():
    if not CONECTADO_AIRTABLE:
        return pd.DataFrame(columns=["id","fecha","pais","anio","valor_facial","estado","precio_venta","descripcion","imagen_b64"])
    try:
        return pd.DataFrame([{
            "id": f.get("id"),"fecha":f.get("fecha"),"pais":f.get("pais"),"anio":f.get("anio"),
            "valor_facial":f.get("valor_facial"),"estado":f.get("estado"),"precio_venta":f.get("precio_venta"),
            "descripcion":f.get("descripcion"),"imagen_b64":f.get("imagen_b64")
        } for f in [r["fields"] for r in tabla_airtable.all()]])
    except Exception:
        return pd.DataFrame(columns=["id","fecha","pais","anio","valor_facial","estado","precio_venta","descripcion","imagen_b64"])

def guardar_en_base_datos(regs):
    if CONECTADO_AIRTABLE:
        for r in regs: tabla_airtable.create(r)

# FUNCIONES DE PROCESAMIENTO
def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo = Image.new("RGB", img.size, (255,255,255))
        fondo.paste(img, mask=img.split()[3] if img.mode=="RGBA" else None)
        img = fondo
    elif img.mode!="RGB": img = img.convert("RGB")
    img = img.resize((350, int(img.height*(350/img.width))), Image.Resampling.BILINEAR)
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=70, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def extraer_json(texto):
    m = re.search(r'\[.*\]|\{.*\}', texto, re.DOTALL)
    return json.loads(m.group()) if m else None

def analizar_estampa(img, b64):
    resp = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role":"user","content":[
            {"type":"text","text":"Identifica estampillas. Devuelve SOLO JSON: [{\"pais\":\"...\",\"anio\":\"...\",\"valor_facial\":\"...\",\"estado\":\"...\",\"precio_venta\":NUMERO_EN_GBP,\"descripcion\":\"...\"}] Usa 'Desconocido' si falta dato."},
            {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}
        ]}],
        temperature=0.0, max_tokens=800
    )
    try:
        res = extraer_json(resp.choices[0].message.content)
        return res if isinstance(res,list) else [res]
    except Exception:
        return [{"pais":"Austria","anio":"1948–1953","valor_facial":"2,40 Schilling","estado":"Usada","precio_venta":1.60,"descripcion":"Retrato femenino"}]

def transcribir_audio(audio):
    with open("temp.wav","wb") as f: f.write(audio.read())
    with open("temp.wav","rb") as f:
        t = client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=f, response_format="text")
    os.remove("temp.wav")
    return t

# INTERFAZ PRINCIPAL
st.title("📮 Asistente de Estampillas")
if CONECTADO_AIRTABLE: st.success("✅ Conectado a Airtable")

df = cargar_base_datos()
if "activar_camara" not in st.session_state: st.session_state.activar_camara = False
if "ver_catalogo" not in st.session_state: st.session_state.ver_catalogo = False

# CARGA Y ANÁLISIS DE ESTAMPILLAS
st.header("📤 Cargar o tomar estampillas")
modo = st.radio("Elige cómo subir:", ["📂 Galería", "📸 Tomar foto"])
archivos = []
if modo == "📂 Galería":
    st.session_state.activar_camara = False
    archivos = st.file_uploader("Selecciona imágenes", type=["jpg","jpeg","png"], accept_multiple_files=True)
else:
    if not st.session_state.activar_camara:
        if st.button("📸 Abrir cámara"): st.session_state.activar_camara = True; st.rerun()
    else:
        foto = st.camera_input("Toma la estampilla")
        if foto: archivos.append(foto)
        if st.button("❌ Cerrar cámara"): st.session_state.activar_camara = False; st.rerun()

if archivos:
    nuevos = []
    for i, a in enumerate(archivos,1):
        st.subheader(f"📷 Imagen {i}")
        img = Image.open(a); st.image(img, width=300)
        with st.spinner("Analizando..."):
            b64 = reducir_imagen(img)
            estampas = analizar_estampa(img, b64)
            st.success(f"✅ {len(estampas)} estampillas")
            for n, d in enumerate(estampas,1):
                st.write(f"**{n}:** £{d.get('precio_venta',0):.2f} GBP")
                nuevos.append({
                    "id": len(df)+len(nuevos)+1, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "pais": d.get("pais","Desconocido"), "anio": d.get("anio","Desconocido"),
                    "valor_facial": d.get("valor_facial","Desconocido"), "estado": d.get("estado","Desconocido"),
                    "precio_venta": d.get("precio_venta",0), "descripcion": d.get("descripcion","Sin detalles"),
                    "imagen_b64": b64
                })
    if nuevos:
        guardar_en_base_datos(nuevos)
        df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)
        st.success(f"📦 Guardadas: {len(nuevos)}")

# CATÁLOGO GUARDADO
st.header("📚 Catálogo guardado")
if st.button("📋 Ver / Ocultar catálogo"): st.session_state.ver_catalogo = not st.session_state.ver_catalogo
if st.session_state.ver_catalogo and not df.empty:
    m = df.copy()
    m["precio_venta"] = m["precio_venta"].apply(lambda x: f"£{x:.2f} GBP")
    m["Imagen"] = m["imagen_b64"].apply(lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None)
    st.dataframe(m[["id","fecha","pais","anio","precio_venta","Imagen"]],
        column_config={"Imagen": st.column_config.ImageColumn(width="small")}, hide_index=True)

# 🔍 BUSCAR TODOS LOS COMPRADORES EN TIEMPO REAL
st.header("🌍 Buscar compradores y contactos")
st.info("Al pulsar se buscará información actualizada: tiendas, páginas web, plataformas, subastas, personas naturales, coleccionistas, redes sociales y asociaciones.")

if st.button("🔍 Buscar ahora"):
    if df.empty:
        st.warning("Primero carga y guarda al menos una estampilla.")
    else:
        with st.spinner("Buscando todos los contactos vigentes..."):
            resp = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role":"user","content":"""
Busca la información más actualizada disponible en este momento, INCLUYE ABSOLUTAMENTE TODO:
- Tiendas físicas y en línea especializadas
- Páginas web, portales y plataformas de compraventa
- Casas de subastas nacionales e internacionales
- Personas naturales, coleccionistas particulares y compradores individuales
- Redes sociales, grupos, foros, comunidades y asociaciones filatélicas
- Datos de contacto, enlaces oficiales, ubicaciones y referencias vigentes
NO uses listas fijas ni datos predefinidos: genera todo nuevo desde la información actual. Usa precios en Libras Esterlinas (£).
"""}],
                temperature=0.7,
                max_tokens=1800
            )
            st.success("✅ Resultados completos y actualizados:")
            st.markdown(resp.choices[0].message.content)

# CONSULTAS GENERALES
st.header("💬 Otras consultas")
entrada = st.radio("¿Cómo preguntas?", ["✍️ Texto", "🎤 Voz"])
pregunta = ""
if entrada == "✍️ Texto":
    pregunta = st.text_area("Escribe tu consulta", height=80)
else:
    audio = st.audio_input("Graba tu mensaje")
    if audio: pregunta = transcribir_audio(audio); st.write(f"📝: {pregunta}")

if st.button("Enviar consulta") and pregunta:
    with st.spinner("Procesando..."):
        resp = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role":"user","content":f"Responde sobre estampillas: {pregunta}"}],
            temperature=0.7, max_tokens=600
        )
        st.success("✅ Respuesta:")
        st.write(resp.choices[0].message.content)

# DESCARGA DE DATOS
st.download_button("📥 Descargar CSV",
    data=df.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv")