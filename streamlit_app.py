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
# CONFIGURACIÓN MÓVIL
# --------------------------
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="auto"
)
st.markdown("""
<style>
.stButton>button {min-height: 48px !important; font-size: 16px !important;}
[data-testid="stFileUploader"] {font-size: 15px !important;}
h1, h2, h3 {font-size: 18px !important;}
</style>
""", unsafe_allow_html=True)

# --------------------------
# CONFIGURACIÓN SEGURA
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
# PROCESAMIENTO DE IMÁGENES
# --------------------------
def reducir_imagen(imagen_pil, max_ancho=500):
    proporcion = max_ancho / imagen_pil.width
    alto_nuevo = int(imagen_pil.height * proporcion)
    img_pequena = imagen_pil.resize((max_ancho, alto_nuevo), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img_pequena.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def extraer_json(texto):
    coincidencia = re.search(r'\[.*\]|\{.*\}', texto, re.DOTALL)
    if coincidencia:
        return json.loads(coincidencia.group())
    raise ValueError("No se encontró JSON válido")

def analizar_varias_en_una(imagen, img_b64):
    """Analiza TODAS las estampillas que haya en la misma foto, cada una por separado"""
    respuesta = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": """
En esta imagen puede haber UNA O VARIAS estampillas.
Identifica CADA estampilla POR SEPARADO, sin omitir ninguna.
Devuelve SOLO un arreglo JSON válido, sin texto antes ni después.
Cada objeto dentro del arreglo debe tener exactamente estos campos:
{
    "pais": "país de emisión",
    "anio": "año aproximado",
    "valor_facial": "valor facial",
    "estado": "estado de conservación",
    "precio_venta": "precio recomendado en USD (solo número)",
    "descripcion": "detalles de diseño y colores"
}
Si solo hay una, devuelve un arreglo con un solo objeto.
"""},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        }],
        temperature=0.1
    )
    try:
        resultado = extraer_json(respuesta.choices[0].message.content)
        if not isinstance(resultado, list):
            resultado = [resultado]
        return resultado
    except Exception as e:
        st.error(f"Error al analizar: {str(e)}")
        return []

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
# INTERFAZ PRINCIPAL
# --------------------------
st.title("📮 Asistente de Estampillas")
df_estampillas = cargar_base_datos()

# --------------------------
# CARGAR O TOMAR FOTO
# --------------------------
st.header("📤 Cargar o tomar estampillas")
modo_carga = st.radio("Elige cómo subir:", ["📸 Tomar foto con cámara", "📂 Seleccionar de la galería"])

archivos_procesar = []

if modo_carga == "📸 Tomar foto con cámara":
    foto = st.camera_input("Toma la foto (puedes poner varias estampillas juntas)")
    if foto:
        archivos_procesar.append(foto)
else:
    archivos_subidos = st.file_uploader(
        "Selecciona una o varias imágenes",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
    if archivos_subidos:
        archivos_procesar.extend(archivos_subidos)

# Procesar imágenes: cada estampilla por separado
if archivos_procesar:
    nuevos_registros = []
    for idx, archivo in enumerate(archivos_procesar):
        st.subheader(f"📷 Imagen {idx+1}")
        imagen = Image.open(archivo)
        st.image(imagen, width=300)
        
        with st.spinner("Analizando cada estampilla por separado..."):
            img_b64 = reducir_imagen(imagen)
            lista_estampas = analizar_varias_en_una(imagen, img_b64)
            
            if not lista_estampas:
                st.warning("No se detectaron estampillas claras en esta imagen")
                continue
            
            st.success(f"✅ Se detectaron {len(lista_estampas)} estampillas en esta foto:")
            for num, datos in enumerate(lista_estampas, 1):
                st.write(f"**Estampilla {num}:**")
                st.table(pd.DataFrame([datos]))
                
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
    
    if nuevos_registros:
        df_nuevos = pd.DataFrame(nuevos_registros)
        df_estampillas = pd.concat([df_estampillas, df_nuevos], ignore_index=True)
        guardar_en_base_datos(df_estampillas)
        st.success(f"📦 Guardadas en total: {len(nuevos_registros)} estampillas")

# --------------------------
# RESTO DE FUNCIONES IGUALES
# --------------------------
st.header("📚 Catálogo guardado")
if not df_estampillas.empty:
    df_mostrar = df_estampillas.copy()
    df_mostrar["Imagen"] = df_mostrar["imagen_b64"].apply(
        lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None
    )
    st.dataframe(
        df_mostrar[["id", "pais", "anio", "valor_facial", "estado", "precio_venta", "Imagen"]],
        column_config={"Imagen": st.column_config.ImageColumn(width="small")},
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Aún no hay estampillas guardadas")

st.header("💬 Consultas")
modo_entrada = st.radio("¿Cómo preguntas?", ["✍️ Texto", "🎤 Voz"])
pregunta = ""
if modo_entrada == "✍️ Texto":
    pregunta = st.text_area("Escribe tu consulta", height=100)
else:
    audio = st.audio_input("Graba tu mensaje")
    if audio:
        with st.spinner("Transcribiendo..."):
            pregunta = transcribir_a_texto(audio.read())
            st.write(f"📝 Tu mensaje: {pregunta}")

if st.button("Enviar consulta") and pregunta:
    with st.spinner("Procesando..."):
        respuesta = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": f"Asesoría sobre estampillas: {pregunta}"}],
            temperature=0.7
        )
        st.success("✅ Respuesta:")
        st.write(respuesta.choices[0].message.content)

st.header("🌍 Venta internacional")
if st.button("Generar propuesta de venta"):
    with st.spinner("Preparando..."):
        lista = df_estampillas[["pais", "anio", "precio_venta"]].to_dict("records")
        propuesta = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": f"Propuesta de venta global: {lista}"}],
            temperature=0.6
        )
        st.markdown(propuesta.choices[0].message.content)

st.download_button(
    label="📥 Descargar CSV",
    data=df_estampillas.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv"
)
