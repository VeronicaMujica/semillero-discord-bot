import os
import json
import time
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from clickup_client import ClickUpClient, ClickUpAPIError
from user_mapping import CLICKUP_TEAM, display_name

log = logging.getLogger(__name__)
ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

GUILD_WORKSPACE_FILE = Path("guild_workspace.json")
WEEK_MS = 7 * 24 * 60 * 60 * 1000


def team_id_for_guild(guild_id: int) -> str | None:
    if not GUILD_WORKSPACE_FILE.exists():
        return None
    try:
        data = json.loads(GUILD_WORKSPACE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data.get(str(guild_id))


class ResumenCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clickup = ClickUpClient()
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )
        self.fallback_team_id = os.getenv("CLICKUP_TEAM_ID") or "9011755800"

    async def cog_load(self):
        self.scheduler.add_job(
            self.enviar_resumen_semanal,
            "cron",
            day_of_week="fri",
            hour=17,
            minute=0,
            id="resumen_job",
            replace_existing=True,
        )
        self.scheduler.start()

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _build_resumen(self, team_id: str) -> str:
        now_ms = int(time.time() * 1000)
        hace_una_semana = now_ms - WEEK_MS

        creadas = await self.clickup.get_all_team_tasks(
            team_id,
            date_created_gt=hace_una_semana,
            include_closed=True,
        )
        cerradas = await self.clickup.get_all_team_tasks(
            team_id,
            date_closed_gt=hace_una_semana,
            include_closed=True,
        )

        por_asignado_cerradas: dict[int, int] = {}
        valid_ids = {info["id"] for info in CLICKUP_TEAM.values()}
        for t in cerradas:
            for a in t.get("assignees", []):
                if a["id"] in valid_ids:
                    por_asignado_cerradas[a["id"]] = (
                        por_asignado_cerradas.get(a["id"], 0) + 1
                    )

        top_cerradas = sorted(
            por_asignado_cerradas.items(), key=lambda x: -x[1]
        )[:3]

        lineas = [
            "🃏 **Resumen semanal del Dealer** 📊",
            "",
            f"📥 Tareas creadas: **{len(creadas)}**",
            f"✅ Tareas cerradas: **{len(cerradas)}**",
        ]

        if top_cerradas:
            lineas.append("")
            lineas.append("🏆 **Top cerradores de la semana:**")
            medallas = ["🥇", "🥈", "🥉"]
            for idx, (ck_id, n) in enumerate(top_cerradas):
                lineas.append(f"{medallas[idx]} {display_name(ck_id)} — {n} tareas")

        lineas.append("")
        lineas.append("_Buen fin de semana, equipo. El Dealer cierra la mesa._ 🃏")
        return "\n".join(lineas)

    async def enviar_resumen_semanal(self):
        if not self.channel_id:
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        team_id = (
            team_id_for_guild(channel.guild.id) if channel.guild else None
        ) or self.fallback_team_id
        try:
            msg = await self._build_resumen(team_id)
        except ClickUpAPIError as e:
            msg = f"⚠️ No pude armar el resumen semanal: `{e}`"
        try:
            await channel.send(msg)
        except discord.DiscordException as e:
            log.error(f"Error enviando resumen: {e}")

    @app_commands.command(
        name="resumen-semanal",
        description="Pedir el resumen semanal ahora (últimos 7 días)",
    )
    async def resumen_semanal(self, interaction: discord.Interaction):
        await interaction.response.defer()
        team_id = team_id_for_guild(interaction.guild_id) or self.fallback_team_id
        try:
            msg = await self._build_resumen(team_id)
        except ClickUpAPIError as e:
            await interaction.followup.send(f"⚠️ Error ClickUp: `{e}`")
            return
        await interaction.followup.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(ResumenCog(bot))
