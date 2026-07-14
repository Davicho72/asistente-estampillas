import streamlit as st
import requests
import google.generativeai as genai
from PIL import Image
import os

# -------------------------- CARGA DE VARIABLES DE ENTORNO --------------------------
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# -------------------------- VALIDACIÓN DE CREDENCIALES --------------------------
if not GEMINI_API_KEY:
    st.error("⚠️ Falta configurar la clave API de Google (GOOGLE_API_KEY)")
    st.stop()

if not all([AIRTABLE_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
    st.error("⚠️ Faltan variables de configuración de Airtable")
    st.stop()

# Configuración de Gemini
genai.configure(api_key=GEMINI_API_KEY)
modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
modelo_imagen = genai.GenerativeModel("gemini-1.5-flash")

# Configuración de la página
st.set_page_config(page_title="Asistente Estampillas eBay", layout="centered")

# -------------------------- FUNCIÓN PARA LEER EL CATÁLOGO --------------------------
def leer_catalogo():
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    # ✅ Usa las variables, no nombres fijos
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        respuesta.raise_for_status()
        return respuesta.json().get("records", [])
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error de acceso: {respuesta.status_code} - Revisa permisos del token o ID de tabla")
        return []
    except Exception as e:
        st.error(f"❌ Error al conectar con Airtable: {str(e)}")
        return []

# -------------------------- FUNCIÓN PARA GENERAR RESPUESTAS --------------------------
def generar_respuesta_texto(pregunta, catalogo):
    contexto = "Eres un asistente de ventas de estampillas para eBay. Responde claro y amable, usando SOLO estos datos del catálogo:\n"
    
    for item in catalogo:
        campos = item.get("fields", {})
        contexto += f"- Nombre: {campos.get('Name', 'Sin nombre')} | Precio: {campos.get('Costo de envío', 'Sin precio')} | Envío: {campos.get('Detalles de envío', 'Consultar')} | Venta: {campos.get('Reglas de venta', 'Consultar')}\n"
    
    contexto += "\nSi no encuentras la información, di amablemente que lo consultarás pronto."
    
    try:
        respuesta = modelo_texto.generate_content(f"{contexto}\n\nPregunta: {pregunta}")
        respuesta.resolve()
        return respuesta.text
    except Exception as e:
        return f"❌ No pude generar la respuesta: {str(e)}"

# -------------------------- FUNCIÓN PARA ANALIZAR IMÁGENES --------------------------
def analizar_imagen(imagen, catalogo):
    contexto = "Eres experto en filatelia. Analiza la estampilla: país, año aproximado, diseño, valor facial y estado. Luego compara con el catálogo:\n"
    
    for item in catalogo:
        campos = item.get("fields", {})
        contexto += f"- {campos.get('Name', 'Sin nombre')} | Precio: {campos.get('Costo de envío', 'Sin precio')}\n"
    
    try:
        respuesta = modelo_imagen.generate_content([contexto, imagen])
        respuesta.resolve()
        return respuesta.text
    except Exception as e:
        return f"❌ No pude analizar la imagen: {str(e)}"

# -------------------------- INTERFAZ DE USUARIO --------------------------
st.title("📮 Asistente de Ventas - Estampillas")
st.subheader("Consulta tu catálogo y analiza estampillas con IA")

# Cargar catálogo una sola vez
catalogo = leer_catalogo()

opcion = st.radio("¿Qué quieres hacer?", ("✍️ Preguntar por texto", "📸 Analizar una foto de estampilla"))

if opcion == "✍️ Preguntar por texto":
    st.info("🎤 Para dictar: usa el micrófono de tu teclado al escribir")
    pregunta = st.text_input("Escribe tu pregunta:")
    if pregunta:
        with st.spinner("Buscando y generando respuesta..."):
            st.success("✅ Respuesta:")
            st.write(generar_respuesta_texto(pregunta, catalogo))

else:
    archivo = st.file_uploader("Sube la foto", type=["jpg", "jpeg", "png"])
    if archivo:
        imagen = Image.open(archivo)
        st.image(imagen, caption="Estampilla cargada", use_column_width=True)
        if st.button("🔍 Analizar estampilla"):
            with st.spinner("Examinando detalles..."):
                st.success("✅ Resultado:")
                st.write(analizar_imagen(imagen, catalogo))

# Mostrar catálogo completo
with st.expander("📋 Ver todo el catálogo"):
    if catalogo:
        for item in catalogo:
            campos = item.get("fields", {})
            st.write(f"**{campos.get('Name', 'Sin nombre')}**")
            st.write(f"Precio: {campos.get('Costo de envío', 'Sin precio')} | Envío: {campos.get('Detalles de envío', 'Consultar')}")
            st.write("---")
    else:
        st.info("No hay datos para mostrar.")