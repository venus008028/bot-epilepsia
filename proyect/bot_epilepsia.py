# Importamos funciones personalizadas para conectar con Google Fit
from google_fit.fit_client import get_google_fit_service, get_heart_rate_last_hour
# Importamos asyncio para poder usar funciones asíncronas (funciones que se ejecutan sin bloquear el resto del código)
import asyncio
# Importamos la clase AsyncTeleBot que nos permite crear un bot de Telegram que trabaje de forma asíncrona
from telebot.async_telebot import AsyncTeleBot
# Importamos types que nos permite crear botones y otras herramientas de Telegram
from telebot import types
# Importamos logging, que nos permite mostrar mensajes en la consola para saber qué está haciendo el bot
import logging
# Importamos módulos del sistema para manejar archivos y terminar el programa si hace falta
import os
import sys
import time
# Importamos la clave de API de Telegram desde un archivo de configuración
from config import TOKEN
# Importamos la clave de API de Gemini desde un archivo de configuración
from gemini.gemini import obtener_respuesta_gemini


# === CONFIGURACIÓN INICIAL ===

# Creamos el bot usando el token
bot = AsyncTeleBot(TOKEN)

# Configuramos el sistema de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Creamos un logger específico para este archivo
logger = logging.getLogger(__name__)

# === ESTADOS DEL FLUJO DE CONFIGURACIÓN ===

# Lista con el orden de las preguntas al registrarse
ESTADOS = [
    "nombre", "enfermedad", "frecuencia", "medicamentos",
    "info_adicional", "contactos_emergencia", "ánimo", "id_telegram"
]

# Diccionario para saber en qué paso está cada usuario
usuarios = {}

# Diccionario para guardar los datos personales de cada usuario
datos_usuario = {}

# === TECLADO PRINCIPAL ===

def teclado_principal():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    botones = [
        types.KeyboardButton("/ver_ficha"),
        types.KeyboardButton("/crisis"),
        types.KeyboardButton("/gemini"),
        types.KeyboardButton("/ayuda")
    ]
    markup.add(*botones)
    return markup

# Teclado de emergencia
def teclado_emergencia():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("/contactar_emergencia"))
    markup.add(types.KeyboardButton("/cronometro"))
    markup.add(types.KeyboardButton("/volver"))
    return markup

# === COMANDO /VOLVER ===
@bot.message_handler(commands=['volver'])
async def cmd_volver(message):
    try:
        chat_id = message.chat.id
        await bot.send_message(
            chat_id,
            "Volviendo al menú principal...",
            parse_mode="Markdown",
            reply_markup=teclado_principal()
        )
    except Exception as e:
        logger.error(f"Error en cmd_volver: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " No pude volver al menú principal.")

# === COMANDO /CONTACTAR_EMERGENCIA ===
@bot.message_handler(commands=['contactar_emergencia'])
async def cmd_contactar_emergencia(message):
    try:
        chat_id = message.chat.id
        await bot.send_message(
            chat_id,
            "*Llama a emergencias al 112*\n\nEnviando tu ficha médica...",
            parse_mode="Markdown",
            reply_markup=teclado_emergencia()
        )
        # Llamamos a la función que muestra la ficha médica
        await cmd_ver_perfil(message)
    except Exception as e:
        logger.error(f"Error en cmd_contactar_emergencia: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " No pude enviar la información de contacto de emergencia.")
# === CRONÓMETRO ===
cronometro_activo = False

@bot.message_handler(commands=['cronometro'])
async def cmd_cronometro(message):
    global cronometro_activo
    try:
        chat_id = message.chat.id
        if cronometro_activo:
            await bot.send_message(chat_id, " Ya hay un cronómetro en ejecución. Por favor, detén el cronómetro actual antes de iniciar uno nuevo.")
            return
        cronometro_activo = True
        await bot.send_message(chat_id, " *Cronómetro iniciado*.\nEste cronómetro durará 5 minutos. El tiempo se actualizará cada segundo.")
        for i in range(5 * 60):
            if not cronometro_activo:
                await bot.send_message(chat_id, " El cronómetro ha sido detenido.")
                return
            minutes = i // 60
            seconds = i % 60
            time_remaining = f"{minutes:02}:{seconds:02}"
            await bot.send_message(chat_id, f" Tiempo transcurrido: {time_remaining}")
            await asyncio.sleep(1)
        await bot.send_message(chat_id, " *Han pasado 5 minutos. Es momento de contactar con emergencias.*")
        await bot.send_message(chat_id, "Llama a emergencias al 112")
    except Exception as e:
        logger.error(f"Error en cmd_cronometro: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al iniciar el cronómetro. Por favor, intenta nuevamente.")
    finally:
        cronometro_activo = False

# === COMANDO /STOP ===
# === COMANDO /STOP ===
@bot.message_handler(commands=['stop'])
async def cmd_stop(message):
    global cronometro_activo
    if cronometro_activo:
        cronometro_activo = False
        await bot.send_message(message.chat.id, " El cronómetro ha sido detenido.")
    else:
        await bot.send_message(message.chat.id, " No hay cronómetro en ejecución para detener.")

# === INICIO / REGISTRO DEL USUARIO ===
@bot.message_handler(commands=['start', 'help'])
async def cmd_start(message):
    try:
        chat_id = message.chat.id
        usuarios[chat_id] = {"estado": "nombre", "paso": 0}
        datos_usuario[chat_id] = {
            "nombre": "",
            "enfermedad": "",
            "frecuencia_crisis": "",
            "medicamentos": "",
            "info_adicional": "",
            "contactos_emergencia": "",
            "ánimo": "",
            "hora_reporte": "12:00",
            "id_telegram": "" # Inicializamos el campo para el ID
        }
        logger.info(f"Iniciando configuración para chat_id: {chat_id}")
        await bot.send_message(
            chat_id,
            " *Bienvenido al Asistente de Epilepsia*\n\n"
            "Vamos a crear tu ficha médica para emergencias. Responde:",
            parse_mode="Markdown"
        )
        await preguntar_siguiente_campo(chat_id)
        asyncio.create_task(monitor_ritmo_cardiaco(chat_id))
    except Exception as e:
        logger.error(f"Error en cmd_start: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al iniciar. Por favor, intenta nuevamente.")

async def preguntar_siguiente_campo(chat_id):
    try:
        estado_actual = usuarios[chat_id]["estado"]
        preguntas = {
            "nombre": " *Nombre completo:*",
            "enfermedad": "*¿Qué tipo de crisis epilépticas experimentas?*",
            "frecuencia": " *¿Con qué frecuencia ocurren tus crisis?*",
            "medicamentos": " *Medicamentos (dosis y frecuencia):*",
            "info_adicional": " *Información adicional relevante:*",
            "contactos_emergencia": " *Contactos de emergencia (nombre y teléfono):*",
            "ánimo": " *¿Cómo te sientes últimamente?*",
            "id_telegram": " *Tu ID de Telegram (puedes preguntarle a @userinfobot):*" # Nueva pregunta
        }
        if estado_actual in preguntas:
            await bot.send_message(chat_id, preguntas[estado_actual], parse_mode="Markdown")
        else:
            logger.error(f"Estado no reconocido: {estado_actual}")
            await bot.send_message(chat_id, " Hubo un error en el flujo. Por favor usa /start para reiniciar.")
    except Exception as e:
        logger.error(f"Error en preguntar_siguiente_campo: {e}", exc_info=True)
        await bot.send_message(chat_id, " Ocurrió un error. Por favor intenta nuevamente.")

# === VER PERFIL ===
@bot.message_handler(func=lambda m: m.text in ["Mi Perfil", "/perfil", "/ver_ficha"])
async def cmd_ver_perfil(message):
    try:
        chat_id = message.chat.id
        datos = datos_usuario.get(chat_id)
        if not datos:
            await bot.send_message(chat_id, " Primero debes configurar tu perfil con /start")
            return
        ficha = (
            f" *Tu Ficha Médica*\n\n"
            f" *Nombre:* {datos.get('nombre', 'No especificado')}\n"
            f" *Tipo de crisis:* {datos.get('enfermedad', 'No especificado')}\n"
            f" *Frecuencia:* {datos.get('frecuencia_crisis', 'No especificado')}\n"
            f" *Medicación:* {datos.get('medicamentos', 'No especificado')}\n"
            f" *Info adicional:* {datos.get('info_adicional', 'No especificado')}\n"
            f" *Contactos emergencia:* {datos.get('contactos_emergencia', 'No especificado')}\n"
            f" *Ánimo reciente:* {datos.get('ánimo', 'No especificado')}"
        )
        await bot.send_message(
            chat_id,
            ficha,
            parse_mode="Markdown",
            reply_markup=teclado_principal()
        )
    except Exception as e:
        logger.error(f"Error en cmd_ver_perfil: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al mostrar tu perfil.")

# === PROTOCOLO DE CRISIS ===

enviar_mensajes_emergencia_crisis = False # Variable global para controlar el envío de mensajes de crisis
id_emergencia = None # Variable global para guardar la ID de emergencia

@bot.message_handler(commands=['crisis', 'emergencia'])
async def cmd_crisis(message):
    global enviar_mensajes_emergencia_crisis
    global id_emergencia
    try:
        chat_id = message.chat.id
        await bot.send_message(chat_id, " *Protocolo de Emergencia Activado*...", parse_mode="Markdown", reply_markup=teclado_emergencia())

        user_info = datos_usuario.get(chat_id)
        if user_info and 'id_telegram' in user_info and user_info.get('nombre'):
            id_emergencia = user_info['id_telegram']
            nombre_usuario = user_info['nombre']
            await bot.send_message(id_emergencia, f"*¡Alerta de Crisis!* {nombre_usuario} ha activado el protocolo de emergencia.")
            await bot.send_message(chat_id, f"Se ha notificado a tu contacto de emergencia.")
            enviar_mensajes_emergencia_crisis = False # Desactivamos el envío continuo de mensajes después de la alerta inicial
        else:
            await bot.send_message(chat_id, "No se encontró la información necesaria de tu contacto de emergencia.")
            enviar_mensajes_emergencia_crisis = False
        await cmd_cronometro(message) # Inicia el cronómetro DESPUÉS de enviar la alerta

    except Exception as e:
        logger.error(f"Error en cmd_crisis: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " No pude activar el protocolo de emergencia.")

# === RECOGER DATOS DEL USUARIO ===
@bot.message_handler(func=lambda m: m.chat.id in usuarios and usuarios[m.chat.id]["estado"] in ESTADOS)
async def recoger_datos_usuario(message):
    try:
        chat_id = message.chat.id
        estado_actual = usuarios[chat_id]["estado"]
        texto = message.text.strip()
        logger.info(f"Recibiendo dato para {estado_actual}: {texto}")
        if estado_actual == "frecuencia":
            datos_usuario[chat_id]["frecuencia_crisis"] = texto
        else:
            datos_usuario[chat_id][estado_actual] = texto
        indice_actual = ESTADOS.index(estado_actual)
        if indice_actual < len(ESTADOS) - 1:
            siguiente_estado = ESTADOS[indice_actual + 1]
            usuarios[chat_id] = {"estado": siguiente_estado, "paso": indice_actual + 1}
            await preguntar_siguiente_campo(chat_id)
        else:
            del usuarios[chat_id]
            await bot.send_message(
                chat_id,
                "*¡Perfil completado con éxito!*\n\nAhora puedes usar todas las funciones del bot.",
                parse_mode="Markdown",
                reply_markup=teclado_principal()
            )
            logger.info(f"Flujo completado para chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error en recoger_datos_usuario: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al guardar tu información. Por favor intenta nuevamente.")

# === BUCLE PRINCIPAL ===
async def main():
    try:
        logger.info("Iniciando bot...")
        await bot.delete_webhook()
        await bot.polling(non_stop=True, timeout=60)
    except Exception as e:
        logger.error(f"Error en main(): {e}", exc_info=True)
        await asyncio.sleep(5)
        await main()

@bot.message_handler(commands=['info'])
async def cmd_info(message):
    try:
        info_message = (
            "Soy un chat bot programado para avisarte y a tus seres queridos "
            "cuando puedes estar sufriendo una posible crisis epiléptica.\n\n"
            "Además, cuento con una IA (Gemini) para responder a tus preguntas "
            "de salud a través del comando /gemini."
        )
        await bot.send_message(message.chat.id, info_message)
    except Exception as e:
        logger.error(f"Error en cmd_info: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al obtener la información. Por favor, intenta nuevamente.")

# === COMANDO /AYUDA ===
@bot.message_handler(commands=['ayuda'])
async def cmd_ayuda(message):
    try:
        ayuda_message = (
            "*Comandos disponibles:*\n\n"
            "/start - Iniciar conversación con el bot\n"
            "/info - Muestra información sobre el bot\n"
            "/crisis - Activa protocolo de emergencia\n"
            "/ayuda - Muestra opciones disponibles\n"
            "/ver_ficha - Consulta tu ficha médica\n"
            "/contactar_emergencia - Contacta a emergencias\n"
            "/cronometro - Inicia un cronómetro de 5 minutos\n"
            "/stop - Detiene todas las acciones activas\n"
            "/gemini - Inicia conversación con la IA"
        )
        await bot.send_message(message.chat.id, ayuda_message)
    except Exception as e:
        logger.error(f"Error en cmd_ayuda: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al mostrar los comandos. Por favor, intenta nuevamente.")

# === COMANDO /GEMINI ===
@bot.message_handler(commands=['gemini'])
async def cmd_gemini(message):
    chat_id = message.chat.id
    await bot.send_message(
        chat_id,
        "Escribe tu duda relacionada con tu salud o tus crisis y te daré una recomendación general:"
    )
    @bot.message_handler(func=lambda m: m.chat.id == chat_id)
    async def recibir_duda(mensaje):
        pregunta = mensaje.text
        respuesta = obtener_respuesta_gemini(pregunta)
        await bot.send_message(chat_id, f"Gemini dice:\n\n{respuesta}")

async def probar_google_fit(chat_id):
    try:
        service = get_google_fit_service()
        if service:
            await bot.send_message(chat_id, "¡Conexión con Google Fit exitosa")
            heart_rate_data = get_heart_rate_last_hour(service)
            if heart_rate_data:
                await bot.send_message(chat_id, f"Ritmo cardíaco de la última hora (ejemplo): {heart_rate_data}")
            else:
                await bot.send_message(chat_id, "No se encontraron datos de ritmo cardíaco en la última hora.")
        else:
            await bot.send_message(chat_id, "No se pudo conectar con Google Fit.")
    except Exception as e:
        logger.error(f"Error al probar Google Fit: {e}", exc_info=True)
        await bot.send_message(chat_id, f"Ocurrió un error al intentar conectar con Google Fit: {e}")

@bot.message_handler(commands=['probar_fit'])
async def cmd_probar_fit(message):
    await probar_google_fit(message.chat.id)

# === BUCLE DE MONITORIZACIÓN (EJEMPLO INICIAL) ===
async def analizar_datos_y_activar_emergencia(chat_id):
    try:
        service = get_google_fit_service()
        if service:
            ritmos_cardiacos = get_heart_rate_last_hour(service)
            if ritmos_cardiacos:
                # --- Lógica MUY BÁSICA de ejemplo para detectar un pico ---
                if len(ritmos_cardiacos) > 5:
                    ultimos_cinco = ritmos_cardiacos[-5:]
                    if all(x > 90 for x in ultimos_cinco): # Si los últimos 5 latidos son altos (ejemplo)
                        await cmd_crisis(chat_id)
                        logger.warning(f"¡Posible pico detectado para chat_id: {chat_id}!")
            else:
                logger.info("No hay datos de ritmo cardíaco para analizar.")
        else:
            logger.error("No se pudo obtener el servicio de Google Fit para el análisis.")
    except Exception as e:
        logger.error(f"Error al analizar datos: {e}", exc_info=True)

async def bucle_de_monitorizacion(chat_id):
    while True:
        await analizar_datos_y_activar_emergencia(chat_id)
        await asyncio.sleep(60) # Esperar 60 segundos antes de volver a analizar

@bot.message_handler(commands=['pulso'])
async def cmd_pulso(message):
    chat_id = message.chat.id
    try:
        service = get_google_fit_service()
        if service:
            latest_heart_rate = get_heart_rate_last_hour(service)
            if latest_heart_rate:
                await bot.send_message(chat_id, f"Tu ritmo cardíaco actual es: {latest_heart_rate} BPM")
            else:
                await bot.send_message(chat_id, "No se encontraron datos recientes de ritmo cardíaco.")
        else:
            await bot.send_message(chat_id, "No se pudo conectar con Google Fit.")
    except Exception as e:
        logger.error(f"Error al obtener el pulso: {e}", exc_info=True)
        await bot.send_message(chat_id, f"Ocurrió un error al obtener tu ritmo cardíaco: {e}")



async def monitor_ritmo_cardiaco(chat_id):
    global id_emergencia
    logger.info("¡El monitor de ritmo cardíaco se ha iniciado!")
    while True:
        try:
            service = get_google_fit_service()
            if service:
                latest_heart_rate = get_heart_rate_last_hour(service)
                if latest_heart_rate:
                    logger.info(f"Ritmo cardíaco: {latest_heart_rate} BPM")
                    ritmo_alto_peligroso = 100
                    ritmo_bajo_peligroso = 50

                    if latest_heart_rate > ritmo_alto_peligroso:
                        await bot.send_message(chat_id, f"*¡Alerta!* Ritmo cardíaco alto: {latest_heart_rate} BPM", parse_mode="Markdown")
                        if id_emergencia:
                            user_info = datos_usuario.get(chat_id)
                            nombre_usuario = user_info.get('nombre', 'Alguien') if user_info else 'Alguien'
                            await bot.send_message(id_emergencia, f"*¡Alerta de Ritmo Cardíaco Alto!* de {nombre_usuario}: {latest_heart_rate} BPM")
                    elif latest_heart_rate < ritmo_bajo_peligroso and latest_heart_rate > 0:
                        await bot.send_message(chat_id, f"*¡Alerta!* Ritmo cardíaco bajo: {latest_heart_rate} BPM", parse_mode="Markdown")
                        if id_emergencia:
                            user_info = datos_usuario.get(chat_id)
                            nombre_usuario = user_info.get('nombre', 'Alguien') if user_info else 'Alguien'
                            await bot.send_message(id_emergencia, f"*¡Alerta de Ritmo Cardíaco Bajo!* de {nombre_usuario}: {latest_heart_rate} BPM")
                else:
                    logger.info("No hay datos recientes de ritmo cardíaco para la alerta.")
            else:
                logger.error("No se pudo conectar con Google Fit para la alerta.")
        except Exception as e:
            logger.error(f"Error al monitorear el pulso para la alerta: {e}", exc_info=True)
        await asyncio.sleep(15)

@bot.message_handler(commands=['start', 'help'])
async def cmd_start(message):
    try:
        chat_id = message.chat.id
        usuarios[chat_id] = {"estado": "nombre", "paso": 0}
        datos_usuario[chat_id] = {
            "nombre": "",
            "enfermedad": "",
            "frecuencia_crisis": "",
            "medicamentos": "",
            "info_adicional": "",
            "contactos_emergencia": "",
            "ánimo": "",
            "hora_reporte": "12:00",
            "id_telegram": ""
        }
        logger.info(f"Iniciando configuración para chat_id: {chat_id}")
        await bot.send_message(
            chat_id,
            " *Bienvenido al Asistente de Epilepsia*\n\n"
            "Vamos a crear tu ficha médica para emergencias. Responde:",
            parse_mode="Markdown"
        )
        await preguntar_siguiente_campo(chat_id)
        asyncio.create_task(monitor_ritmo_cardiaco(chat_id))
    except Exception as e:
        logger.error(f"Error en cmd_start: {e}", exc_info=True)
        await bot.send_message(message.chat.id, " Ocurrió un error al iniciar. Por favor, intenta nuevamente.")

@bot.message_handler(func=lambda message: enviar_mensajes_emergencia_crisis and message.from_user.id != bot.user.id)
async def enviar_mensajes_crisis(message):
    global id_emergencia
    user_info = datos_usuario.get(message.chat.id)
    if id_emergencia and user_info and 'nombre' in user_info:
        nombre_usuario = user_info['nombre']
        try:
            await bot.send_message(id_emergencia, f"Mensaje de crisis de {nombre_usuario} (ID: {message.from_user.id}):\n{message.text}")
        except Exception as e:
            logger.error(f"Error al enviar mensaje de crisis: {e}", exc_info=True)

if __name__ == '__main__':
    try:
        logger.info("Iniciando bot de epilepsia...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error irrecoverable: {e}", exc_info=True)
        sys.exit(1)