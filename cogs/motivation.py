import os
import random
import logging
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

FRASES_DEALER = [
    "🃏 Buen día, equipo. Hoy las cartas están a favor del que se sienta a jugarlas.",
    "🎲 La suerte es para el que aparece. Empezamos.",
    "🔥 Otra jornada, otra mano. El Dealer reparte, ustedes juegan.",
    "☕ Buen día. Recuerden: una tarea cerrada hoy vale más que diez pendientes mañana.",
    "💼 El que sostiene el ritmo, gana el juego. Arrancamos.",
    "⚡ Energía de lunes (o el día que sea). Mover una sola cosa ya es avanzar.",
    "🎯 No hace falta terminar todo hoy. Hace falta empezar.",
    "🌱 Sembrando desde temprano. El día rinde cuando se agarra al vuelo.",
    "🃏 El Dealer saluda. Hoy vamos por lo importante, no por lo urgente.",
    "🚀 Menos scroll, más foco. Vamos con una primera tarea bien hecha.",
    "💡 La disciplina cansa menos que la culpa. Buen día, equipo.",
    "🎶 Pongan música, abran ClickUp, y hagamos magia.",
    "🧠 Cerebro fresco, decisiones claras. Aprovechen la mañana.",
    "🌞 Buen día. Hoy el Dealer reparte foco y café.",
]


class MotivationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )

    async def cog_load(self):
        # Lun/Mié/Vie a las 9:00 Arg
        self.scheduler.add_job(
            self.enviar_motivacion,
            "cron",
            day_of_week="mon,wed,fri",
            hour=9,
            minute=0,
            id="motivation_job",
            replace_existing=True,
        )
        self.scheduler.start()
        log.info("MotivationCog scheduler iniciado.")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def enviar_motivacion(self):
        if not self.channel_id:
            log.warning("No hay DEALER_CHANNEL_ID configurado.")
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            log.warning(f"Canal {self.channel_id} no encontrado.")
            return
        frase = random.choice(FRASES_DEALER)
        try:
            await channel.send(frase)
        except discord.DiscordException as e:
            log.error(f"Error enviando motivación: {e}")

    @app_commands.command(
        name="motivacion",
        description="Pedile al Dealer una frase motivadora ahora mismo",
    )
    async def motivacion(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(FRASES_DEALER))


async def setup(bot: commands.Bot):
    await bot.add_cog(MotivationCog(bot))
