import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import io
import os

# ---------------------- CONFIGURACIÓN GENERAL ----------------------
st.set_page_config(
    page_title="Herramienta Completa de Imágenes",
    page_icon="🎨",
    layout="wide"
)

# Configuración segura de la clave API (sin escribirla directamente)
API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("⚠️ Falta configurar la clave API de Google. Revisa los pasos anteriores.")
    st.stop()

genai.configure(api_key=API_KEY)
modelo = genai.GenerativeModel("gemini-2.5-flash")

# ---------------------- FUNCIÓN 1: ANALIZAR IMAGEN ----------------------
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
        return f"Error al analizar: {str(e)}"

# ---------------------- FUNCIÓN 2: AGREGAR ESTAMPILLA / MARCA DE AGUA ----------------------
def generar_estampilla(imagen, texto, posicion, tamaño=30, opacidad=120):
    # Convertimos a formato compatible con transparencia
    img = imagen.convert("RGBA")
    capa_estampa = Image.new("RGBA", img.size, (255, 255, 255, 0))
    dibujo = ImageDraw.Draw(capa_estampa)

    # Cargar fuente (usa Arial si existe, si no la predeterminada)
    try:
        fuente = ImageFont.truetype("arial.ttf", tamaño)
    except:
        fuente = ImageFont.load_default(size=tamaño)

    # Calcular dimensiones del texto y la imagen
    ancho_texto, alto_texto = dibujo.textbbox((0, 0), texto, font=fuente)[2:4]
    ancho_img, alto_img = img.size
    margen = 20

    # Definir posición exacta
    if posicion == "Arriba izquierda":
        x, y = margen, margen
    elif posicion == "Arriba derecha":
        x, y = ancho_img - ancho_texto - margen, margen
    elif posicion == "Abajo izquierda":
        x, y = margen, alto_img - alto_texto - margen
    elif posicion == "Abajo derecha":
        x, y = ancho_img - ancho_texto - margen, alto_img - alto_texto - margen
    else:  # Centrado
        x, y = (ancho_img - ancho_texto) // 2, (alto_img - alto_texto) // 2

    # Dibujar la estampilla y unir capas
    dibujo.text((x, y), texto, fill=(255, 255, 255, opacidad), font=fuente)
    imagen_final = Image.alpha_composite(img, capa_estampa).convert("RGB")
    return imagen_final

# ---------------------- INTERFAZ DE USUARIO ----------------------
st.title("🎨 Analizador de Imágenes + Asistente de Estampillas")

# Separamos las funciones en pestañas claras
pestaña_analizar, pestaña_estampillas = st.tabs([
    "📷 Analizar Imagen",
    "🖌️ Asistente de Estampillas"
])

# ---------------------- PESTAÑA 1: ANALIZADOR ----------------------
with pestaña_analizar:
    st.subheader("Sube una imagen y obtén su descripción detallada")
    archivo_analizar = st.file_uploader(
        "Selecciona una imagen",
        type=["jpg", "jpeg", "png", "webp"],
        key="cargador_analizar"
    )

    if archivo_analizar is not None:
        imagen_analizar = Image.open(archivo_analizar)
        # Tamaño fijo mediano para no ocupar toda la pantalla
        st.image(
            imagen_analizar,
            caption="Imagen cargada",
            width=500
        )

        if st.button("🔍 Iniciar análisis", key="boton_analizar"):
            with st.spinner("La IA está examinando la imagen..."):
                resultado = analizar_imagen(imagen_analizar)
                if "Error" in resultado:
                    st.error(resultado)
                else:
                    st.success("✅ Análisis completado!")
                    st.subheader("Resultado:")
                    st.write(resultado)

# ---------------------- PESTAÑA 2: ESTAMPILLAS ----------------------
with pestaña_estampillas:
    st.subheader("Agrega tu marca de agua o estampilla personalizada")
    archivo_estampa = st.file_uploader(
        "Selecciona la imagen para modificar",
        type=["jpg", "jpeg", "png", "webp"],
        key="cargador_estampa"
    )

    if archivo_estampa is not None:
        imagen_original = Image.open(archivo_estampa)
        st.image(
            imagen_original,
            caption="Imagen original",
            width=500
        )

        # Opciones de configuración de la estampilla
        st.markdown("### ⚙️ Configura tu estampilla")
        texto_estampa = st.text_input("Texto que quieres agregar:", value="© Mi Marca Personal")
        posicion = st.selectbox(
            "Posición en la imagen:",
            ["Abajo derecha", "Abajo izquierda", "Arriba derecha", "Arriba izquierda", "Centrado"]
        )
        tamaño_texto = st.slider("Tamaño del texto:", min_value=10, max_value=80, value=32)
        transparencia = st.slider("Transparencia:", min_value=20, max_value=255, value=110)

        if st.button("✨ Aplicar estampilla", key="boton_aplicar_estampa"):
            with st.spinner("Añadiendo la estampilla..."):
                imagen_con_estampa = generar_estampilla(
                    imagen_original,
                    texto_estampa,
                    posicion,
                    tamaño_texto,
                    transparencia
                )
                st.success("✅ Estampilla agregada correctamente!")
                st.image(
                    imagen_con_estampa,
                    caption="Imagen con tu estampilla",
                    width=500
                )

                # Opción para descargar la imagen lista
                buffer_descarga = io.BytesIO()
                imagen_con_estampa.save(buffer_descarga, format="JPEG", quality=92)
                st.download_button(
                    label="💾 Descargar imagen final",
                    data=buffer_descarga.getvalue(),
                    file_name="imagen_con_estampilla.jpg",
                    mime="image/jpeg"
                )

# ---------------------- INFORMACIÓN ADICIONAL ----------------------
with st.expander("ℹ️ Ver modelos disponibles de Gemini"):
    if st.button("Cargar lista de modelos"):
        try:
            for modelo_disponible in genai.list_models():
                if "generateContent" in modelo_disponible.supported_generation_methods:
                    st.write(f"- {modelo_disponible.name}")
        except Exception as error:
            st.error(f"No se pudo cargar la lista: {str(error)}")