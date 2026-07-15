import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import pandas as pd

# ---------------------- CONFIGURACIÓN ----------------------
st.set_page_config(
    page_title="Catálogo de Estampillas",
    page_icon="📇",
    layout="wide"
)

# ✅ Lectura segura de tu variable en Render
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
modelo = genai.GenerativeModel("gemini-2.5-flash")

# ---------------------- FUNCIÓN DE ANÁLISIS ----------------------
def analizar_estampilla(imagen):
    try:
        img_byte_arr = io.BytesIO()
        imagen.save(img_byte_arr, format=imagen.format or "JPEG")
        contenido = [
            "Analiza esta estampilla postal y devuelve SOLO los datos en este formato exacto:",
            "País: ", "Año: ", "Valor Facial: ", "Temática: ", "Estado: ", "Color Principal: ",
            {"mime_type": f"image/{(imagen.format or 'jpeg').lower()}", "data": img_byte_arr.getvalue()}
        ]
        respuesta = modelo.generate_content(contenido)
        respuesta.resolve()
        texto = respuesta.text

        # Extracción ordenada para la tabla
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
            elif "Valor" in linea:
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

# ---------------------- INICIO DE DATOS PERMANENTES ----------------------
# Guardamos los datos en la sesión para que no se borren al recargar
if "catalogo" not in st.session_state:
    st.session_state.catalogo = []

# ---------------------- INTERFAZ ----------------------
st.title("📇 Catálogo y Análisis de Estampillas")

# Subida de imágenes
st.subheader("1. Sube tus estampillas para analizarlas")
archivos = st.file_uploader(
    "Selecciona una o varias imágenes",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    key="subir_estampillas"
)

# Procesar imágenes
if archivos:
    progreso = st.progress(0)
    for i, archivo in enumerate(archivos):
        st.info(f"Analizando estampilla {i+1} de {len(archivos)}...")
        img = Image.open(archivo)
        st.image(img, width=280, caption=f"Estampilla {i+1}")

        # Analizar y agregar al catálogo
        datos_estampa = analizar_estampilla(img)
        st.session_state.catalogo.append(datos_estampa)
        progreso.progress((i+1)/len(archivos))

    st.success("✅ Todas las estampillas han sido analizadas y guardadas!")

# Mostrar tabla ordenada
st.subheader("2. Tabla de Estampillas Guardadas")
if st.session_state.catalogo:
    # Crear DataFrame ordenado por columnas
    df = pd.DataFrame(st.session_state.catalogo)
    # Ordenar columnas en el orden que queremos
    columnas_orden = ["País", "Año", "Valor Facial", "Temática", "Estado", "Color Principal"]
    df = df.reindex(columns=columnas_orden)

    # Mostrar tabla limpia
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Opciones de guardado
    st.subheader("3. Guardar tu catálogo")
    col1, col2 = st.columns(2)

    with col1:
        # Descargar en CSV
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="💾 Descargar en CSV (Excel)",
            data=csv,
            file_name="catalogo_estampillas.csv",
            mime="text/csv"
        )

    with col2:
        # Descargar en Excel
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Estampillas")
        st.download_button(
            label="📊 Descargar en Excel",
            data=excel_buffer.getvalue(),
            file_name="catalogo_estampillas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Botón para limpiar el catálogo
    if st.button("🗑️ Limpiar catálogo actual"):
        st.session_state.catalogo = []
        st.rerun()

else:
    st.info("Aún no hay estampillas guardadas. Sube tus imágenes para empezar.")