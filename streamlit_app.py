from groq import Groq
import base64

# --- Configuración (todo igual) ---
client = Groq(api_key="TU_CLAVE_API_AQUI")

# --- 🔄 CAMBIOS REALIZADOS: ---
# 1. Modelo reemplazado por uno activo con soporte de visión
# 2. Imagen reducida: ajusta el valor de "max_width" para hacerla más pequeña
def reducir_imagen(ruta_imagen, max_width=800):
    """Reduce el tamaño de la imagen antes de enviarla"""
    from PIL import Image
    import io
    
    with Image.open(ruta_imagen) as img:
        # Calcula nueva altura manteniendo proporción
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img_redimensionada = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Guarda en buffer con calidad ajustada
        buffer = io.BytesIO()
        img_redimensionada.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

# --- Carga y prepara la imagen (mismo funcionamiento, más pequeña) ---
ruta_archivo = "tu_imagen.jpg"  # Mantén tu ruta original
imagen_base64 = reducir_imagen(ruta_archivo, max_width=600)  # Pon 400/500 si quieres aún más pequeña

# --- Solicitud a la API ---
respuesta = client.chat.completions.create(
    model="openai/gpt-oss-120b",  # ✅ Modelo activo vigente
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analiza detalladamente esta imagen:"},  # Mantén tu texto original
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{imagen_base64}"
                    }
                }
            ]
        }
    ],
    temperature=0.7,  # Mantén tus parámetros originales
    max_tokens=1024,
    top_p=1
)

# --- Muestra el resultado (igual que antes) ---
print(respuesta.choices[0].message.content)
