import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# ---------------------- CONFIGURACIÓN ----------------------
# Configuración de la página de Streamlit
st.set_page_config(
    page_title="Analizador de Imágenes",
    page_icon="📷",
    layout="wide"
)

# Tu clave API de Google AI
# Recuerda: puedes ponerla aquí o usar st.secrets en producción
API_KEY = "TU_CLAVE_API_AQUI"
genai.configure(api_key=API_KEY)

# ---------------------- FUNCIÓN DE ANÁLISIS ----------------------
def analizar_imagen(imagen):
    # Usamos el modelo disponible y estable: gemini-2.5-flash
    modelo = genai.GenerativeModel("gemini-2.5-flash")
    
    # Convertimos la imagen al formato que requiere la API
    img_byte_arr = io.BytesIO()
    imagen.save(img_byte_arr, format=imagen.format)
    img_bytes = img_byte_arr.getvalue()
    
    # Preparamos el contenido para el modelo
    contenido = [
        "Describe detalladamente todo lo que veas en esta imagen:",
        {"mime_type": f"image/{imagen.format.lower()}", "data": img_bytes}
    ]
    
    # Generamos la respuesta
    respuesta = modelo.generate_content(contenido)
    return respuesta.text

# ---------------------- INTERFAZ DE USUARIO ----------------------
st.title("📷 Analizador de Imágenes con IA")
st.subheader("Sube una imagen y obtén su descripción detallada")

# Subida de imagen
archivo_subido = st.file_uploader("Selecciona una imagen", type=["jpg", "jpeg", "png", "webp"])

if archivo_subido is not None:
    # Cargamos y mostramos la imagen (CORRECCIÓN: usamos width en lugar de use_column_width)
    imagen = Image.open(archivo_subido)
    st.image(
        imagen,
        caption="Imagen subida",
        width="stretch"  # ✅ Reemplazo correcto de use_column_width=True
    )

    # Botón para iniciar el análisis
    if st.button("🔍 Analizar imagen"):
        with st.spinner("Analizando la imagen, por favor espera..."):
            try:
                resultado = analizar_imagen(imagen)
                st.success("✅ Análisis completado!")
                st.subheader("Resultado:")
                st.write(resultado)
            except Exception as error:
                st.error(f"❌ Ocurrió un error: {str(error)}")
                st.info("Revisa que tu clave API sea válida y que tengas conexión a internet.")

# ---------------------- INFORMACIÓN ADICIONAL ----------------------
with st.expander("ℹ️ Ver modelos disponibles"):
    if st.button("Listar modelos de Gemini"):
        modelos_disponibles = genai.list_models()
        for m in modelos_disponibles:
            if "generateContent" in m.supported_generation_methods:
                st.write(f"- {m.name}")