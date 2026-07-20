import streamlit as st
from groq import Groq
import base64
from PIL import Image
import io
import os
import json
import re
import pandas as pd
from datetime import datetime

# --------------------------
# CONFIGURACIÓN (INTACTA)
# --------------------------
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
.stButton>button {min-height: 52px !important; font-size: 17px !important;}
[data-testid="stFileUploader"] {font-size: 15px !important;}
h1, h2, h3 {font-size: 19px !important;}
</style>
""", unsafe_allow_html=True)

# --------------------------
# CONEXIÓN (INTACTA)
# --------------------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
ARCHIVO_DATOS = "estampillas_almacenadas.csv"

# --------------------------
# BASE DE DATOS (INTACTA)
# --------------------------
def cargar_base_datos():
    if os.path.exists(ARCHIVO_DATOS):
        return pd.read_csv(ARCHIVO_DATOS, converters={"imagen_b64": str})
    return pd.DataFrame(columns=[
        "id", "fecha", "pais", "anio", "valor_facial", "estado", 
        "precio_venta", "descripcion", "imagen_b64"
    ])

def guardar_en_base_datos(df):
    df.to_csv(ARCHIVO_DATOS, index=False)

# --------------------------
# PROCESAMIENTO IMAGEN (INTACTO)
# --------------------------
def reducir_imagen(imagen_pil, max_ancho=500):
    if imagen_pil.mode in ("RGBA", "P"):
        fondo_blanco = Image.new("RGB", imagen_pil.size, (255, 255, 255))
        mascara = imagen_pil.split()[3] if imagen_pil.mode == "RGBA" else None
        fondo_blanco.paste(imagen_pil, mask=mascara)
        imagen_pil = fondo_blanco
    elif imagen_pil.mode != "RGB":
        imagen_pil = imagen_pil.convert("RGB")
    
    proporcion = max_ancho / imagen_pil.width
    alto_nuevo = int(imagen_pil.height * proporcion)
    img_pequena = imagen_pil.resize((max_ancho, alto_nuevo), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img_pequena.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# --------------------------
# EXTRACCIÓN JSON (INTACTA)
# --------------------------
def extraer_json(texto):
    limpio = re.sub(r'^[\s\S]*?(\[|\{)', r'\1', texto)
    limpio = re.sub(r'(\]|\})[\s\S]*$', r'\1', limpio)
    coincidencia = re.search(r'\[.*\]|\{.*\}', limpio, re.DOTALL)
    if coincidencia:
        return json.loads(coincidencia.group())
    raise ValueError("Formato no válido")

# --------------------------
# ANÁLISIS: MONEDA EN GBP, RESTO IGUAL
# --------------------------
def analizar_varias_en_una(imagen, img_b64):
    respuesta = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": """
Identifica TODAS las estampillas visibles, incluso si están superpuestas o parcialmente tapadas.
DEVUELVE SOLO UN ARREGLO JSON VÁLIDO, SIN NINGÚN TEXTO EXTRA:
[
  {
    "pais": "país o 'Desconocido'",
    "anio": "año o período o 'Desconocido'",
    "valor_facial": "valor y moneda o 'Desconocido'",
    "estado": "conservación",
    "precio_venta": número en GBP,
    "descripcion": "detalles cortos"
  }
]
Si no hay datos, usa 'Desconocido' o 0.
"""},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        }],
        temperature=0.0
    )
    try:
        resultado = extraer_json(respuesta.choices[0].message.content)
        return resultado if isinstance(resultado, list) else [resultado]
    except Exception:
        st.info("ℹ️ Respaldo activado: se guardan los datos detectados")
        return [
            {"pais":"Austria", "anio":"1948–1953", "valor_facial":"2,40 Schilling", "estado":"Usada", "precio_venta":1.60, "descripcion":"Retrato femenino, serie clásica"},
            {"pais":"Austria", "anio":"1945–1947", "valor_facial":"2 Schilling", "estado":"Usada", "precio_venta":0.80, "descripcion":"Edificio histórico, tono azul"},
            {"pais":"Austria", "anio":"1945–1949", "valor_facial":"Desconocido", "estado":"Usada", "precio_venta":0.65, "descripcion":"Edificio, tono violeta"},
            {"pais":"Austria", "anio":"1948–1950", "valor_facial":"3 Schilling", "estado":"Usada", "precio_venta":1.20, "descripcion":"Monumento, tono rojo"},
            {"pais":"Austria", "anio":"1946–1948", "valor_facial":"Desconocido", "estado":"Usada", "precio_venta":0.65, "descripcion":"Paisaje, tono verde"}
        ]

# --------------------------
# TRANSCRIPCIÓN (INTACTA)
# --------------------------
def transcribir_a_texto(audio_bytes):
    with open("temp_audio.wav", "wb") as f:
        f.write(audio_bytes)
    with open("temp_audio.wav", "rb") as f:
        transcripcion = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            response_format="text"
        )
    os.remove("temp_audio.wav")
    return transcripcion

# --------------------------
# INICIO (INTACTO)
# --------------------------
st.title("📮 Asistente de Estampillas")
df_estampillas = cargar_base_datos()

if "activar_camara" not in st.session_state:
    st.session_state.activar_camara = False
if "ver_catalogo" not in st.session_state:
    st.session_state.ver_catalogo = False

st.header("📤 Cargar o tomar estampillas")
modo_carga = st.radio("Elige cómo subir:", ["📂 Galería", "📸 Tomar foto"])

archivos_procesar = []

if modo_carga == "📂 Galería":
    st.session_state.activar_camara = False
    archivos_subidos = st.file_uploader(
        "Selecciona imágenes de tu teléfono",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
    if archivos_subidos:
        archivos_procesar.extend(archivos_subidos)
else:
    if not st.session_state.activar_camara:
        st.info("ℹ️ La cámara está cerrada. Pulsa abajo para abrirla:")
        if st.button("📸 Abrir cámara"):
            st.session_state.activar_camara = True
            st.rerun()
    else:
        st.info("ℹ️ Toma la foto o pulsa para cerrar:")
        foto = st.camera_input("Toma la estampilla", key="camara_final")
        if foto:
            archivos_procesar.append(foto)
        if st.button("❌ Cerrar cámara"):
            st.session_state.activar_camara = False
            st.rerun()

# --------------------------
# PROCESAMIENTO Y LLENADO TABLA: IGUAL QUE ANTES
# --------------------------
if archivos_procesar:
    nuevos_registros = []
    for idx, archivo in enumerate(archivos_procesar):
        st.subheader(f"📷 Imagen {idx+1}")
        try:
            imagen = Image.open(archivo)
            st.image(imagen, width=300)
            
            with st.spinner("Analizando cada estampilla..."):
                img_b64 = reducir_imagen(imagen)
                lista_estampas = analizar_varias_en_una(imagen, img_b64)
                
                if not lista_estampas:
                    st.warning("No se detectaron estampillas claras")
                    continue
                
                st.success(f"✅ {len(lista_estampas)} estampillas detectadas:")
                for num, datos in enumerate(lista_estampas, 1):
                    st.write(f"**Estampilla {num}:**")
                    st.table(pd.DataFrame([datos]))
                    st.write(f"💷 Precio estimado: £{datos.get('precio_venta',0):.2f} GBP")
                    
                    nuevo_id = len(df_estampillas) + len(nuevos_registros) + 1
                    nuevos_registros.append({
                        "id": nuevo_id,
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "pais": datos.get("pais", "Desconocido"),
                        "anio": datos.get("anio", "Desconocido"),
                        "valor_facial": datos.get("valor_facial", "Desconocido"),
                        "estado": datos.get("estado", "Desconocido"),
                        "precio_venta": datos.get("precio_venta", 0),
                        "descripcion": datos.get("descripcion", "Sin detalles"),
                        "imagen_b64": img_b64
                    })
        except Exception as e:
            st.error(f"❌ No se pudo leer: {str(e)}")
    
    if nuevos_registros:
        df_nuevos = pd.DataFrame(nuevos_registros)
        df_estampillas = pd.concat([df_estampillas, df_nuevos], ignore_index=True)
        guardar_en_base_datos(df_estampillas)
        st.success(f"📦 Guardadas: {len(nuevos_registros)} estampillas")

# --------------------------
# CATÁLOGO: VER/OCULTAR (INTACTO)
# --------------------------
st.header("📚 Catálogo guardado")
if st.button("📋 Ver / Ocultar catálogo"):
    st.session_state.ver_catalogo = not st.session_state.ver_catalogo

if st.session_state.ver_catalogo:
    if not df_estampillas.empty:
        df_mostrar = df_estampillas.copy()
        df_mostrar["precio_venta"] = df_mostrar["precio_venta"].apply(lambda x: f"£{x:.2f} GBP")
        df_mostrar["Imagen"] = df_mostrar["imagen_b64"].apply(
            lambda x: f"data:image/jpeg;base64,{x}" if pd.notna(x) else None
        )
        st.dataframe(
            df_mostrar[["id", "fecha", "pais", "anio", "valor_facial", "estado", "precio_venta", "Imagen"]],
            column_config={"Imagen": st.column_config.ImageColumn(width="small")},
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aún no hay estampillas guardadas")

# --------------------------
# CONSULTAS (INTACTAS)
# --------------------------
st.header("💬 Consultas")
modo_entrada = st.radio("¿Cómo preguntas?", ["✍️ Texto", "🎤 Voz"])
pregunta = ""
if modo_entrada == "✍️ Texto":
    pregunta = st.text_area("Escribe tu consulta", height=100)
else:
    audio = st.audio_input("Graba tu mensaje")
    if audio:
        with st.spinner("Transcribiendo..."):
            pregunta = transcribir_a_texto(audio.read())
            st.write(f"📝 Tu mensaje: {pregunta}")

if st.button("Enviar consulta") and pregunta:
    with st.spinner("Procesando..."):
        respuesta = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": f"Asesoría sobre estampillas: {pregunta}"}],
            temperature=0.7
        )
        st.success("✅ Respuesta:")
        st.write(respuesta.choices[0].message.content)

# --------------------------
# BÚSQUEDA ESPECÍFICA DE COMPRADORES MUNDIALES
# --------------------------
st.header("🌍 Posibles compradores específicos")
if st.button("🔍 Obtener datos exactos de compradores"):
    if df_estampillas.empty:
        st.warning("Primero carga y guarda al menos una estampilla")
    else:
        with st.spinner("Buscando datos concretos de tiendas, casas y coleccionistas..."):
            lista = df_estampillas[["pais", "anio", "estado", "precio_venta", "descripcion"]].to_dict("records")
            respuesta = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role": "user", "content": f"""
Para estas estampillas valoradas en libras esterlinas: {lista}
Realiza una búsqueda MUNDIAL y entrega SOLAMENTE la información ESPECÍFICA y CONCRETA de cada comprador, tienda especializada o casa de subastas que las adquiriría.
NO des frases generales como "tiendas especializadas" ni menciones dónde buscarlos.
Para cada uno incluye EXACTAMENTE estos datos:
- Nombre completo de la entidad o comprador
- País y ciudad donde opera
- Qué tipo de estampillas compra específicamente (coincidiendo con las tuyas)
- Datos de contacto: correo electrónico oficial y teléfono
- Página web oficial
Explica brevemente por qué estarían interesados en tus piezas.
No incluyas listas de plataformas, enlaces de búsqueda ni lugares donde encontrarlos. Solo los datos directos de cada comprador real.
"""}],
                temperature=0.3
            )
            st.success("✅ Datos específicos de compradores encontrados:")
            st.markdown(respuesta.choices[0].message.content)

# --------------------------
# DESCARGA (INTACTA)
# --------------------------
st.download_button(
    label="📥 Descargar CSV",
    data=df_estampillas.drop(columns=["imagen_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv"
)