import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from clickup_client import ClickUpClient, ClickUpAPIError
from informes_service import MESES, PERSONAS, asegurar_mes, generar_mes, semana_actual

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


class InformesCog(commands.Cog):
    """
    Crea automáticamente en ClickUp los Docs de informes de Mesa Alta:
      • "Informes semanales" → Mes → Semana (Lun–Vie) → página por persona
      • "Informes mensuales" → Mes → página por persona

    Automatización (idempotente, nunca duplica):
      • Cada LUNES 10:30 ART → asegura la semana en curso (autorreparando lo
        que falte) y manda el DEEP LINK a esa página. Si la semana cruza de mes,
        adelanta también el mes siguiente.
    Y a mano: /generar-informes [mes] [año] (solo admins, fuerza la creación).
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
            self._job_lunes, "cron", day_of_week="mon", hour=10, minute=30,
            id="informes_lunes", replace_existing=True,
        )
        self.scheduler.start()
        log.info("InformesCog scheduler iniciado (lunes 10:30 ART).")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _job_lunes(self):
        hoy = dt.datetime.now(ARG_TZ).date()
        try:
            # asegurar_mes autorrepara lo que falte y devuelve el deep link a la
            # página de la semana en curso.
            res = await asegurar_mes(self.client, hoy)
        except ClickUpAPIError as e:
            # Antes esto era un `return` mudo: cuando venció el token de ClickUp
            # el lunes no llegó ningún mensaje y nadie se enteró. Ahora avisa.
            log.error("InformesCog: error asegurando informes: %s", e)
            await self._avisar_error(e)
            return
        except Exception:
            log.exception("InformesCog: error inesperado en el job de los lunes")
            return
        await self._avisar_semana(res)

    async def _canal(self):
        if not self.channel_id:
            log.warning("InformesCog: sin canal para avisar (DEALER_CHANNEL_ID).")
            return None
        canal = self.bot.get_channel(self.channel_id)
        if not canal:
            log.warning("InformesCog: canal %s no encontrado.", self.channel_id)
        return canal

    async def _avisar_error(self, err: Exception):
        canal = await self._canal()
        if not canal:
            return
        detalle = str(err)[:300]
        pista = ""
        if "401" in detalle or "OAUTH" in detalle.upper() or "Token invalid" in detalle:
            pista = "\n👉 Huele a **token de ClickUp vencido**: actualizá `CLICKUP_API_TOKEN`."
        try:
            await canal.send(
                "⚠️ **La casa no pudo repartir los informes.**\n"
                f"ClickUp devolvió un error:\n```{detalle}```{pista}"
            )
        except discord.DiscordException as e:
            log.error("InformesCog: error enviando aviso de error: %s", e)

    async def _avisar_semana(self, res: dict):
        canal = await self._canal()
        if not canal:
            return

        prox = res.get("proximo_mes")
        linea_prox = f"\n🗓️ Mensual de {prox['mes']} → {prox['url']}" if prox else ""
        mensaje = (
            f"🃏 **Arranca la semana, arranca la mano.**\n"
            f"Ya está el informe de la **{res['semana']}** listo para cargar 👇\n"
            f"📄 Semanal → {res['semanales']['url']}\n"
            f"📅 Mensual de {res['mes']} → {res['mensuales']['url']}"
            f"{linea_prox}\n"
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
