import logging
import os
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Jueves 14:00 ART — aviso anticipado: mañana se entrega.
MSG_JUEVES = (
    "🃏 **Aviso de la casa** — Mañana se entrega el reporte.\n"
    "Hoy es buen momento para ir juntando tus cartas: dejá procentajes y avances "
    "listos así mañana no jugás a contrarreloj. 📊"
)

# Viernes 08:00 ART — día de entrega.
MSG_VIERNES = (
    "🎴 **Hoy la casa cobra** — Es viernes: día de entrega del reporte.\n"
    "Poné tu reporte sobre la mesa antes del medio dia ⏳📊"
)


class ReportesCog(commands.Cog):
    """Recordatorios automáticos de entrega de reporte (branding Dealer)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        # Mismo canal que las frases de motivación.
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )

    async def cog_load(self):
        # Jueves 14:00 ART — aviso anticipado.
        self.scheduler.add_job(
            self._recordatorio_jueves,
            "cron",
            day_of_week="thu",
            hour=14,
            minute=0,
            id="reporte_jueves",
            replace_existing=True,
        )
        # Viernes 08:00 ART — día de entrega.
        self.scheduler.add_job(
            self._recordatorio_viernes,
            "cron",
            day_of_week="fri",
            hour=8,
            minute=0,
            id="reporte_viernes",
            replace_existing=True,
        )
        self.scheduler.start()
        log.info("ReportesCog scheduler iniciado (jue 14:00 / vie 08:00 ART).")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _enviar(self, mensaje: str):
        if not self.channel_id:
            log.warning(
                "ReportesCog: sin canal (DEALER_CHANNEL_ID / DISCORD_CHANNEL_REMINDERS)."
            )
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            log.warning(f"ReportesCog: canal {self.channel_id} no encontrado.")
            return
        try:
            await channel.send(mensaje)
        except discord.DiscordException as e:
            log.error(f"ReportesCog: error enviando recordatorio: {e}")

    async def _recordatorio_jueves(self):
        await self._enviar(MSG_JUEVES)

    async def _recordatorio_viernes(self):
        await self._enviar(MSG_VIERNES)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReportesCog(bot))
