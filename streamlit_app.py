import streamlit as st
import requests
import google.generativeai as genai
from PIL import Image

# -------------------------- CONFIGURACIÓN (PON TUS DATOS AQUÍ) --------------------------
AIRTABLE_TOKEN = "pat8xdjKQgmWh7J4J"
AIRTABLE_BASE_ID = "appFrOOKpw2fDSR44/tbl3F27bFOtYOTU0X/viw4mTPlvmVHWWS6U?blocks=hide "
AIRTABLE_TABLE_NAME = "Catálogo de Estampillas"
GEMINI_API_KEY = "AQ.Ab8RN6LJOjLH_RF1z3q3_ITpT9b5H0VCzshuh-dzkK6ls8EdLQ"
# -------------------------------------------------------------------------------------------

genai.configure(api_key=GEMINI_API_KEY)
modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
modelo_imagen = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="Asistente Estampillas eBay", layout="centered")

def leer_catalogo():
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    respuesta = requests.get(url, headers=headers)
    return respuesta.json().get("records", []) if respuesta.status_code == 200 else []

def generar_respuesta_texto(pregunta, catalogo):
    contexto = "Eres un asistente de ventas de estampillas en eBay. Usa solo esta información para responder:\n"
    for item in catalogo:
        campos = item["fields"]
        contexto += f"- {campos.get('Descripción', 'Sin nombre')} | País: {campos.get('País', 'Desconocido')} | Precio: {campos.get('Precio', 'Sin precio')} | Envío: {campos.get('Detalles envío', 'Consultar')}\n"
    contexto += "\nSi no sabes la respuesta, di que lo consultarás pronto."
    
    respuesta = modelo_texto.generate_content(f"{contexto}\n\nPregunta: {pregunta}")
    return respuesta.text

def analizar_imagen(imagen, catalogo):
    contexto = "Analiza esta estampilla y dime: país, año aproximado, diseño, valor facial y estado. Luego compara con este catálogo y dime si ya existe y su precio:\n"
    for item in catalogo:
        campos = item["fields"]
        contexto += f"- {campos.get('Descripción', 'Sin nombre')} | País: {campos.get('País', 'Desconocido')} | Precio: {campos.get('Precio', 'Sin precio')}\n"
    
    respuesta = modelo_imagen.generate_content([contexto, imagen])
    return respuesta.text

st.title("📮 Asistente de Ventas - Estampillas")
st.subheader("Funciona en cualquier lugar | Texto y fotos | Totalmente gratuito")

catalogo = leer_catalogo()

opcion = st.radio("¿Qué quieres hacer?", ("✍️ Preguntar por texto", "📸 Analizar una foto de estampilla"))

if opcion == "✍️ Preguntar por texto":
    st.info("🎤 Para hablar: usa el micrófono de tu teclado al escribir")
    pregunta = st.text_input("Escribe tu pregunta:")
    if pregunta:
        with st.spinner("Consultando..."):
            respuesta = generar_respuesta_texto(pregunta, catalogo)
            st.success("✅ Respuesta:")
            st.write(respuesta)

else:
    archivo = st.file_uploader("Sube la foto de la estampilla", type=["jpg", "jpeg", "png"])
    if archivo:
        imagen = Image.open(archivo)
        st.image(imagen, caption="Foto subida", use_column_width=True)
        if st.button("🔍 Analizar estampilla"):
            with st.spinner("Examinando la imagen..."):
                resultado = analizar_imagen(imagen, catalogo)
                st.success("✅ Resultado del análisis:")
                st.write(resultado)

with st.expander("📋 Ver todo el catálogo"):
    for item in catalogo:
        campos = item["fields"]
        st.write(f"**{campos.get('Descripción', 'Sin nombre')}**")
        st.write(f"País: {campos.get('País', 'Desconocido')} | Año: {campos.get('Año', 'Desconocido')} | Precio: {campos.get('Precio', 'Sin precio')}")
        st.write("---")