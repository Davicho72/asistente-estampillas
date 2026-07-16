import streamlit as st
from groq import Groq
from PIL import Image
import io
import os
import pandas as pd
import base64
import time

# ---------------------- CONFIGURACIÓN ----------------------
st.set_page_config(
    page_title="Asistente de Estampillas",
    page_icon="📮",
    layout="wide"
)

# Lectura segura de tu variable en Render
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    try:
        API_KEY = st.secrets.get("GROQ_API_KEY")
    except:
        API_KEY = None

if not API_KEY:
    st.error("⚠️ Falta configurar GROQ_API_KEY en Render.")
    st.stop()

cliente = Groq(api_key=API_KEY)

# ---------------------- FUNCIÓN ANALIZAR ESTAMPILLA ----------------------
def analizar_estampilla(imagen):
    try:
        img_byte_arr = io.BytesIO()
        imagen.save(img_byte_arr, format=imagen.format or "JPEG")
        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

        respuesta = cliente.chat.completions.create(
            model="llama-3.2-11b-vision-instruct",  # ✅ Modelo de visión válido
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analiza esta estampilla postal y devuelve SOLO los datos en este formato exacto, sin explicaciones extra:\nPaís: \nAño: \nValor Facial: \nTemática: \nEstado de conservación: \nColor Principal:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                }
            ],
            temperature=0.2,
            max_tokens=1024
        )

        texto = respuesta.choices[0].message.content

        datos = {
            "País": "No detectado",
            "Año": "No detectado",
            "Valor Facial": "No detectado",
            "Temática": "No detectado",
            "Estado": "No detectado",
            "Color Principal": "No detectado"
        }

        for linea in texto.split("\n"):
            if "País" in linea:
                datos["País"] = linea.split(":", 1)[-1].strip()
            elif "Año" in linea:
                datos["Año"] = linea.split(":", 1)[-1].strip()
            elif "Valor Facial" in linea:
                datos["Valor Facial"] = linea.split(":", 1)[-1].strip()
            elif "Temática" in linea or "Tema" in linea:
                datos["Temática"] = linea.split(":", 1)[-1].strip()
            elif "Estado" in linea:
                datos["Estado"] = linea.split(":", 1)[-1].strip()
            elif "Color" in linea:
                datos["Color Principal"] = linea.split(":", 1)[-1].strip()

        return datos
    except Exception as e:
        return {"Error": f"Fallo al analizar: {str(e)}"}

# ---------------------- FUNCIÓN CHAT ----------------------
def responder_chat(mensaje, catalogo):
    try:
        contexto = f"""Eres un experto en estampillas postales y coleccionismo.
        Mi catálogo actual es: {catalogo if catalogo else 'Aún no he agregado estampillas al catálogo.'}
        Responde de forma clara, sencilla y breve, en español correcto.
        Pregunta: {mensaje}"""

        respuesta = cliente.chat.completions.create(
            model="llama-3.1-8b-instruct",  # ✅ Modelo de chat válido y rápido
            messages=[{"role": "user", "content": contexto}],
            temperature=0.3,
            max_tokens=1024
        )

        return respuesta.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# ---------------------- INICIO DE DATOS ----------------------
if "catalogo" not in st.session_state:
    st.session_state.catalogo = []
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []

# ---------------------- PESTAÑAS ----------------------
pestaña1, pestaña2 = st.tabs([
    "📇 Catálogo y Análisis",
    "💬 Chat con Asistente"
])

# ---------------------- PESTAÑA 1: CATÁLOGO ----------------------
with pestaña1:
    st.subheader("Sube tus estampillas para analizarlas")
    archivos = st.file_uploader(
        "Selecciona una o varias imágenes",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="subir_estampillas"
    )

    if archivos:
        progreso = st.progress(0)
        for i, archivo in enumerate(archivos):
            st.info(f"Analizando estampilla {i+1} de {len(archivos)}...")
            img = Image.open(archivo)
            st.image(img, width=280, caption=f"Estampilla {i+1}")

            datos_estampa = analizar_estampilla(img)
            st.session_state.catalogo.append(datos_estampa)
            progreso.progress((i+1)/len(archivos))
            time.sleep(0.3)

        st.success("✅ Todas las estampillas guardadas en la tabla!")

    st.subheader("📋 Tabla ordenada de tu colección")
    if st.session_state.catalogo:
        df = pd.DataFrame(st.session_state.catalogo)
        columnas_orden = ["País", "Año", "Valor Facial", "Temática", "Estado", "Color Principal"]
        df = df.reindex(columns=columnas_orden)

        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="💾 Descargar catálogo en CSV",
            data=csv,
            file_name="catalogo_estampillas.csv",
            mime="text/csv"
        )

        if st.button("🗑️ Limpiar catálogo completo"):
            st.session_state.catalogo = []
            st.rerun()
    else:
        st.info("Aún no hay estampillas guardadas. Sube tus imágenes para empezar.")

# ---------------------- PESTAÑA 2: CHAT ----------------------
with pestaña2:
    st.subheader("Consulta tus estampillas y pregunta cualquier cosa")
    st.markdown("✅ El asistente conoce tu catálogo y responde tus dudas\n✅ Respuesta escrita y hablada")

    pregunta = st.chat_input("Escribe tu pregunta...")

    if pregunta:
        st.session_state.historial_chat.append({"rol": "usuario", "texto": pregunta})
        respuesta = responder_chat(pregunta, st.session_state.catalogo)
        st.session_state.historial_chat.append({"rol": "asistente", "texto": respuesta})

    for msg in st.session_state.historial_chat:
        if msg["rol"] == "usuario":
            st.chat_message("👤 Tú").write(msg["texto"])
        else:
            st.chat_message("🤖 Asistente").write(msg["texto"])
            texto_seguro = msg["texto"].replace("'", "\\'").replace('"', '\\"')
            st.markdown(f"""
            <button onclick="speechSynthesis.speak(new SpeechSynthesisUtterance('{texto_seguro}'))"
            style="padding:6px 12px; background:#0068c9; color:white; border:none; border-radius:6px; cursor:pointer; font-size:13px; margin:5px 0;">
            🔊 Escuchar respuesta
            </button>
            """, unsafe_allow_html=True)

    if st.button("🗑️ Borrar historial del chat"):
        st.session_state.historial_chat = []
        st.rerun()