import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from clickup_client import ClickUpClient, ClickUpAPIError
from informes_service import MESES, PERSONAS, generar_mes, semana_actual

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


class InformesCog(commands.Cog):
    """
    Crea automáticamente en ClickUp los Docs de informes de Mesa Alta:
      • "Informes semanales" → Mes → Semana (Lun–Vie) → página por persona
      • "Informes mensuales" → Mes → página por persona

    Automatización (idempotente, nunca duplica):
      • Cada LUNES 06:00 ART → asegura la estructura del mes/semana en curso
        y avisa en el canal de reminders con el link al Doc.
    Y a mano: /generar-informes [mes] [año] (solo admins).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = ClickUpClient()
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )

    async def cog_load(self):
        self.scheduler.add_job(
            self._job_lunes, "cron", day_of_week="mon", hour=6, minute=0,
            id="informes_lunes", replace_existing=True,
        )
        self.scheduler.start()
        log.info("InformesCog scheduler iniciado (lunes 06:00 ART).")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _job_lunes(self):
        hoy = dt.datetime.now(ARG_TZ)
        try:
            res = await generar_mes(self.client, hoy.year, hoy.month)
        except ClickUpAPIError as e:
            log.error("InformesCog: error generando informes: %s", e)
            return
        await self._avisar_semana(hoy.date(), res)

    async def _avisar_semana(self, hoy: dt.date, res: dict):
        if not self.channel_id:
            log.warning("InformesCog: sin canal para avisar (DEALER_CHANNEL_ID).")
            return
        canal = self.bot.get_channel(self.channel_id)
        if not canal:
            log.warning("InformesCog: canal %s no encontrado.", self.channel_id)
            return

        label, _lun, _vie = semana_actual(hoy)
        url_sem = res["semanales"]["url"]
        url_men = res["mensuales"]["url"]
        mensaje = (
            f"🃏 **Arranca la semana, arranca la mano.**\n"
            f"Ya está el informe de la **{label}** listo para cargar 👇\n"
            f"📄 Semanales → {url_sem}\n"
            f"📅 Mensual de {res['mes']} → {url_men}\n"
            f"Dejá tus cartas sobre la mesa. 📊"
        )
        try:
            await canal.send(mensaje)
        except discord.DiscordException as e:
            log.error("InformesCog: error enviando aviso: %s", e)

    @app_commands.command(
        name="generar-informes",
        description="Crea/asegura los Docs de informes de Mesa Alta en ClickUp (solo admins).",
    )
    @app_commands.describe(
        mes="Número de mes 1-12 (por defecto, el mes actual).",
        anio="Año (por defecto, el actual).",
    )
    async def generar_informes(
        self,
        interaction: discord.Interaction,
        mes: app_commands.Range[int, 1, 12] | None = None,
        anio: app_commands.Range[int, 2024, 2100] | None = None,
    ):
        if not (interaction.guild and interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                "🔒 Solo un admin puede generar los informes.", ephemeral=True
            )
            return

        hoy = dt.datetime.now(ARG_TZ)
        year = anio or hoy.year
        month = mes or hoy.month

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            res = await generar_mes(self.client, year, month)
        except ClickUpAPIError as e:
            await interaction.followup.send(f"❌ ClickUp devolvió un error:\n```{e}```")
            return

        s, m = res["semanales"]["creadas"], res["mensuales"]["creadas"]
        await interaction.followup.send(
            f"✅ Informes de **{MESES[month]} {year}** listos en ClickUp (Space MESA ALTA).\n"
            f"• **{res['total_creadas']}** páginas nuevas (semanales: {s}, mensuales: {m}).\n"
            f"• Personas: {', '.join(PERSONAS)}.\n"
            f"📄 {res['semanales']['url']}\n"
            f"📅 {res['mensuales']['url']}\n"
            f"_Idempotente: si ya existían, no se duplicó nada._"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(InformesCog(bot))
