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

# ---------------------- FUNCIÓN: IMAGEN A MINIATURA PARA TABLA ----------------------
def imagen_a_html(img, ancho=100):
    buf = io.BytesIO()
    imagen_redimensionada = img.copy()
    imagen_redimensionada.thumbnail((ancho, ancho))
    imagen_redimensionada.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f'<img src="data:image/png;base64,{b64}" width="{ancho}">'

# ---------------------- FUNCIÓN: ANALIZAR TODAS LAS ESTAMPILLAS DE UNA FOTO ----------------------
def analizar_imagen_completa(imagen):
    try:
        img_byte_arr = io.BytesIO()
        imagen.save(img_byte_arr, format=imagen.format or "JPEG")
        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

        respuesta = cliente.chat.completions.create(
            # ✅ Modelo de visión CONFIRMADO en Groq hoy
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": """
Analiza esta imagen: puede tener UNA o VARIAS estampillas postales.
Detecta CADA estampilla por separado. Para cada una, devuelve SOLO este formato exacto, sin texto extra:

--- ESTAMPILLA ---
País:
Año aproximado:
Valor facial original:
Precio estimado de mercado (en euros):
Temática / diseño:
Estado de conservación:
Color principal:
--- FIN ---

Si hay varias, repite el bloque para cada una. Si solo hay una, pon un solo bloque.
"""},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=2048
        )

        texto = respuesta.choices[0].message.content
        lista_estampillas = []
        bloque_actual = {}

        # Extraer cada bloque de datos
        for linea in texto.split("\n"):
            linea = linea.strip()
            if "--- ESTAMPILLA ---" in linea:
                bloque_actual = {}
            elif "--- FIN ---" in linea:
                if bloque_actual:
                    bloque_actual["Foto"] = imagen_a_html(imagen)
                    lista_estampillas.append(bloque_actual)
            elif "País:" in linea:
                bloque_actual["País"] = linea.split(":", 1)[-1].strip() or "No detectado"
            elif "Año" in linea:
                bloque_actual["Año"] = linea.split(":", 1)[-1].strip() or "No detectado"
            elif "Valor facial" in linea:
                bloque_actual["Valor Facial"] = linea.split(":", 1)[-1].strip() or "No detectado"
            elif "Precio estimado" in linea:
                bloque_actual["Precio Estimado (€)"] = linea.split(":", 1)[-1].strip() or "No disponible"
            elif "Temática" in linea or "diseño" in linea:
                bloque_actual["Temática"] = linea.split(":", 1)[-1].strip() or "No detectado"
            elif "Estado" in linea:
                bloque_actual["Estado"] = linea.split(":", 1)[-1].strip() or "No detectado"
            elif "Color principal" in linea:
                bloque_actual["Color Principal"] = linea.split(":", 1)[-1].strip() or "No detectado"

        # Si no se detectó el formato, guardar como una sola estampilla
        if not lista_estampillas:
            lista_estampillas.append({
                "Foto": imagen_a_html(imagen),
                "País": "No detectado",
                "Año": "No detectado",
                "Valor Facial": "No detectado",
                "Precio Estimado (€)": "No disponible",
                "Temática": "No detectado",
                "Estado": "No detectado",
                "Color Principal": "No detectado"
            })

        return lista_estampillas

    except Exception as e:
        st.error(f"Fallo al analizar: {str(e)}")
        return []

# ---------------------- FUNCIÓN CHAT ----------------------
def responder_chat(mensaje, catalogo):
    try:
        contexto = f"""Eres un experto en estampillas postales y coleccionismo.
Mi catálogo actual: {catalogo if catalogo else 'Vacío'}
Responde claro, breve y en español correcto.
Pregunta: {mensaje}"""

        respuesta = cliente.chat.completions.create(
            # ✅ Modelo de chat CONFIRMADO y estable
            model="llama-3.3-70b-instruct",
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
    "📇 Catálogo con Fotos y Precios",
    "💬 Chat con Asistente"
])

# ---------------------- PESTAÑA 1: CATÁLOGO ----------------------
with pestaña1:
    st.subheader("Sube tus fotos: se analiza cada estampilla por separado")
    archivos = st.file_uploader(
        "Puedes subir fotos con una o varias estampillas",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="subir_estampillas"
    )

    if archivos:
        progreso = st.progress(0)
        nuevas_totales = []
        for i, archivo in enumerate(archivos):
            st.info(f"Procesando imagen {i+1} de {len(archivos)}...")
            img = Image.open(archivo)
            st.image(img, width=350, caption="Imagen cargada")

            nuevas = analizar_imagen_completa(img)
            nuevas_totales.extend(nuevas)
            for estampa in nuevas:
                st.session_state.catalogo.append(estampa)

            progreso.progress((i+1)/len(archivos))
            time.sleep(0.5)

        st.success(f"✅ Se agregaron {len(nuevas_totales)} estampillas nuevas!")

    st.subheader("📋 Tabla completa")
    if st.session_state.catalogo:
        columnas = ["Foto", "País", "Año", "Valor Facial", "Precio Estimado (€)", "Temática", "Estado", "Color Principal"]
        df = pd.DataFrame(st.session_state.catalogo)
        df = df.reindex(columns=columnas)

        # Mostrar tabla con imágenes
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Descargar CSV (sin imágenes para que sea compatible)
        csv = df.drop(columns=["Foto"]).to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="💾 Descargar catálogo en CSV",
            data=csv,
            file_name="catalogo_estampillas.csv",
            mime="text/csv"
        )

        if st.button("🗑️ Limpiar todo el catálogo"):
            st.session_state.catalogo = []
            st.rerun()
    else:
        st.info("Aún no hay estampillas. Sube tus fotos para empezar.")

# ---------------------- PESTAÑA 2: CHAT ----------------------
with pestaña2:
    st.subheader("Consulta tu colección")
    st.markdown("✅ Conoce todas tus estampillas\n✅ Respuesta escrita y hablada")

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
            seguro = msg["texto"].replace("'", "\\'").replace('"', '\\"')
            st.markdown(f"""
            <button onclick="speechSynthesis.speak(new SpeechSynthesisUtterance('{seguro}'))"
            style="padding:6px 12px; background:#0068c9; color:white; border:none; border-radius:6px; cursor:pointer;">
            🔊 Escuchar respuesta
            </button>
            """, unsafe_allow_html=True)

    if st.button("🗑️ Borrar chat"):
        st.session_state.historial_chat = []
        st.rerun()