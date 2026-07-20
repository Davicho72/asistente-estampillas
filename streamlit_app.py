import streamlit as st
from groq import Groq
import pandas as pd
from PIL import Image
import io

# ---------------------- CONFIGURACIÓN INICIAL ----------------------
st.set_page_config(page_title="Asistente de Estampillas", layout="wide")

# CLAVE DE GROQ (YA CONFIGURADA)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ---------------------- TÍTULO Y PRESENTACIÓN ----------------------
st.title("📦 Asistente para Gestión y Valoración de Estampillas")
st.subheader("Análisis detallado, conservación y valoración en Libras Esterlinas (£)")

# ---------------------- SECCIÓN DE ANÁLISIS ----------------------
st.header("🔍 Analizar Estampilla")
archivo_imagen = st.file_uploader("Sube la imagen de la estampilla", type=["jpg", "jpeg", "png"])

if archivo_imagen is not None:
    imagen = Image.open(archivo_imagen)
    st.image(imagen, caption="Estampilla cargada", use_column_width=True)

    with st.spinner("Analizando la estampilla..."):
        # Convertir imagen a bytes
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG")
        imagen_bytes = buffer.getvalue()

        # Solicitud a Groq
        respuesta = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analiza esta estampilla y devuelve: país, año aproximado, tema, estado de conservación, valor estimado en Libras Esterlinas (£) y observaciones importantes. Usa formato claro y estructurado."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{archivo_imagen.getvalue().decode('latin1')}"}}
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=1500
        )

        resultado = respuesta.choices[0].message.content
        st.markdown("### 📋 Resultado del Análisis")
        st.write(resultado)

# ---------------------- BASE DE DATOS Y GRÁFICOS ----------------------
st.header("📊 Registro y Valoración")

# DATOS DE EJEMPLO (MANTENEMOS ESTRUCTURA, CAMBIAMOS MONEDA)
datos_estampillas = pd.DataFrame({
    "Nombre": ["Estampilla España 1950", "Estampilla Reino Unido 1965", "Estampilla Francia 1972"],
    "Año": [1950, 1965, 1972],
    "Estado": ["Muy Bueno", "Bueno", "Regular"],
    "Valor Estimado (£)": [125.50, 82.75, 34.20]
})

st.dataframe(datos_estampillas, use_container_width=True)

# GRÁFICA ORIGINAL SIN CAMBIOS DE DISEÑO, SOLO ETIQUETA DE MONEDA
st.subheader("Valor por Estado de Conservación")
st.bar_chart(
    datos_estampillas.groupby("Estado")["Valor Estimado (£)"].mean(),
    x_label="Estado de Conservación",
    y_label="Valor Promedio (£)",
    color="#1f77b4"
)

# ---------------------- NOTAS ----------------------
st.info("💡 Todos los valores se muestran en **Libras Esterlinas (£ - GBP)**. Si necesitas ajustar alguna cifra o formato, avísame sin modificar el resto.")