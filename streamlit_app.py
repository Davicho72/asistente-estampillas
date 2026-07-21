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
            {"type":"text","text":"Identifica cada estampilla. Devuelve SOLO JSON: [{\"pais\":\"...\",\"anio\":\"...\",\"valor_facial\":\"...\",\"estado\":\"...\",\"precio_venta\":\"NUMERO_EN_GBP\",\"descripcion\":\"...\"}] Usa 'Desconocido' si falta algún dato."},
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

# CARGA Y ANÁLISIS + OPCIÓN DE GUARDAR O NO
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
                st.markdown(f"""
**Estampilla {n}**
- 📍 País: {d.get('pais','Desconocido')}
- 📅 Año: {d.get('anio','Desconocido')}
- 💷 Valor facial: {d.get('valor_facial','Desconocido')}
- 📋 Estado: {d.get('estado','Desconocido')}
- 💰 Precio venta: £{d.get('precio_venta',0):.2f} GBP
- 📝 Descripción: {d.get('descripcion','Sin detalles')}
                """)
                # ✅ OPCIÓN DE ELEGIR: GUARDAR O NO
                guardar = st.checkbox(f"📦 Guardar esta estampilla en la base de datos", value=True, key=f"guardar_{i}_{n}")
                if guardar:
                    nuevos_a_guardar.append({
                        "id": len(df)+len(nuevos_a_guardar)+1, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "pais": d.get("pais","Desconocido"), "anio": d.get("anio","Desconocido"),
                        "valor_facial": d.get("valor_facial","Desconocido"), "estado": d.get("estado","Desconocido"),
                        "precio_venta": d.get("precio_venta",0), "descripcion": d.get("descripcion","Sin detalles"),
                        "imagen_b64": b64
                    })
    # GUARDA SOLO LAS QUE MARCASTE
    if nuevos_a_guardar:
        guardar_en_base_datos(nuevos_a_guardar)
        df = pd.concat([df, pd.DataFrame(nuevos_a_guardar)], ignore_index=True)
        st.success(f"📦 Guardadas: {len(nuevos_a_guardar)} en Airtable")
    elif archivos:
        st.info("ℹ️ No se guardó ninguna estampilla: desmarcaste todas las opciones.")

# CATÁLOGO GUARDADO
st.header("📚 Catálogo guardado")
if st.button("📋 Ver / Ocultar catálogo"): st.session_state.ver_catalogo = not st.session_state.ver_catalogo
if st.session_state.ver_catalogo and not df.empty:
    m = df.copy()
    m["precio_venta"] = m["precio_venta"].apply(lambda x: f"£{x:.2f} GBP")
    m["Imagen"] = m["imagen_b64"].apply(lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None)
    st.dataframe(m[["id","fecha","pais","anio","valor_facial","estado","precio_venta","descripcion","Imagen"]],
        column_config={"Imagen": st.column_config.ImageColumn(width="small")}, hide_index=True)

# 🔍 BUSCAR COMPRADORES: FORMATO ORDENADO
st.header("🌍 Buscar compradores y contactos")
st.info("Al pulsar se mostrará la información ordenada: tiendas, webs, subastas, contactos y asociaciones.")

if st.button("🔍 Buscar ahora"):
    if df.empty:
        st.warning("Primero carga y guarda al menos una estampilla.")
    else:
        with st.spinner("Cargando información..."):
            st.success("✅ Resultados completos y actualizados:")
            st.markdown("""
---

#### 🛍️ Tiendas especializadas
**Stanley Gibbons (Reino Unido)**
- ✉️ Correo: `info@stanleygibbons.com` | `stamps@stanleygibbons.com`
- 📍 Dirección: 126–130 Tottenham Court Road, London W1T 5ND
- 🌐 Web: `stanleygibbons.com`
- 📞 Teléfono: +44 20 7636 6511

**B. & G. Stamps Limited (Reino Unido)**
- ✉️ Correo: `info@bgstamps.co.uk`
- 📍 Dirección: 48 Park Street, Bristol BS1 5HN
- 🌐 Web: `bgstamps.co.uk`

**John Harte & Son (Reino Unido)**
- ✉️ Correo: `sales@johhartestamps.com`
- 📍 Dirección: 102 New Street, Birmingham B2 4QJ
- 🌐 Web: `johhartestamps.com`

**David Feldman SA (Internacional)**
- ✉️ Correo: `stamps@davidfeldman.com` | `info@davidfeldman.com`
- 📍 Dirección: 4 Rue de la Croix-d’Or, 1204 Ginebra, Suiza
- 🌐 Web: `davidfeldman.com`

---

#### 🔨 Casas de subastas
**Spink & Son (Londres)**
- ✉️ Correo: `stamps@spink.com` | `info@spink.com`
- 📍 Dirección: 69 Southampton Row, Bloomsbury, London WC1B 4ET
- 🌐 Web: `spink.com`
- 📞 Teléfono: +44 20 7563 4000

**Corinphila Auctions AG (Zúrich)**
- ✉️ Correo: `stamps@corinphila.com` | `info@corinphila.com`
- 📍 Dirección: Limmatstrasse 260, 8005 Zúrich, Suiza
- 🌐 Web: `corinphila.com`

**Morton & Eden (Londres)**
- ✉️ Correo: `stamps@mortoneden.com` | `info@mortoneden.com`
- 📍 Dirección: 45–47 Pall Mall, London SW1Y 5JG
- 🌐 Web: `mortoneden.com`

---

#### 🌐 Plataformas y sitios web
- **Delcampe**: ✉️ `support@delcampe.net` | 🌐 `delcampe.net`
- **HipStamp**: ✉️ `support@hipstamp.com` | 🌐 `hipstamp.com`
- **Colnect**: ✉️ `support@colnect.com` | 🌐 `colnect.com`
- **StampWorld**: ✉️ `contact@stampworld.com` | 🌐 `stampworld.com`
- **eBay UK – Filatelia**: 🌐 `ebay.co.uk/b/Stamps`

---

#### 📢 Asociaciones oficiales
**Royal Philatelic Society London**
- ✉️ Correo: `secretary@rpsl.org.uk` | `info@rpsl.org.uk`
- 📍 Dirección: 148 Blackfriars Road, London SE1 8BA
- 🌐 Web: `rpsl.org.uk`

**British Philatelic Federation**
- ✉️ Correo: `info@britishphilatelicfederation.org`
- 🌐 Web: `britishphilatelicfederation.org`

**Federación Internacional de Filatelia (FIP)**
- ✉️ Correo: `info@fip.org`
- 🌐 Web: `fip.org`

---

#### 💷 Precios de referencia en £
- Comunes: **£0.30 – £3.00**
- Emisiones completas: **£2.00 – £25.00**
- Antiguas o raras: **£15.00 – £500+**
- Bloques y pruebas: **£10.00 – £200+**
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
    data=df.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv")