import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import pandas as pd

# ---------------------- CONFIGURACIÓN ----------------------
st.set_page_config(
    page_title="Asistente de Estampillas + Búsqueda Web",
    page_icon="🌐",
    layout="wide"
)

# Lectura segura de tu variable en Render
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    try:
        API_KEY = st.secrets.get("GOOGLE_API_KEY")
    except:
        API_KEY = None

if not API_KEY:
    st.error("⚠️ Falta configurar GOOGLE_API_KEY en Render.")
    st.stop()

genai.configure(api_key=API_KEY)

# ✅ Habilitamos la búsqueda web en el modelo
modelo = genai.GenerativeModel(
    "gemini-3.5-flash",
    generation_config={"temperature": 0.3},
    tools="google_search_retrieval"  # Activa la búsqueda en internet automática
)

# ---------------------- FUNCIÓN ANALIZAR ESTAMPILLA ----------------------
def analizar_estampilla(imagen):
    try:
        img_byte_arr = io.BytesIO()
        imagen.save(img_byte_arr, format=imagen.format or "JPEG")
        contenido = [
            "Analiza esta estampilla postal. Primero describe lo que ves, luego usa la búsqueda en internet para confirmar datos exactos, valor de mercado y rareza. Devuelve SOLO los datos en este formato:",
            "País: ", "Año exacto o aproximado: ", "Valor facial original: ", "Valor de mercado actual: ", "Temática: ", "Estado de conservación: ", "Rareza (común/poco común/rara/muy rara): ", "Color principal: ",
            {"mime_type": f"image/{(imagen.format or 'jpeg').lower()}", "data": img_byte_arr.getvalue()}
        ]
        respuesta = modelo.generate_content(contenido)
        respuesta.resolve()
        texto = respuesta.text

        datos = {
            "País": "No detectado",
            "Año": "No detectado",
            "Valor Facial": "No detectado",
            "Valor Mercado": "Consulta en chat",
            "Temática": "No detectado",
            "Estado": "No detectado",
            "Rareza": "No detectado",
            "Color Principal": "No detectado"
        }

        for linea in texto.split("\n"):
            if "País" in linea:
                datos["País"] = linea.split(":", 1)[-1].strip()
            elif "Año" in linea:
                datos["Año"] = linea.split(":", 1)[-1].strip()
            elif "Valor facial" in linea:
                datos["Valor Facial"] = linea.split(":", 1)[-1].strip()
            elif "Valor de mercado" in linea:
                datos["Valor Mercado"] = linea.split(":", 1)[-1].strip()
            elif "Temática" in linea or "Tema" in linea:
                datos["Temática"] = linea.split(":", 1)[-1].strip()
            elif "Estado" in linea:
                datos["Estado"] = linea.split(":", 1)[-1].strip()
            elif "Rareza" in linea:
                datos["Rareza"] = linea.split(":", 1)[-1].strip()
            elif "Color" in linea:
                datos["Color Principal"] = linea.split(":", 1)[-1].strip()

        return datos
    except Exception as e:
        return {"Error": f"Fallo al analizar: {str(e)}"}

# ---------------------- INICIO DE DATOS ----------------------
if "catalogo" not in st.session_state:
    st.session_state.catalogo = []
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []

# ---------------------- PESTAÑAS ----------------------
pestaña1, pestaña2 = st.tabs([
    "📇 Catálogo con datos de Internet",
    "💬 Chat (Consulta tu colección + Busca en Web)"
])

# ---------------------- PESTAÑA 1: CATÁLOGO ----------------------
with pestaña1:
    st.subheader("Sube tus estampillas: se analizan y se busca información en internet automáticamente")
    archivos = st.file_uploader(
        "Selecciona una o varias imágenes",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="subir_estampillas"
    )

    if archivos:
        progreso = st.progress(0)
        for i, archivo in enumerate(archivos):
            st.info(f"Analizando y buscando datos de estampilla {i+1}...")
            img = Image.open(archivo)
            st.image(img, width=280, caption=f"Estampilla {i+1}")

            datos_estampa = analizar_estampilla(img)
            st.session_state.catalogo.append(datos_estampa)
            progreso.progress((i+1)/len(archivos))

        st.success("✅ Análisis completado: se combinó tu imagen con datos de internet!")

    st.subheader("📋 Tabla ordenada de tu colección")
    if st.session_state.catalogo:
        df = pd.DataFrame(st.session_state.catalogo)
        columnas_orden = ["País", "Año", "Valor Facial", "Valor Mercado", "Temática", "Estado", "Rareza", "Color Principal"]
        df = df.reindex(columns=columnas_orden)

        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="💾 Descargar catálogo en CSV",
            data=csv,
            file_name="catalogo_estampillas_completo.csv",
            mime="text/csv"
        )

        if st.button("🗑️ Limpiar catálogo completo"):
            st.session_state.catalogo = []
            st.rerun()
    else:
        st.info("Aún no hay estampillas guardadas. Sube tus imágenes para empezar.")

# ---------------------- PESTAÑA 2: CHAT CON BÚSQUEDA ----------------------
with pestaña2:
    st.subheader("Consulta tu colección y busca cualquier dato en internet")
    st.markdown("✅ **Busca en tu catálogo**: datos de tus estampillas guardadas\n✅ **Busca en internet**: precios, catálogos, historia, rareza, noticias\n✅ Respuesta escrita y hablada")

    pregunta = st.chat_input("Escribe tu pregunta: ej. ¿Cuánto vale esta estampilla? / ¿Dónde venderla? / Historia de las estampillas de España...")

    if pregunta:
        st.session_state.historial_chat.append({"rol": "usuario", "texto": pregunta})

        # Contexto que combina tu catálogo + permiso de búsqueda web
        contexto = f"""Eres experto en filatelia.
        1. Primero revisa mi catálogo: {st.session_state.catalogo if st.session_state.catalogo else 'No tengo estampillas guardadas aún.'}
        2. Usa la búsqueda en internet para complementar, confirmar y ampliar la información: precios actuales, catálogos oficiales, datos históricos, valor de mercado, rareza, etc.
        3. Responde claro, breve y en español. Si usas datos de internet, menciona brevemente la fuente.
        Pregunta: {pregunta}"""

        respuesta = modelo.generate_content(contexto).text
        st.session_state.historial_chat.append({"rol": "asistente", "texto": respuesta})

    for msg in st.session_state.historial_chat:
        if msg["rol"] == "usuario":
            st.chat_message("👤 Tú").write(msg["texto"])
        else:
            st.chat_message("🤖 Asistente").write(msg["texto"])
            texto_seguro = msg["texto"].replace("'", "\\'").replace('"', '\\"')
            st.markdown(f"""
            <button onclick="speechSynthesis.speak(new SpeechSynthesisUtterance('{texto_seguro}'))"
            style="padding:6px 12px; background:#0068c9; color:white; border:none; border-radius:5px; cursor:pointer; font-size:13px; margin:5px 0;">
            🔊 Escuchar respuesta
            </button>
            """, unsafe_allow_html=True)

    if st.button("🗑️ Borrar historial del chat"):
        st.session_state.historial_chat = []
        st.rerun()