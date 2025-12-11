import discord
from discord.ext import commands, tasks
from pytz import timezone
import random
import datetime
import asyncio

# --- CONFIG USUARIOS / MENSAJES INTERACTIVOS ---

ROCHI_ID = 749116237472071772  
CAM_ID = 737370380775456798   

NOMBRES_BOT = ["semillero bot", "semillero-bot", "semillerobot"]

RESPUESTAS_MENCION = [
    "¿Me llamaron? 🌱 Estoy acá regando ideas.",
    "Presente, Semillero Bot reportándose 💻🌿",
    "Acá estoy, ¿qué vamos a sembrar hoy? ✨",
    "Yo escuché *Semillero bot* y vine corriendo 🌾"
]

RESPUESTAS_SALUDO = [
    "¡Hola equipo! 👋",
    "Ey, ¿cómo va ese jardín de ideas? 🌱",
    "Presente en la daily emocional ✋",
]

# --- MOTIVACION (por ahora no las usamos, pero las dejamos listas) ---

FRASES_MANANA = [
    "🌞 ¡Buen día, equipo Semillero! Hoy es una nueva oportunidad para sembrar algo importante. 🌱",
    "☀️ Buenos días 🌱. Recuerda: los grandes cambios comienzan con pasos pequeños.",
    "✨ Hoy puede ser ese día donde todo empieza a florecer. Vamos con todo 💪"
]

GIFS_MANIANA = [
    "https://media.giphy.com/media/26BRv0ThflsHCqDrG/giphy.gif",
    "https://media1.giphy.com/media/ll1QggrS3wdxceZr7A/giphy.gif",
    "https://media1.giphy.com/media/3oEjHOUcNRKgpqTHiM/giphy.gif",
]

FRASES_TARDE = [
    "🌇 Ya va cayendo la tarde... pero todavía hay energía para una última semilla 🌱",
    "🍵 Una pausa, una respiración, y seguimos 🌾",
    "🔥 Lo estás haciendo bien. Aunque nadie lo vea, estás creciendo."
]

# --- CONFIGURACIÓN DE HORARIOS ---

TZ_ARG = timezone("America/Argentina/Buenos_Aires")

TARGET_HOUR_SALUDO = 8
TARGET_MIN_SALUDO = 35  # 👈 08:35

CHANNEL_ID = 1320416281492717601  # Canal del equipo


class MotivationCog(commands.Cog):
    """Cog de interacción y saludo diario para el equipo Semillero 🌱"""

    def __init__(self, bot):
        self.bot = bot
        # Iniciamos el loop que revisa la hora cada minuto
        self.saludo_inicial_loop.start()
        print("🗓️ Loop de saludo inicial iniciado (08:20 ARG)")

    # ======================================================
    # EVENTO INTERACTIVO CUANDO HABLAN DEL BOT
    # ======================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        contenido = message.content.lower()

        # Si mencionan al bot por nombre
        if any(nombre in contenido for nombre in NOMBRES_BOT):
            respuesta = random.choice(RESPUESTAS_MENCION)
            await message.channel.send(respuesta)

            try:
                await message.add_reaction("🌱")
            except Exception:
                pass

        # Saludan + mencionan al bot
        saludos = ["hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"]
        if any(s in contenido for s in saludos) and any(n in contenido for n in NOMBRES_BOT):
            await message.channel.send(random.choice(RESPUESTAS_SALUDO))

    # ======================================================
    # LOOP QUE CORRE CADA MINUTO Y DISPARA EL SALUDO A LAS 08:20
    # ======================================================

    @tasks.loop(minutes=1)
    async def saludo_inicial_loop(self):
        """Loop que chequea la hora y manda el saludo a las 08:20 ARG."""
        ahora = datetime.datetime.now(TZ_ARG)
        # Debug opcional:
        # print(f"[DEBUG] Son las {ahora.hour}:{ahora.minute} en ARG")

        if ahora.hour == TARGET_HOUR_SALUDO and ahora.minute == TARGET_MIN_SALUDO:
            await self.saludo_inicial()

    @saludo_inicial_loop.before_loop
    async def before_saludo_inicial(self):
        """Esperamos a que el bot esté listo antes de empezar el loop."""
        await self.bot.wait_until_ready()
        print("✅ Bot listo, saludo_inicial_loop comenzando...")

    # ======================================================
    # MENSAJE ESPECIAL DE 08:20
    # ======================================================

    async def saludo_inicial(self):
        """Mensaje inicial diario (08:20) con bienvenida a nuevas integrantes."""
        try:
            canal = self.bot.get_channel(CHANNEL_ID)
            if not canal:
                # Fallback por si get_channel devuelve None
                canal = await self.bot.fetch_channel(CHANNEL_ID)

            rochi = f"<@{ROCHI_ID}>"
            cam = f"<@{CAM_ID}>"

            mensaje = (
                f"🌱 ¡Volví equipo! Ya estoy listo para otro día de siembra.\n\n"
                f"✨ Y veo que tenemos nuevas integrantes en el jardín... "
                f"¡bienvenidas {cam} y {rochi}! ✨\n\n"
                f"Vamos a hacer que hoy crezca algo lindo 👇"
            )

            await canal.send(mensaje)
            print("[Motivation] ✅ Saludo inicial enviado.")
        except Exception as e:
            print(f"❌ Error en saludo_inicial: {e}")

# --- SETUP DEL COG ---
async def setup(bot):
    await bot.add_cog(MotivationCog(bot))
