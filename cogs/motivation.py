import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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

# --- MOTIVACION ---

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

HORA_MANIANA = {"hour": 8, "minute": 0}
HORA_TARDE = {"hour": 16, "minute": 0}
HORA_SALUDO_INICIAL = {"hour": 10, "minute": 21}

CHANNEL_ID = 1320416281492717601 # Canal del equipo



class MotivationCog(commands.Cog):
    """Cog de motivación diaria para el equipo Semillero 🌱"""

    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=TZ_ARG)
        self.last_sent = {"morning": None, "evening": None, "inicio": None}

        # Programación
        self.scheduler.add_job(self.saludo_inicial, "cron", **HORA_SALUDO_INICIAL)
        self.scheduler.add_job(self.enviar_mensaje_mananero, "cron", **HORA_MANIANA)
        self.scheduler.add_job(self.enviar_mensaje_tarde, "cron", **HORA_TARDE)
        self.scheduler.start()

        print("🗓️ Schedulers iniciados (8, 8:30 y 16)")

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
            except:
                pass

        # Saludan + mencionan al bot
        saludos = ["hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"]
        if any(s in contenido for s in saludos) and any(n in contenido for n in NOMBRES_BOT):
            await message.channel.send(random.choice(RESPUESTAS_SALUDO))

    # ======================================================
    # MENSAJE ESPECIAL DE 8:30 AM
    # ======================================================

    async def saludo_inicial(self):
        """Mensaje inicial diario (08:30) con bienvenida a nuevas integrantes."""
        ahora = datetime.datetime.now(TZ_ARG).date()

        if self.last_sent["inicio"] == ahora:
            return
        self.last_sent["inicio"] = ahora

        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            rochi = f"<@{ROCHI_ID}>"
            cam = f"<@{CAM_ID}>"

            mensaje = (
                f"🌱 ¡Volví equipo! Ya estoy listo para otro día de siembra.\n\n"
                f"✨ Y veo que tenemos nuevas integrantes en el jardín... ¡bienvenidas {cam} y {rochi}! ✨\n\n"
                f"Vamos a hacer que hoy crezca algo lindo 👇"
            )

            await canal.send(mensaje)
            print("[Motivation] Saludo inicial enviado.")
        except Exception as e:
            print(f"❌ Error en saludo_inicial: {e}")

    # ======================================================
    # DESCANSO FIN DE SEMANA
    # ======================================================

    async def _enviar_mensaje_descanso(self):
        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            await canal.send("🌿 Es fin de semana, equipo. Hoy la tarea es descansar y recargar energía 🌞")
        except Exception as e:
            print(f"❌ Error al enviar mensaje de descanso: {e}")


# --- SETUP DEL COG ---
async def setup(bot):
    await bot.add_cog(MotivationCog(bot))
