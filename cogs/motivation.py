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

CHANNEL_ID = 1320416281492717601  # Canal del equipo

class MotivationCog(commands.Cog):
    """Cog de motivación diaria para el equipo Semillero 🌱"""

    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=TZ_ARG)
        self.last_sent = {"morning": None, "evening": None}  # Protección de duplicados

        # Programación de mensajes
        self.scheduler.add_job(self.enviar_mensaje_mananero, "cron", **HORA_MANIANA)
        self.scheduler.add_job(self.enviar_mensaje_tarde, "cron", **HORA_TARDE)
        self.scheduler.start()
        print("🗓️ Scheduler de motivación iniciado (8AM / 16PM ARG)")

    # --- FUNCIONES PRINCIPALES ---

    async def enviar_mensaje_mananero(self):
        """Mensaje motivacional diario (8 AM ARG)"""
        ahora = datetime.datetime.now(TZ_ARG)
        dia_semana = ahora.strftime("%A").lower()
        hoy = ahora.date()

        # Protección de duplicados
        if self.last_sent["morning"] == hoy:
            print("🕗 Ya se envió el mensaje matutino hoy.")
            return
        self.last_sent["morning"] = hoy

        # Modo descanso
        if dia_semana in ["saturday", "sunday"]:
            await self._enviar_mensaje_descanso()
            return

        # Personalización según día (solo lunes y viernes)
        if dia_semana == "monday":
            mensaje = "💪 Lunes de siembra: esta semana puede florecer algo increíble. 🌱"
        elif dia_semana == "friday":
            mensaje = "🎉 ¡Viernes, equipo! Hoy celebramos lo que creció esta semana. 🌾"
        else:
            mensaje = random.choice(FRASES_MANANA)

        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            gif = random.choice(GIFS_MANIANA)
            await canal.send(f"{mensaje}\n\nReacciona con tu mood de hoy 👇")
            await canal.send(gif)
            print(f"[Motivation] ✅ Mensaje de mañana enviado a {ahora}")
        except Exception as e:
            print(f"❌ Error en enviar_mensaje_mananero: {e}")

    async def enviar_mensaje_tarde(self):
        """Mensaje de la tarde (simple y relajado)"""
        ahora = datetime.datetime.now(TZ_ARG)
        hoy = ahora.date()

        # Protección de duplicados
        if self.last_sent["evening"] == hoy:
            print("🕗 Ya se envió el mensaje de la tarde hoy.")
            return
        self.last_sent["evening"] = hoy

        # No enviar en fines de semana
        dia_semana = ahora.strftime("%A").lower()
        if dia_semana in ["saturday", "sunday"]:
            print("🌿 Fin de semana, no se envía mensaje de tarde.")
            return

        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            frase = random.choice(FRASES_TARDE)
            await canal.send(frase)
            print(f"[Motivation] ✅ Mensaje de tarde enviado a {ahora}")
        except Exception as e:
            print(f"❌ Error en enviar_mensaje_tarde: {e}")

    async def _enviar_mensaje_descanso(self):
        """Mensaje especial para fines de semana"""
        try:
            canal = await self.bot.fetch_channel(CHANNEL_ID)
            await canal.send("🌿 Es fin de semana, equipo. Hoy la tarea es descansar y recargar energía 🌞")
            print(f"[Motivation] 🌿 Mensaje de descanso enviado correctamente.")
        except Exception as e:
            print(f"❌ Error al enviar mensaje de descanso: {e}")

    # --- EVENTOS Y REACCIONES ---

    # --- COMANDO MANUAL ---
    @commands.command(name="test_motivation")
    async def test_motivation(self, ctx):
        """Permite probar manualmente el mensaje motivacional"""
        ahora = datetime.datetime.now(TZ_ARG)
        dia_semana = ahora.strftime("%A").lower()

        if dia_semana in ["saturday", "sunday"]:
            await self._enviar_mensaje_descanso()
        else:
            await self.enviar_mensaje_mananero()

        await ctx.send("🌱 Mensaje motivacional de prueba enviado correctamente.")

# --- SETUP DEL COG ---
async def setup(bot):
    await bot.add_cog(MotivationCog(bot))
