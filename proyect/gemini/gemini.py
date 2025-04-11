from google.generativeai import configure, GenerativeModel

# 🔑 Clave API directamente (sólo para pruebas, no recomendado en producción)
GEMINI_API_KEY = "AIzaSyCpVA9s-Du158k3yE5Ru_7plRKVCX9lyA4"

# Configurar la API
configure(api_key=GEMINI_API_KEY)

model = GenerativeModel('gemini-2.0-flash')

# Función para obtener respuesta
def obtener_respuesta_gemini(mensaje_usuario):
    try:
        respuesta = model.generate_content(mensaje_usuario)
        return respuesta.text
    except Exception as e:
        print("Error con Gemini:", e)
        return "Lo siento, hubo un error al generar la respuesta con Gemini."