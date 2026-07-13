import streamlit as st
import requests
import google.generativeai as genai
from PIL import Image
import os

# -------------------------- CONFIGURACIÓN --------------------------
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN", "pat8xdjKQgmWh7J4J")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appFrOOKpw2fDSR44")
AIRTABLE_TABLE_NAME = "Catálogo de Estampillas"
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
# -------------------------------------------------------------------

# Validación de credenciales
if not GEMINI_API_KEY:
    st.error("⚠️ Falta la clave API de Gemini en las variables de entorno")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
modelo_imagen = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="Asistente Estampillas eBay", layout="centered")

def leer_catalogo():
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    try:
        respuesta = requests.get(url, headers=headers, timeout=10)
        respuesta.raise_for_status()
        return respuesta.json().get("records", [])
    except Exception as e:
        st.error(f"❌ Error al cargar catálogo: {str(e)}")
        return []

def generar_respuesta_texto(pregunta, catalogo):
    contexto = "Eres asistente de ventas de estampillas para eBay. Usa SOLO estos datos:\n"
    for item in catalogo:
        f = item.get("fields", {})
        contexto += f"- {f.get('Descripción','Sin nombre')} | País: {f.get('País','Desconocido')} | Precio: {f.get('Precio','Sin precio')} | Envío: {f.get('Detalles envío','Consultar')}\n"
    contexto += "\nSi no sabes, di que lo consultarás pronto."
    
    try:
        resp = modelo_texto.generate_content(f"{contexto}\nPregunta: {pregunta}")
        resp.resolve()
        return resp.text
    except Exception as e:
        return f"Error: {str(e)}"

def analizar_imagen(imagen, catalogo):
    contexto = "Analiza la estampilla: país, año, diseño, valor, estado. Compara con el catálogo:\n"
    for item in catalogo:
        f = item.get("fields", {})
        contexto += f"- {f.get('Descripción','Sin nombre')} | País: {f.get('País','Desconocido')} | Precio: {f.get('Precio','Sin precio')}\n"
    
    try:
        resp = modelo_imagen.generate_content([contexto, imagen])
        resp.resolve()
        return resp.text
    except Exception as e:
        return f"Error: {str(e)}"

# INTERFAZ
st.title("📮 Asistente de Ventas - Estampillas")
catalogo = leer_catalogo()

opcion = st.radio("¿Qué quieres hacer?", ("✍️ Preguntar por texto", "📸 Analizar foto"))

if opcion == "✍️ Preguntar por texto":
    pregunta = st.text_input("Escribe tu pregunta:")
    if pregunta:
        with st.spinner("Consultando..."):
            st.write(generar_respuesta_texto(pregunta, catalogo))

else:
    archivo = st.file_uploader("Sube la foto", type=["jpg","jpeg","png"])
    if archivo:
        img = Image.open(archivo)
        st.image(img)
        if st.button("🔍 Analizar"):
            with st.spinner("Examinando..."):
                st.write(analizar_imagen(img, catalogo))

with st.expander("📋 Ver catálogo completo"):
    for item in catalogo:
        f = item.get("fields", {})
        st.write(f"**{f.get('Descripción')}** | País: {f.get('País')} | Precio: {f.get('Precio')}")
        st.write("---")