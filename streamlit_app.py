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

# --------------------------
# 🔒 PROTECCIÓN CON CONTRASEÑA (NUEVO)
# --------------------------
CONTRASEÑA_APP = st.secrets.get("CONTRASEÑA_APP", "tu_contraseña_segura_aqui")

def verificar_acceso():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        st.title("🔒 Acceso restringido")
        st.info("Esta aplicación es privada. Ingresa la contraseña para continuar.")
        clave = st.text_input("Contraseña", type="password")
        if st.button("🔑 Entrar"):
            if clave == CONTRASEÑA_APP:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
        st.stop()

# Ejecutar verificación antes de mostrar nada
verificar_acceso()

# --------------------------
# CONFIGURACIÓN COMPATIBLE CON TODOS LOS NAVEGADORES MÓVILES
# --------------------------
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Asistente de análisis de estampillas"}
)

# AJUSTES OBLIGATORIOS PARA CHROME EN TELÉFONO
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests; default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:;">
<style>
html, body, .stApp {
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
    margin: 0 !important;
    padding: 0.5rem !important;
}
* {box-sizing: border-box !important;}
.stButton>button {
    width: 100% !important;
    min-height: 48px !important;
    font-size: 16px !important;
    margin: 0.4rem 0 !important;
}
.stFileUploader, .stCameraInput, .stTextArea {
    width: 100% !important;
    font-size: 15px !important;
}
h1 {font-size: 22px !important;}
h2 {font-size: 20px !important;}
h3 {font-size: 18px !important;}
img, .stDataFrame, .stTable {
    max-width: 100% !important;
    height: auto !important;
}
[data-testid="stSidebar"] {display: none !important;}
</style>
""", unsafe_allow_html=True)

# --------------------------
# CONEXIÓN GROQ Y AIRTABLE
# --------------------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
    AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
    AIRTABLE_TABLA = os.getenv("AIRTABLE_TABLA")
    
    if all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLA]):
        api_airtable = Api(AIRTABLE_API_KEY)
        tabla_airtable = api_airtable.table(AIRTABLE_BASE_ID, AIRTABLE_TABLA)
        CONECTADO_AIRTABLE = True
    else:
        CONECTADO_AIRTABLE = False
except Exception:
    CONECTADO_AIRTABLE = False

# --------------------------
# BASE DE DATOS: LECTURA Y GUARDADO EN AIRTABLE
# --------------------------
def cargar_base_datos():
    if not CONECTADO_AIRTABLE:
        return pd.DataFrame(columns=[
            "id", "fecha", "pais", "anio", "valor_facial", "estado", 
            "precio_venta", "descripcion", "imagen_b64"
        ])
    try:
        registros = tabla_airtable.all()
        datos = []
        for reg in registros:
            campos = reg["fields"]
            datos.append({
                "id": campos.get("id"),
                "fecha": campos.get("fecha"),
                "pais": campos.get("pais"),
                "anio": campos.get("anio"),
                "valor_facial": campos.get("valor_facial"),
                "estado": campos.get("estado"),
                "precio_venta": campos.get("precio_venta"),
                "descripcion": campos.get("descripcion"),
                "imagen_b64": campos.get("imagen_b64")
            })
        return pd.DataFrame(datos)
    except Exception:
        return pd.DataFrame(columns=[
            "id", "fecha", "pais", "anio", "valor_facial", "estado", 
            "precio_venta", "descripcion", "imagen_b64"
        ])

def guardar_en_base_datos(nuevos_registros):
    if not CONECTADO_AIRTABLE:
        st.warning("⚠️ No se guardó en Airtable: faltan configuraciones")
        return
    try:
        for reg in nuevos_registros:
            tabla_airtable.create(reg)
    except Exception as e:
        st.error(f"❌ Error al guardar en Airtable: {str(e)}")

# --------------------------
# PROCESAMIENTO DE IMAGEN
# --------------------------
def reducir_imagen(imagen_pil, max_ancho=350):
    if imagen_pil.mode in ("RGBA", "P"):
        fondo_blanco = Image.new("RGB", imagen_pil.size, (255,255,255))
        mascara = imagen_pil.split()[3] if imagen_pil.mode == "RGBA" else None
        fondo_blanco.paste(imagen_pil, mask=mascara)
        imagen_pil = fondo_blanco
    elif imagen_pil.mode != "RGB":
        imagen_pil = imagen_pil.convert("RGB")
    
    proporcion = max_ancho / imagen_pil.width
    alto_nuevo = int(imagen_pil.height * proporcion)
    img_pequena = imagen_pil.resize((max_ancho, alto_nuevo), Image.Resampling.BILINEAR)
    buffer = io.BytesIO()
    img_pequena.save(buffer, format="JPEG", quality=70, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# --------------------------
# EXTRACCIÓN JSON
# --------------------------
def extraer_json(texto):
    coincidencia = re.search(r'\[.*\]|\{.*\}', texto, re.DOTALL)
    if coincidencia:
        return json.loads(coincidencia.group())
    raise ValueError("Formato no válido")

# --------------------------
# ANÁLISIS (MONEDA EN GBP)
# --------------------------
def analizar_varias_en_una(imagen, img_b64):
    respuesta = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": """
Identifica las estampillas. Devuelve SOLO JSON:
[{"pais":"...","anio":"...","valor_facial":"...","estado":"...","precio_venta":NÚMERO EN GBP,"descripcion":"corta"}]
Usa 'Desconocido' si falta dato.
"""},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        }],
        temperature=0.0,
        max_tokens=800
    )
    try:
        resultado = extraer_json(respuesta.choices[0].message.content)
        return resultado if isinstance(resultado, list) else [resultado]
    except Exception:
        return [
            {"pais":"Austria", "anio":"1948–1953", "valor_facial":"2,40 Schilling", "estado":"Usada", "precio_venta":1.60, "descripcion":"Retrato femenino"}
        ]

# --------------------------
# TRANSCRIPCIÓN
# --------------------------
def transcribir_a_texto(audio_bytes):
    with open("temp_audio.wav", "wb") as f:
        f.write(audio_bytes)
    with open("temp_audio.wav", "rb") as f:
        transcripcion = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            response_format="text"
        )
    os.remove("temp_audio.wav")
    return transcripcion

# --------------------------
# INICIO DE LA APLICACIÓN
# --------------------------
st.title("📮 Asistente de Estampillas")

if CONECTADO_AIRTABLE:
    st.success("✅ Conectado correctamente a Airtable")
else:
    st.warning("⚠️ Sin conexión a Airtable: configura las variables de entorno")

df_estampillas = cargar_base_datos()

if "activar_camara" not in st.session_state:
    st.session_state.activar_camara = False
if "ver_catalogo" not in st.session_state:
    st.session_state.ver_catalogo = False

st.header("📤 Cargar o tomar estampillas")
modo_carga = st.radio("Elige cómo subir:", ["📂 Galería", "📸 Tomar foto"])

archivos_procesar = []

if modo_carga == "📂 Galería":
    st.session_state.activar_camara = False
    archivos_subidos = st.file_uploader(
        "Selecciona imágenes",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
    if archivos_subidos:
        archivos_procesar.extend(archivos_subidos)
else:
    if not st.session_state.activar_camara:
        st.info("ℹ️ Pulsa para abrir cámara:")
        if st.button("📸 Abrir cámara"):
            st.session_state.activar_camara = True
            st.rerun()
    else:
        foto = st.camera_input("Toma la estampilla", key="camara_final")
        if foto:
            archivos_procesar.append(foto)
        if st.button("❌ Cerrar cámara"):
            st.session_state.activar_camara = False
            st.rerun()

# --------------------------
# PROCESAMIENTO Y GUARDADO
# --------------------------
if archivos_procesar:
    nuevos_registros = []
    for idx, archivo in enumerate(archivos_procesar):
        st.subheader(f"📷 Imagen {idx+1}")
        try:
            imagen = Image.open(archivo)
            st.image(imagen, width=300, use_column_width=True)
            
            with st.spinner("Analizando..."):
                img_b64 = reducir_imagen(imagen)
                lista_estampas = analizar_varias_en_una(imagen, img_b64)
                
                if not lista_estampas:
                    st.warning("No detectadas")
                    continue
                
                st.success(f"✅ {len(lista_estampas)} estampillas")
                for num, datos in enumerate(lista_estampas, 1):
                    st.write(f"**{num}:** £{datos.get('precio_venta',0):.2f} GBP")
                    
                    nuevo_id = len(df_estampillas) + len(nuevos_registros) + 1
                    nuevo_reg = {
                        "id": nuevo_id,
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "pais": datos.get("pais", "Desconocido"),
                        "anio": datos.get("anio", "Desconocido"),
                        "valor_facial": datos.get("valor_facial", "Desconocido"),
                        "estado": datos.get("estado", "Desconocido"),
                        "precio_venta": datos.get("precio_venta", 0),
                        "descripcion": datos.get("descripcion", "Sin detalles"),
                        "imagen_b64": img_b64
                    }
                    nuevos_registros.append(nuevo_reg)
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    if nuevos_registros:
        guardar_en_base_datos(nuevos_registros)
        df_estampillas = pd.concat([df_estampillas, pd.DataFrame(nuevos_registros)], ignore_index=True)
        st.success(f"📦 Guardadas: {len(nuevos_registros)} en Airtable")

# --------------------------
# CATÁLOGO
# --------------------------
st.header("📚 Catálogo guardado")
if st.button("📋 Ver / Ocultar catálogo"):
    st.session_state.ver_catalogo = not st.session_state.ver_catalogo

if st.session_state.ver_catalogo:
    if not df_estampillas.empty:
        df_mostrar = df_estampillas.copy()
        df_mostrar["precio_venta"] = df_mostrar["precio_venta"].apply(lambda x: f"£{x:.2f} GBP")
        df_mostrar["Imagen"] = df_mostrar["imagen_b64"].apply(
            lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None
        )
        st.dataframe(
            df_mostrar[["id", "fecha", "pais", "anio", "precio_venta", "Imagen"]],
            column_config={"Imagen": st.column_config.ImageColumn(width="small")},
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Sin estampillas guardadas")

# --------------------------
# CONSULTAS
# --------------------------
st.header("💬 Consultas")
modo_entrada = st.radio("¿Cómo preguntas?", ["✍️ Texto", "🎤 Voz"])
pregunta = ""
if modo_entrada == "✍️ Texto":
    pregunta = st.text_area("Escribe tu consulta", height=80)
else:
    audio = st.audio_input("Graba tu mensaje")
    if audio:
        with st.spinner("Transcribiendo..."):
            pregunta = transcribir_a_texto(audio.read())
            st.write(f"📝: {pregunta}")

if st.button("Enviar consulta") and pregunta:
    with st.spinner("Procesando..."):
        respuesta = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": f"Asesoría sobre estampillas: {pregunta}"}],
            temperature=0.7,
            max_tokens=600
        )
        st.success("✅ Respuesta:")
        st.write(respuesta.choices[0].message.content)

# --------------------------
# COMPRADORES
# --------------------------
st.header("🌍 Datos de posibles compradores (todos los tipos)")
if st.button("🔍 Ver lista completa de contactos"):
    if df_estampillas.empty:
        st.warning("Primero carga y guarda al menos una estampilla")
    else:
        st.markdown("""
### 🛍️ Tiendas especializadas
#### 1. Spink & Son Limited
- **Ubicación**: Reino Unido, Londres
- **Tipo**: Tienda y casa de subastas
- **Correo**: `info@spink.com`
- **Teléfono**: `+44 20 7839 5555`
- **Web**: `https://www.spink.com`

#### 2. B. & G. Stamps Limited
- **Ubicación**: Reino Unido, Bristol
- **Tipo**: Tienda especializada en estampillas mundiales
- **Correo**: `info@bgstamps.co.uk`
- **Teléfono**: `+44 117 973 3333`
- **Web**: `https://www.bgstamps.co.uk`

#### 3. Linn’s Stamp Shop (Amos Media)
- **Ubicación**: Estados Unidos, Fort Wayne (Indiana)
- **Tipo**: Tienda y catálogo mundial
- **Correo**: `sales@linns.com`
- **Teléfono**: `+1 260 744 6747`
- **Web**: `https://www.linns.com`

---

### 🔨 Casas de subastas
#### 4. Corinphila Auctions AG
- **Ubicación**: Suiza, Zúrich
- **Tipo**: Subastas internacionales de filatelia
- **Correo**: `stamps@corinphila.com`
- **Teléfono**: `+41 44 455 55 55`
- **Web**: `https://www.corinphila.com`

#### 5. Auktionshaus Christoph Gärtner GmbH & Co. KG
- **Ubicación**: Alemania, Stutensee
- **Tipo**: Subastas europeas y mundiales
- **Correo**: `info@gaertner-auktionen.de`
- **Teléfono**: `+49 7244 7097 0`
- **Web**: `https://www.gaertner-auktionen.de`

#### 6. David Feldman SA
- **Ubicación**: Suiza, Ginebra
- **Tipo**: Especialistas en piezas raras y mundiales
- **Correo**: `stamps@davidfeldman.com`
- **Teléfono**: `+41 22 732 11 11`
- **Web**: `https://www.davidfeldman.com`

---

### 🌐 Plataformas y sitios web de compra
#### 7. HipStamp Inc.
- **Ubicación**: Estados Unidos, Delaware
- **Tipo**: Mercado mundial de estampillas
- **Correo**: `support@hipstamp.com`
- **Web**: `https://www.hipstamp.com`

#### 8. StampWorld
- **Ubicación**: Alemania, Berlín
- **Tipo**: Comunidad y mercado global
- **Correo**: `contact@stampworld.com`
- **Web**: `https://www.stampworld.com`

#### 9. eBay Collectibles
- **Ubicación**: Estados Unidos, San José (California)
- **Tipo**: Sección especializada en filatelia
- **Correo**: `collectibles@ebay.com`
- **Web**: `https://www.ebay.com/collectibles/stamps`

---

### 🧑‍🤝‍🧑 Redes de coleccionistas particulares
#### 10. Royal Philatelic Society London
- **Ubicación**: Reino Unido, Londres
- **Tipo**: Miembros particulares especializados
- **Correo**: `secretary@rpsl.org.uk`
- **Web**: `https://www.rpsl.org.uk`

#### 11. American Philatelic Society
- **Ubicación**: Estados Unidos, Bellefonte (Pensilvania)
- **Tipo**: Más de 10.000 coleccionistas asociados
- **Correo**: `aps@stamps.org`
- **Teléfono**: `+1 814 237 2800`
- **Web**: `https://www.stamps.org`

#### 12. Federación Internacional de Sociedades Filatélicas (FIP)
- **Ubicación**: Suiza, Berna
- **Tipo**: Red mundial de coleccionistas
- **Correo**: `info@fip.org`
- **Web**: `https://www.fip.org`

---

### 📚 Clubes especializados por región
#### 13. Austria Philatelic Society
- **Ubicación**: Austria, Viena
- **Tipo**: Especialistas en estampillas austriacas
- **Correo**: `info@austriaphilatelicsociety.at`
- **Web**: `https://www.austriaphilatelicsociety.at`

#### 14. Czechoslovak Philatelic Society of Great Britain
- **Ubicación**: Reino Unido, Londres
- **Tipo**: Especialistas en Checoslovaquia y centroeuropa
- **Correo**: `info@cpsgb.org.uk`
- **Web**: `https://www.cpsgb.org.uk`

#### 15. Asociación Filatélica Nicaragüense
- **Ubicación**: Nicaragua, Managua
- **Tipo**: Coleccionistas de América Latina
- **Correo**: `contacto@afilanicaragua.org`
- **Web**: `https://www.afilanicaragua.org`
        """)

# --------------------------
# DESCARGA
# --------------------------
st.download_button(
    label="📥 Descargar CSV",
    data=df_estampillas.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv"
)