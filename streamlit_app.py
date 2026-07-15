import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import io
import os

# ---------------------- CONFIGURACIÓN ----------------------
st.set_page_config(
    page_title="Herramienta de Imágenes",
    page_icon="🎨",
    layout="wide"
)

# ✅ Lectura segura compatible con Render y local
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    try:
        API_KEY = st.secrets.get("GEMINI_API_KEY")
    except FileNotFoundError:
        API_KEY = None

if not API_KEY:
    st.error("⚠️ Falta configurar la variable GEMINI_API_KEY en Render.")
    st.stop()

genai.configure(api_key=API_KEY)
modelo = genai.GenerativeModel("gemini-2.5-flash")

# ---------------------- FUNCIÓN ANALIZAR IMAGEN ----------------------
def analizar_imagen(imagen):
    try:
        img_byte_arr = io.BytesIO()
        imagen.save(img_byte_arr, format=imagen.format or "JPEG")
        contenido = [
            "Describe detalladamente todo lo que veas en esta imagen:",
            {"mime_type": f"image/{(imagen.format or 'jpeg').lower()}", "data": img_byte_arr.getvalue()}
        ]
        respuesta = modelo.generate_content(contenido)
        respuesta.resolve()
        return respuesta.text
    except Exception as e:
        return f"Error: {str(e)}"

# ---------------------- FUNCIÓN ESTAMPILLA ----------------------
def generar_estampilla(imagen, texto, posicion, tamaño=30, opacidad=120):
    img = imagen.convert("RGBA")
    capa = Image.new("RGBA", img.size, (255,255,255,0))
    dibujo = ImageDraw.Draw(capa)

    try:
        fuente = ImageFont.truetype("arial.ttf", tamaño)
    except:
        fuente = ImageFont.load_default(size=tamaño)

    ancho_texto, alto_texto = dibujo.textbbox((0,0), texto, font=fuente)[2:4]
    ancho_img, alto_img = img.size
    margen = 20

    if posicion == "Arriba izquierda":
        x, y = margen, margen
    elif posicion == "Arriba derecha":
        x, y = ancho_img - ancho_texto - margen, margen
    elif posicion == "Abajo izquierda":
        x, y = margen, alto_img - alto_texto - margen
    elif posicion == "Abajo derecha":
        x, y = ancho_img - ancho_texto - margen, alto_img - alto_texto - margen
    else:
        x, y = (ancho_img - ancho_texto)//2, (alto_img - alto_texto)//2

    dibujo.text((x, y), texto, fill=(255,255,255,opacidad), font=fuente)
    final = Image.alpha_composite(img, capa).convert("RGB")
    return final

# ---------------------- INTERFAZ ----------------------
st.title("🎨 Analizador + Estampillas")

pestaña1, pestaña2 = st.tabs(["📷 Analizar Imagen", "🖌️ Asistente de Estampillas"])

# Pestaña 1
with pestaña1:
    st.subheader("Sube una imagen para describirla")
    archivo = st.file_uploader("Selecciona imagen", type=["jpg","jpeg","png","webp"], key="analizar")

    if archivo:
        img = Image.open(archivo)
        st.image(img, caption="Imagen cargada", width=500)

        if st.button("🔍 Analizar", key="boton1"):
            with st.spinner("Procesando..."):
                res = analizar_imagen(img)
                st.success("✅ Listo!")
                st.write(res)

# Pestaña 2
with pestaña2:
    st.subheader("Agrega tu marca de agua")
    archivo_estampa = st.file_uploader("Selecciona imagen", type=["jpg","jpeg","png","webp"], key="estampa")

    if archivo_estampa:
        img_original = Image.open(archivo_estampa)
        st.image(img_original, caption="Imagen original", width=500)

        texto = st.text_input("Texto:", value="© Mi Marca")
        pos = st.selectbox("Posición:", ["Abajo derecha", "Abajo izquierda", "Arriba derecha", "Arriba izquierda", "Centrado"])
        tam = st.slider("Tamaño:", 10, 80, 30)
        opac = st.slider("Transparencia:", 20, 255, 100)

        if st.button("✨ Aplicar estampilla", key="boton2"):
            with st.spinner("Aplicando..."):
                img_final = generar_estampilla(img_original, texto, pos, tam, opac)
                st.success("✅ Hecho!")
                st.image(img_final, caption="Imagen final", width=500)

                buffer = io.BytesIO()
                img_final.save(buffer, format="JPEG", quality=90)
                st.download_button(
                    label="💾 Descargar",
                    data=buffer.getvalue(),
                    file_name="imagen_final.jpg",
                    mime="image/jpeg"
                )

# Ver modelos
with st.expander("ℹ️ Modelos disponibles"):
    if st.button("Cargar modelos"):
        try:
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    st.write(f"- {m.name}")
        except Exception as e:
            st.error(f"Error: {str(e)}")