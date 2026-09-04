"""
Resumen con IA (OpenAI) de los reportes semanales (Mesa Alta).

Automático: **viernes 16:00 ART** — lee las páginas de la semana en ClickUp y
publica en Discord un resumen de lo más relevante de cada reporte.

Por qué el viernes a las 16:00: el reporte se entrega el viernes antes del
mediodía (`cogs/reportes.py`), así que a esa hora ya está todo cargado; y queda
antes del resumen de tareas de las 17:00 (`cogs/resumen.py`), que es otra cosa
(números de ClickUp, no lo que escribió la gente).

A mano: `/resumen-reportes`, abierto a todo el equipo. Por defecto responde en
privado — sirve para leerlo antes de mandarlo al canal.
"""
import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from openai_client import IAError, OpenAIClient
from clickup_client import ClickUpClient, ClickUpAPIError
from resumen_reportes_service import SYSTEM, construir_prompt, recolectar_semana

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Discord corta en 2000; dejamos aire para no pelear con el borde.
LIMITE_DISCORD = 1900

# Canal donde cae el resumen. Override por RESUMEN_REPORTES_CHANNEL_ID.
CANAL_RESUMEN_REPORTES = 1453087931035291759


def partir_mensaje(texto: str, limite: int = LIMITE_DISCORD) -> list[str]:
    """Parte en trozos <= limite cortando por líneas (no por la mitad de una)."""
    trozos: list[str] = []
    actual = ""

    def cerrar():
        nonlocal actual
        if actual.strip():
            trozos.append(actual.rstrip("\n"))
        actual = ""

    for linea in texto.split("\n"):
        # Línea sola más larga que el tope: se corta a lo bruto, pero antes hay
        # que cerrar lo acumulado o los trozos salen desordenados.
        while len(linea) > limite:
            cerrar()
            trozos.append(linea[:limite])
            linea = linea[limite:]
        if len(actual) + len(linea) + 1 > limite:
            cerrar()
        actual += linea + "\n"
    cerrar()
    return trozos or [texto[:limite]]


class ResumenReportesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clickup = ClickUpClient()
        self.ia = OpenAIClient()
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        # Canal propio, separado del canal general del equipo: los reportes
        # incluyen "sensaciones de la semana" y no van al canal de todos.
        # Va hardcodeado (no cae a DEALER_CHANNEL_ID) justamente para que un
        # .env viejo en el servidor no lo mande al canal equivocado.
        self.channel_id = int(
            os.getenv("RESUMEN_REPORTES_CHANNEL_ID") or CANAL_RESUMEN_REPORTES
        )
        self.dia = os.getenv("RESUMEN_REPORTES_DAY", "fri")
        self.hora = int(os.getenv("RESUMEN_REPORTES_HOUR", "16"))
        self.minuto = int(os.getenv("RESUMEN_REPORTES_MINUTE", "0"))

    async def cog_load(self):
        self.scheduler.add_job(
            self._job_semanal, "cron",
            day_of_week=self.dia, hour=self.hora, minute=self.minuto,
            id="resumen_reportes", replace_existing=True,
        )
        self.scheduler.start()
        log.info(
            "ResumenReportesCog scheduler iniciado (%s %02d:%02d ART).",
            self.dia, self.hora, self.minuto,
        )
        if not self.ia.disponible:
            log.warning(
                "ResumenReportesCog: falta OPENAI_API_KEY — el resumen no va a correr."
            )

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # ---------------------------------------------------------------- #
    # Núcleo                                                            #
    # ---------------------------------------------------------------- #
    async def _armar_resumen(self, semanas_atras: int = 0) -> list[str]:
        """Mensajes listos para mandar. Levanta ClickUpAPIError / IAError."""
        hoy = dt.datetime.now(ARG_TZ).date()
        datos = await recolectar_semana(self.clickup, hoy, semanas_atras)

        cargaron = len(datos["reportes"])
        pendientes = datos["sin_cargar"] + datos["faltantes"]
        total = cargaron + len(pendientes)

        if not cargaron:
            return [
                f"🃏 **La casa quiso leer las cartas de la {datos['semana']}… "
                f"y la mesa está vacía.**\n"
                f"Nadie cargó su reporte todavía."
                + (f"\n📄 {datos['url']}" if datos["url"] else "")
            ]

        resumen = await self.ia.responder(
            system=SYSTEM,
            prompt=construir_prompt(datos),
            max_tokens=2000,
        )

        pie = f"\n\n—\n✅ Cargaron **{cargaron}/{total}**"
        if pendientes:
            pie += f" · ⏳ Faltan: {', '.join(pendientes)}"
        if datos["url"]:
            pie += f"\n📄 Reportes completos → {datos['url']}"

        cabecera = (
            f"🃏 **La casa leyó las cartas** — {datos['semana']}\n"
            f"Resumen de lo más relevante de cada reporte 👇\n\n"
        )
        return partir_mensaje(cabecera + resumen + pie)

    async def _job_semanal(self):
        canal = self.bot.get_channel(self.channel_id) if self.channel_id else None
        if not canal:
            log.warning(
                "ResumenReportesCog: sin canal (%s) — se saltea el resumen.",
                self.channel_id,
            )
            return
        try:
            mensajes = await self._armar_resumen()
        except (ClickUpAPIError, IAError) as e:
            # Nunca fallar en silencio: si no avisa, nadie se entera hasta el
            # lunes (lección aprendida con el token vencido de ClickUp).
            log.error("ResumenReportesCog: %s", e)
            await self._avisar_error(canal, e)
            return
        except Exception:
            log.exception("ResumenReportesCog: error inesperado en el resumen semanal")
            return

        for m in mensajes:
            try:
                await canal.send(m)
            except discord.DiscordException as e:
                log.error("ResumenReportesCog: error enviando resumen: %s", e)
                return

    async def _avisar_error(self, canal, err: Exception):
        detalle = str(err)[:300]
        pista = ""
        if isinstance(err, IAError) and "OPENAI_API_KEY" in detalle:
            pista = "\n👉 Cargá `OPENAI_API_KEY` en el `.env` y en los secrets de GitHub."
        elif "401" in detalle or "Token invalid" in detalle:
            pista = "\n👉 Huele a **token de ClickUp vencido**: actualizá `CLICKUP_API_TOKEN`."
        try:
            await canal.send(
                "⚠️ **La casa no pudo leer los reportes.**\n"
                f"```{detalle}```{pista}"
            )
        except discord.DiscordException as e:
            log.error("ResumenReportesCog: error avisando el fallo: %s", e)

    # ---------------------------------------------------------------- #
    # Slash                                                             #
    # ---------------------------------------------------------------- #
    @app_commands.command(
        name="resumen-reportes",
        description="Resume con IA los reportes semanales de Mesa Alta.",
    )
    @app_commands.describe(
        semanas_atras="0 = semana en curso (default), 1 = la anterior, etc.",
        publicar="Mandarlo al canal del equipo en vez de mostrártelo solo a vos.",
    )
    async def resumen_reportes(
        self,
        interaction: discord.Interaction,
        semanas_atras: app_commands.Range[int, 0, 8] = 0,
        publicar: bool = False,
    ):
        # Sin `publicar`, el resumen se ve solo para quien lo pidió: los reportes
        # traen "sensaciones de la semana" y conviene poder leerlo antes.
        await interaction.response.defer(ephemeral=not publicar, thinking=True)
        try:
            mensajes = await self._armar_resumen(semanas_atras)
        except (ClickUpAPIError, IAError) as e:
            await interaction.followup.send(f"❌ {e}")
            return

        for m in mensajes:
            await interaction.followup.send(m, ephemeral=not publicar)


async def setup(bot: commands.Bot):
    await bot.add_cog(ResumenReportesCog(bot))
