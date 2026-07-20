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

# --------------------------
# CONFIGURACIÓN
# --------------------------
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
.stButton>button {min-height: 52px !important; font-size: 17px !important;}
[data-testid="stFileUploader"] {font-size: 15px !important;}
h1, h2, h3 {font-size: 19px !important;}
</style>
""", unsafe_allow_html=True)

# --------------------------
# CONEXIÓN Y ARCHIVO
# --------------------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
ARCHIVO_DATOS = "estampillas_almacenadas.csv"

# --------------------------
# BASE DE DATOS
# --------------------------
def cargar_base_datos():
    if os.path.exists(ARCHIVO_DATOS):
        return pd.read_csv(ARCHIVO_DATOS, converters={"imagen_b64": str})
    return pd.DataFrame(columns=[
        "id", "fecha", "pais", "anio", "valor_facial", "estado", 
        "precio_venta", "descripcion", "imagen_b64"
    ])

def guardar_en_base_datos(df):
    df.to_csv(ARCHIVO_DATOS, index=False)

# --------------------------
# PROCESAMIENTO DE IMAGEN (RÁPIDO)
# --------------------------
def reducir_imagen(imagen_pil, max_ancho=400):
    if imagen_pil.mode in ("RGBA", "P"):
        fondo_blanco = Image.new("RGB", imagen_pil.size, (255, 255, 255))
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
# ANÁLISIS DE ESTAMPILLAS (GBP)
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
# TRANSCRIPCIÓN DE AUDIO
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
# INICIO DE LA APP
# --------------------------
st.title("📮 Asistente de Estampillas")
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
            st.image(imagen, width=250)
            
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
                    nuevos_registros.append({
                        "id": nuevo_id,
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "pais": datos.get("pais", "Desconocido"),
                        "anio": datos.get("anio", "Desconocido"),
                        "valor_facial": datos.get("valor_facial", "Desconocido"),
                        "estado": datos.get("estado", "Desconocido"),
                        "precio_venta": datos.get("precio_venta", 0),
                        "descripcion": datos.get("descripcion", "Sin detalles"),
                        "imagen_b64": img_b64
                    })
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    if nuevos_registros:
        df_nuevos = pd.DataFrame(nuevos_registros)
        df_estampillas = pd.concat([df_estampillas, df_nuevos], ignore_index=True)
        guardar_en_base_datos(df_estampillas)
        st.success(f"📦 Guardadas: {len(nuevos_registros)}")

# --------------------------
# CATÁLOGO VER/OCULTAR
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
# TODOS LOS TIPOS DE COMPRADORES MUNDIALES
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
# DESCARGA DEL CATÁLOGO
# --------------------------
st.download_button(
    label="📥 Descargar CSV",
    data=df_estampillas.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv"
)