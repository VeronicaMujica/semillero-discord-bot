import os
import json
import time
import logging
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import defaultdict

import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from clickup_client import ClickUpClient, ClickUpAPIError
from user_mapping import (
    CLICKUP_TEAM,
    get_discord_id_for_clickup,
    display_name,
    auto_link_from_guild,
)

log = logging.getLogger(__name__)
ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

GUILD_WORKSPACE_FILE = Path("guild_workspace.json")
UMBRAL_ATRASADAS = 2


def load_guild_workspace() -> dict:
    if not GUILD_WORKSPACE_FILE.exists():
        return {}
    try:
        return json.loads(GUILD_WORKSPACE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def team_id_for_guild(guild_id: int) -> str | None:
    return load_guild_workspace().get(str(guild_id))


class RemindersCog(commands.Cog):
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
            self.enviar_reminders,
            "cron",
            day_of_week="tue,thu",
            hour=10,
            minute=0,
            id="reminders_job",
            replace_existing=True,
        )
        self.scheduler.start()
        log.info("RemindersCog scheduler iniciado.")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                nuevos = await auto_link_from_guild(guild)
                if nuevos:
                    log.info(f"Auto-vinculados {nuevos} miembros en {guild.name}")
            except Exception as e:
                log.warning(f"Error auto-linkeando en {guild.name}: {e}")

    async def _overdue_by_user(self, team_id: str) -> dict[int, list[dict]]:
        now_ms = int(time.time() * 1000)
        tasks = await self.clickup.get_all_team_tasks(
            team_id,
            due_date_lt=now_ms,
            include_closed=False,
        )
        by_user: dict[int, list[dict]] = defaultdict(list)
        for t in tasks:
            for a in t.get("assignees", []):
                by_user[a["id"]].append(t)
        return by_user

    def _resolve_channel(self):
        if not self.channel_id:
            return None
        return self.bot.get_channel(self.channel_id)

    def _team_id_for_channel(self, channel) -> str:
        if channel and channel.guild:
            tid = team_id_for_guild(channel.guild.id)
            if tid:
                return tid
        return self.fallback_team_id

    async def enviar_reminders(self):
        channel = self._resolve_channel()
        if not channel:
            log.warning("Canal de reminders no encontrado.")
            return

        team_id = self._team_id_for_channel(channel)

        try:
            overdue = await self._overdue_by_user(team_id)
        except ClickUpAPIError as e:
            await channel.send(f"⚠️ El Dealer no pudo leer ClickUp: `{e}`")
            return

        valid_clickup_ids = {info["id"] for info in CLICKUP_TEAM.values()}

        lineas = ["🃏 **El Dealer pasa lista** — tarjeta de tareas atrasadas:\n"]
        alguien_tiene = False
        for ck_id, tareas in sorted(overdue.items(), key=lambda x: -len(x[1])):
            if ck_id not in valid_clickup_ids:
                continue
            if len(tareas) < UMBRAL_ATRASADAS:
                continue
            alguien_tiene = True
            discord_id = get_discord_id_for_clickup(ck_id)
            nombre = display_name(ck_id)
            mencion = f"<@{discord_id}>" if discord_id else f"**{nombre}**"
            lineas.append(
                f"• {mencion} tenés **{len(tareas)}** tareas atrasadas. A actualizarlas 👀"
            )

        if not alguien_tiene:
            lineas.append(
                "✨ Nadie tiene 2+ atrasadas. La mesa está limpia, buen laburo equipo."
            )
        else:
            lineas.append(
                "\n_Recordatorio: actualicen estado, fecha o cierren en ClickUp._"
            )

        try:
            await channel.send("\n".join(lineas))
        except discord.DiscordException as e:
            log.error(f"Error enviando reminders: {e}")

    @app_commands.command(
        name="atrasadas",
        description="Ver quién tiene más tareas atrasadas en ClickUp",
    )
    async def atrasadas(self, interaction: discord.Interaction):
        await interaction.response.defer()
        team_id = team_id_for_guild(interaction.guild_id) or self.fallback_team_id
        try:
            overdue = await self._overdue_by_user(team_id)
        except ClickUpAPIError as e:
            await interaction.followup.send(f"⚠️ Error ClickUp: `{e}`")
            return

        valid_ids = {info["id"] for info in CLICKUP_TEAM.values()}
        ranking = sorted(
            [(ck, len(t)) for ck, t in overdue.items() if ck in valid_ids and t],
            key=lambda x: -x[1],
        )

        if not ranking:
            await interaction.followup.send("✨ Nadie tiene tareas atrasadas. Mesa limpia.")
            return

        lineas = ["🃏 **Ranking de atrasadas:**"]
        medallas = ["🥇", "🥈", "🥉"]
        for idx, (ck_id, cant) in enumerate(ranking):
            medalla = medallas[idx] if idx < 3 else "•"
            lineas.append(f"{medalla} {display_name(ck_id)} — {cant}")

        await interaction.followup.send("\n".join(lineas))


async def setup(bot: commands.Bot):
    await bot.add_cog(RemindersCog(bot))
