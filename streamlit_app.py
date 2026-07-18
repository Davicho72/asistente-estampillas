import streamlit as st
from groq import Groq
import base64
from PIL import Image
import io
import os
import pandas as pd
from datetime import datetime

# --------------------------
# CONFIGURACIÓN SEGURA
# --------------------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
ARCHIVO_DATOS = "estampillas_almacenadas.csv"

# --------------------------
# INICIALIZAR BASE DE DATOS
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
# FUNCIONES DE PROCESAMIENTO
# --------------------------
def reducir_imagen(imagen_pil, max_ancho=600):
    proporcion = max_ancho / imagen_pil.width
    alto_nuevo = int(imagen_pil.height * proporcion)
    img_pequena = imagen_pil.resize((max_ancho, alto_nuevo), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img_pequena.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

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

def texto_a_voz(texto):
    respuesta = client.audio.speech.create(
        model="canopylabs/orpheus-v1-english",
        voice="diana",
        input=texto
    )
    return respuesta.content

# --------------------------
# INTERFAZ PRINCIPAL
# --------------------------
st.set_page_config(page_title="Asistente de Estampillas", layout="wide")
st.title("📮 Asistente Integral para Estampillas")

# Cargar datos
df_estampillas = cargar_base_datos()

# --------------------------
# SECCIÓN 1: CARGAR Y CARACTERIZAR ESTAMPILLAS
# --------------------------
st.header("📤 Cargar y analizar estampillas")
archivos_subidos = st.file_uploader(
    "Sube una o varias imágenes de estampillas",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if archivos_subidos:
    nuevos_registros = []
    for idx, archivo in enumerate(archivos_subidos):
        st.subheader(f"Estampilla {idx+1}")
        imagen = Image.open(archivo)
        st.image(imagen, width=350)
        
        with st.spinner("Analizando características..."):
            img_b64 = reducir_imagen(imagen)
            respuesta = client.chat.completions.create(
                model="qwen/qwen3.6-27b-instruct",
                messages=[{
                    "role": "user",
                    "content": f"""Analiza esta estampilla y devuelve SOLO un JSON con estos datos:
                    - pais: país de emisión
                    - anio: año aproximado
                    - valor_facial: valor facial
                    - estado: estado de conservación
                    - precio_venta: precio recomendado en USD
                    - descripcion: detalles adicionales
                    ![Imagen](data:image/jpeg;base64,{img_b64})"""
                }],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            import json
            datos = json.loads(respuesta.choices[0].message.content)
            
            # Mostrar en tabla
            st.write("📋 Características detectadas:")
            st.table(pd.DataFrame([datos]))
            
            # Agregar a base
            nuevo_id = len(df_estampillas) + 1
            nuevos_registros.append({
                "id": nuevo_id,
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "pais": datos["pais"],
                "anio": datos["anio"],
                "valor_facial": datos["valor_facial"],
                "estado": datos["estado"],
                "precio_venta": datos["precio_venta"],
                "descripcion": datos["descripcion"],
                "imagen_b64": img_b64
            })
    
    # Guardar todo
    if nuevos_registros:
        df_nuevos = pd.DataFrame(nuevos_registros)
        df_estampillas = pd.concat([df_estampillas, df_nuevos], ignore_index=True)
        guardar_en_base_datos(df_estampillas)
        st.success(f"✅ Se guardaron {len(nuevos_registros)} estampillas correctamente")

# --------------------------
# SECCIÓN 2: VER TODAS LAS ESTAMPILLAS EN TABLA
# --------------------------
st.header("📚 Catálogo guardado")
if not df_estampillas.empty:
    # Preparar tabla con imágenes
    df_mostrar = df_estampillas.copy()
    df_mostrar["Imagen"] = df_mostrar["imagen_b64"].apply(
        lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None
    )
    columnas_mostrar = ["id", "fecha", "pais", "anio", "valor_facial", "estado", "precio_venta", "Imagen"]
    st.dataframe(
        df_mostrar[columnas_mostrar],
        column_config={
            "Imagen": st.column_config.ImageColumn(width="medium"),
            "precio_venta": st.column_config.NumberColumn("Precio USD")
        },
        use_container_width=True
    )
else:
    st.info("Aún no hay estampillas guardadas.")

# --------------------------
# SECCIÓN 3: COMUNICACIÓN POR TEXTO Y VOZ
# --------------------------
st.header("💬 Hablar con el asistente")
modo_entrada = st.radio("¿Cómo quieres preguntar?", ["✍️ Texto", "🎤 Voz"])

pregunta = ""
if modo_entrada == "✍️ Texto":
    pregunta = st.text_area("Escribe tu consulta sobre estampillas, precios, venta...")
else:
    audio = st.audio_input("Graba tu mensaje")
    if audio:
        with st.spinner("Transcribiendo..."):
            pregunta = transcribir_a_texto(audio.read())
            st.write(f"📝 Tu mensaje: {pregunta}")

modo_respuesta = st.radio("¿Cómo quieres la respuesta?", ["📄 Solo texto", "🔊 Texto + voz"])

if st.button("Enviar consulta") and pregunta:
    with st.spinner("Procesando..."):
        respuesta = client.chat.completions.create(
            model="qwen/qwen3.6-27b-instruct",
            messages=[{
                "role": "user",
                "content": f"""Eres un asistente especializado en coleccionismo y venta internacional de estampillas.
                Usa la información guardada en el catálogo si es necesario. Responde claro y completo.
                Consulta: {pregunta}"""
            }],
            temperature=0.7
        )
        texto_respuesta = respuesta.choices[0].message.content
    
    st.success("✅ Respuesta:")
    st.write(texto_respuesta)
    
    if modo_respuesta == "🔊 Texto + voz":
        with st.spinner("Generando audio..."):
            audio_respuesta = texto_a_voz(texto_respuesta)
            st.audio(audio_respuesta, format="audio/mp3")

# --------------------------
# SECCIÓN 4: BUSCAR COMPRADORES Y OFRECER
# --------------------------
st.header("🌍 Buscar compradores y ofrecer estampillas")
if st.button("🔍 Generar propuesta de venta global"):
    with st.spinner("Buscando mercados y compradores..."):
        lista_estampas = df_estampillas[["pais", "anio", "valor_facial", "precio_venta"]].to_dict("records")
        propuesta = client.chat.completions.create(
            model="qwen/qwen3.6-27b-instruct",
            messages=[{
                "role": "user",
                "content": f"""Genera una propuesta comercial para ofrecer estas estampillas a coleccionistas y mercados mundiales:
                {lista_estampas}
                
                Incluye:
                - Plataformas recomendadas (HipStamp, eBay, Delcampe, mercados locales)
                - Perfiles de compradores más probables
                - Consejos de envío internacional y precios
                - Cómo contactar coleccionistas por país/región"""
            }],
            temperature=0.6
        )
        st.markdown(propuesta.choices[0].message.content)

# --------------------------
# EXPORTAR DATOS
# --------------------------
st.download_button(
    label="📥 Descargar catálogo completo (CSV)",
    data=df_estampillas.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_estampillas_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)
