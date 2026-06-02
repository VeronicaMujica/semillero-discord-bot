import os
import random
import logging
from datetime import datetime
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

FRASES_RANDOM_DEALER = [
    "🃏 Pausá un toque. Volvé a la mesa con cabeza fresca.",
    "🎲 Recordatorio del Dealer: si una tarea lleva más de 1 hora trabada, dejala marinar y pasá a otra.",
    "☕ ¿Hace cuánto que no tomás agua? La casa observa.",
    "💼 Una tarea sin fecha es una tarea sin compromiso. Pongan fecha.",
    "🔥 La consistencia gana al heroismo. Una hora hoy > maratón el viernes.",
    "🎯 ¿Tu próxima tarea está clara? Si no, te recomiendo abrir ClickUp.",
    "✨ Si terminaste algo hoy, marcalo. Sentir el cierre es parte del trabajo.",
    "🃏 El Dealer pasa a saludar. ¿Cómo va la mano?",
    "🌿 Levantate, estirate, respirá. Es gratis y rinde.",
    "📋 Una idea suelta hoy es una tarea bien capturada mañana. /tarea está ahí.",
    "⚡ Atención: enfocarse en 1 cosa por 25 min rinde más que 3 cosas a la vez por 2 horas.",
    "🎶 Cambialé la música. El cerebro lo nota.",
    "🃏 Recordatorio: tu yo de la noche te va a agradecer cerrar 1 tarea ahora.",
    "💪 Si llegaste hasta acá del día, ya ganaste. Cerrá una más y rematás bien.",
    "🪟 Asomate por la ventana 1 minuto. Vuelvas, retomá.",
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
        # Lun/Mié/Vie a las 9:00 Arg — frases motivadoras matutinas
        self.scheduler.add_job(
            self.enviar_motivacion,
            "cron",
            day_of_week="mon,wed,fri",
            hour=9,
            minute=0,
            id="motivation_job",
            replace_existing=True,
        )
        # Todos los días a las 10:00 → elige hora random para una frase suelta
        self.scheduler.add_job(
            self._programar_frase_random_del_dia,
            "cron",
            hour=10,
            minute=0,
            id="motivation_random_selector",
            replace_existing=True,
        )
        self.scheduler.start()
        # Programar también para hoy si el bot arranca después de las 10:00
        try:
            await self._programar_frase_random_del_dia()
        except Exception as e:
            log.warning(f"No pude programar frase random de hoy: {e}")
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

    async def _programar_frase_random_del_dia(self):
        """Elige una hora random entre 11 y 16 para tirar una frase suelta hoy."""
        now = datetime.now(ARG_TZ)
        target_hour = random.randint(11, 16)
        target_minute = random.randint(0, 59)
        run_at = now.replace(
            hour=target_hour, minute=target_minute, second=0, microsecond=0
        )
        if run_at <= now:
            log.info(
                f"Hora random {run_at.strftime('%H:%M')} ya pasó hoy — salteo."
            )
            return
        self.scheduler.add_job(
            self.enviar_frase_random,
            "date",
            run_date=run_at,
            id=f"random_phrase_{now.date()}",
            replace_existing=True,
        )
        log.info(f"Frase random programada para hoy {run_at.strftime('%H:%M')}")

    async def enviar_frase_random(self):
        if not self.channel_id:
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        frase = random.choice(FRASES_RANDOM_DEALER)
        try:
            await channel.send(frase)
        except discord.DiscordException as e:
            log.error(f"Error enviando frase random: {e}")

    @app_commands.command(
        name="motivacion",
        description="Pedile al Dealer una frase motivadora ahora mismo",
    )
    async def motivacion(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(FRASES_DEALER))


async def setup(bot: commands.Bot):
    await bot.add_cog(MotivationCog(bot))
