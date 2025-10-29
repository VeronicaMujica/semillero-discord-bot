import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import random
import datetime
import asyncio

# --- FRASES Y GIFS ---
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

RESPUESTAS_SIMPLIFICADAS = [
    "💚 Qué lindo que me hables 🌱",
    "✨ Te leo y sonrío 😌",
    "🌿 Estoy acá, siempre sembrando buena energía 💫",
    "🌞 ¡Vamos equipo, que esto florece! 🌱"
]

# --- CONFIGURACIÓN DE HORARIOS ---
TZ_ARG = timezone("America/Argentina/Buenos_Aires")
HORA_MANIANA = {"hour": 8, "minute": 0}
HORA_TARDE = {"hour": 16, "minute": 0}

# ⚙️ Canal donde el bot enviará los mensajes
CHANNEL_ID = 1320416281492717601  # Reemplazar por el canal real

class MotivationCog(commands.Cog):
    """Cog de motivación diaria para el equipo Semillero 🌱"""

    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=TZ_ARG)
        # 🕗 Tareas programadas
        self.scheduler.add_job(self.enviar_mensaje_mananero, "cron", **HORA_MANIANA)
        self.scheduler.add_job(self.enviar_mensaje_tarde, "cron", **HORA_TARDE)
        self.scheduler.start()
        print("🗓️ Scheduler de motivación iniciado (8AM / 16PM ARG)")

    async def enviar_mensaje_mananero(self):
        """Mensaje motivacional diario con GIF (8 AM ARG)"""
        await self._enviar_mensaje(
            random.choice(FRASES_MANANA),
            random.choice(GIFS_MANIANA)
        )

    async def enviar_mensaje_tarde(self):
        """Frase inspiradora e interactiva (tarde)"""
        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            frase = random.choice(FRASES_TARDE)
            mensaje = await canal.send(frase + "\n💬 ¿Qué fue lo más lindo que hiciste hoy?")
            # Reacciones interactivas
            for emoji in ["🌱", "💚", "🔥", "😌"]:
                await mensaje.add_reaction(emoji)
        except Exception as e:
            print(f"❌ Error en enviar_mensaje_tarde: {e}")

    async def _enviar_mensaje(self, frase, gif_url):
        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            await canal.send(frase)
            await canal.send(gif_url)
            print(f"[Motivation] ✅ Mensaje enviado a {datetime.datetime.now(TZ_ARG)}")
        except Exception as e:
            print(f"❌ Error al enviar mensaje motivacional: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Responder a menciones o mensajes dirigidos al bot"""
        if message.author.bot:
            return

        contenido = message.content.lower()
        mencionado = self.bot.user.mentioned_in(message)
        respuesta = random.choice(RESPUESTAS_SIMPLIFICADAS)

        if mencionado or any(palabra in contenido for palabra in ["bot", "semillero", "hola", "gracias"]):
            await message.channel.send(respuesta)

    # Comando manual para probar el mensaje
    @commands.command(name="test_motivation")
    async def test_motivation(self, ctx):
        """Permite probar manualmente el mensaje motivacional"""
        await self._enviar_mensaje(
            random.choice(FRASES_MANANA),
            random.choice(GIFS_MANIANA)
        )
        await ctx.send("🌱 Mensaje motivacional de prueba enviado correctamente.")

async def setup(bot):
    await bot.add_cog(MotivationCog(bot))
