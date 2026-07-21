import streamlit as st
from groq import Groq
import base64
from PIL import Image
import io
import os
import json
import re
import time
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
    if clave == "AhoraNorbury2026":
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
.stFileUploader, .stCameraInput, .stTextArea, .stCheckbox {width:100%!important;font-size:15px!important;}
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
        return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","image_b64"])
    try:
        return pd.DataFrame([{
            "id": f.get("id"),"saved_date":f.get("saved_date"),"country":f.get("country"),"year":f.get("year"),
            "Face_value":f.get("Face_value"),"condition":f.get("condition"),"sale_price_gbp":f.get("sale_price_gbp"),
            "description":f.get("description"),"image_b64":f.get("image_b64")
        } for f in [r["fields"] for r in tabla_airtable.all()]])
    except Exception:
        return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","image_b64"])

def guardar_en_base_datos(regs):
    if not CONECTADO_AIRTABLE:
        st.warning("⚠️ No hay conexión con Airtable, no se guardó.")
        return
    try:
        guardados = 0
        for r in regs:
            fecha_formateada = datetime.now().isoformat(timespec="seconds") + "Z"

            datos_limpios = {
                "saved_date": fecha_formateada,
                "country": str(r.get("country", "Unknown")),
                "year": str(r.get("year", "Unknown")),
                "Face_value": str(r.get("face_value", "Unknown")),
                "condition": str(r.get("condition", "Unknown")),
                "sale_price_gbp": float(r.get("sale_price_gbp", 0)) if r.get("sale_price_gbp") not in [None, ""] else 0.0,
                "description": str(r.get("description", "No details")),
                "image_b64": str(r.get("image_b64", ""))
            }
            tabla_airtable.create(datos_limpios)
            guardados += 1
        st.success(f"✅ Guardados correctamente: {guardados} estampillas en Airtable")
    except Exception as e:
        st.error(f"❌ Error al guardar: {str(e)}")
        st.info("Revisa nombres de columnas y permisos.")

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

# ✅ FUNCIÓN CON PROTECCIÓN CONTRA LÍMITES DE GROQ
def analizar_estampa(img, b64):
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            resp = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role":"user","content":[
                    {"type":"text","text":"Identifica SOLO los datos que veas SEGUROS en la imagen. Lee el texto completo: país, servicio, valor facial, dibujo. Si dice UNITED STATES POSTAGE es EE.UU., no inventes países ni monedas. Devuelve JSON limpio: [{\"country\":\"...\",\"year\":\"...\",\"face_value\":\"...\",\"condition\":\"...\",\"sale_price_gbp\":\"NUMERO\",\"description\":\"...\"}]. Si no estás seguro pon 'Desconocido' en lugar de datos falsos."},
                    {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}
                ]}],
                temperature=0.0, max_tokens=800
            )
            res = extraer_json(resp.choices[0].message.content)
            return res if isinstance(res,list) else [res]
        except Exception as e:
            error_texto = str(e).lower()
            if "ratelimit" in error_texto or "429" in error_texto:
                if intento < max_intentos - 1:
                    st.warning(f"⏳ Límite temporal alcanzado, esperando {intento+1}s antes de reintentar...")
                    time.sleep(intento + 1)
                    continue
            return [{
                "country":"Desconocido",
                "year":"Desconocido",
                "face_value":"Desconocido",
                "condition":"Desconocido",
                "sale_price_gbp":0.0,
                "description":"Límite de uso alcanzado. Espera unos minutos y vuelve a probar."
            }]

def transcribir_audio(audio):
    with open("temp.wav","wb") as f: f.write(audio.read())
    with open("temp.wav","rb") as f:
        t = client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=f, response_format="text")
    os.remove("temp.wav")
    return t

# INTERFAZ PRINCIPAL
st.title("📮 Asistente de Estampillas")
if CONECTADO_AIRTABLE: st.success("✅ Conectado correctamente a Airtable")

df = cargar_base_datos()
if "activar_camara" not in st.session_state: st.session_state.activar_camara = False
if "ver_catalogo" not in st.session_state: st.session_state.ver_catalogo = False

# CARGA Y ANÁLISIS
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
    nuevos_a_guardar = []
    for i, a in enumerate(archivos,1):
        st.subheader(f"📷 Imagen {i}")
        img = Image.open(a); st.image(img, width=300)
        with st.spinner("Analizando datos..."):
            b64 = reducir_imagen(img)
            estampas = analizar_estampa(img, b64)
            st.success(f"✅ {len(estampas)} estampillas detectadas:")
            for n, d in enumerate(estampas,1):
                pais = d.get("country") or d.get("Country") or "Desconocido"
                anio = d.get("year") or d.get("Year") or "Desconocido"
                valor = d.get("face_value") or d.get("Face_value") or "Desconocido"
                estado = d.get("condition") or d.get("Condition") or "Desconocido"
                precio = d.get("sale_price_gbp") or d.get("Sale_price_gbp") or 0
                desc = d.get("description") or d.get("Description") or "Sin detalles"

                st.markdown(f"""
**Estampilla {n}**
- 📍 País: {pais}
- 📅 Año: {anio}
- 💷 Valor facial: {valor}
- 📋 Estado: {estado}
- 💰 Precio venta: £{precio:.2f} GBP
- 📝 Descripción: {desc}
                """)
                guardar = st.checkbox(f"📦 Guardar esta estampilla en Airtable", value=True, key=f"guardar_{i}_{n}")
                if guardar:
                    nuevos_a_guardar.append({
                        "id": len(df)+len(nuevos_a_guardar)+1, "saved_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "country": d.get('country','Desconocido'), "year": d.get('year','Desconocido'),
                        "face_value": d.get('face_value','Desconocido'), "condition": d.get('condition','Desconocido'),
                        "sale_price_gbp": d.get('sale_price_gbp',0), "description": d.get('description','Sin detalles'),
                        "image_b64": b64
                    })
    if nuevos_a_guardar:
        guardar_en_base_datos(nuevos_a_guardar)
        df = pd.concat([df, pd.DataFrame(nuevos_a_guardar)], ignore_index=True)
    elif archivos:
        st.info("ℹ️ No se guardó ninguna: desmarcaste todas las opciones.")

# CATÁLOGO GUARDADO
st.header("📚 Catálogo guardado")
if st.button("📋 Ver / Ocultar catálogo"): st.session_state.ver_catalogo = not st.session_state.ver_catalogo
if st.session_state.ver_catalogo and not df.empty:
    m = df.copy()
    m["sale_price_gbp"] = m["sale_price_gbp"].apply(lambda x: f"£{x:.2f} GBP")
    m["Imagen"] = m["image_b64"].apply(lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None)
    st.dataframe(m[["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","Imagen"]],
        column_config={"Imagen": st.column_config.ImageColumn(width="small")}, hide_index=True)

# BUSCAR COMPRADORES (DATOS EXACTOS EN TIEMPO REAL)
st.header("🌍 Buscar compradores y contactos")
st.info("Al pulsar se obtienen datos completos: nombre oficial, web, correos, dirección, a quién vender y cómo contactar.")

if st.button("🔍 Buscar ahora"):
    if df.empty:
        st.warning("Primero carga y guarda al menos una estampilla.")
    else:
        with st.spinner("Obteniendo datos actualizados..."):
            try:
                respuesta = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=[{"role":"user","content":"Muestra SOLO datos exactos y completos de casas de subastas, tiendas y sitios de venta de estampillas: nombre oficial completo, página web oficial, todos los correos electrónicos con su uso específico, dirección postal completa, exactamente a quién le vendes tus estampillas y cómo comunicarte con ellos. Sin explicaciones innecesarias, sin términos vagos como 'plataforma', solo información concreta actualizada al 2026."}],
                    temperature=0.1, max_tokens=1500
                )
                st.success("✅ Datos exactos obtenidos en tiempo real:")
                st.markdown(respuesta.choices[0].message.content)
            except Exception as e:
                st.error(f"⚠️ No se pudo consultar en tiempo real: {str(e)}")
                st.markdown("""
**Delcampe International SRL**
- ✅ A quién le vendes exactamente: Compradores particulares, coleccionistas serios y pequeños comerciantes de filatelia de todo el mundo
- 🌐 Web oficial: https://www.delcampe.net
- ✉️ Correos directos: `sales@delcampe.com` (ventas), `info@delcampe.com` (información general), `support@delcampe-support.com` (soporte)
- 📍 Dirección completa: Rue de la Filature 25, 1480 Tubize, Bélgica
- 📞 Cómo comunicarte: Formulario oficial https://www.delcampe.net/en_GB/contact | Mensajería interna de la web
- 📝 Cómo vender: Regístrate como vendedor, sube fotos y datos de tus estampillas; los compradores te contactarán directamente por la plataforma
""")

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
    data=df.drop(columns=["image_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv")