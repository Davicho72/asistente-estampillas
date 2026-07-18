import streamlit as st
from groq import Groq
import base64
from PIL import Image
import io
import os

# ✅ Lee la clave de Render de forma segura
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ✅ Función para reducir la imagen (igual que antes)
def reducir_imagen(imagen_pil, max_ancho=600):
    proporcion = max_ancho / imagen_pil.width
    alto_nuevo = int(imagen_pil.height * proporcion)
    img_pequena = imagen_pil.resize((max_ancho, alto_nuevo), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img_pequena.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# 🖼️ Interfaz para subir imagen
st.title("Analizador de Estampillas")
archivo_subido = st.file_uploader("Sube tu imagen aquí", type=["jpg", "jpeg", "png"])

if archivo_subido is not None:
    # Carga la imagen subida sin usar archivos locales
    imagen = Image.open(archivo_subido)
    st.image(imagen, caption="Imagen subida", width=400)

    # Convierte y reduce la imagen
    imagen_codificada = reducir_imagen(imagen)

    # Llamada a la API con el modelo correcto
    with st.spinner("Analizando la imagen..."):
        respuesta = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analiza detalladamente esta estampilla:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_codificada}"}}
                    ]
                }
            ]
        )

    # Muestra el resultado
    st.success("✅ Análisis terminado:")
    st.write(respuesta.choices[0].message.content)

else:
    st.info("Sube una imagen para empezar.")
