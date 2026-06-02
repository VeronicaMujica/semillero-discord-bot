import json
import logging
import os
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from clickup_client import ClickUpClient, ClickUpAPIError
from user_mapping import get_clickup_id, display_name

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
GUILD_WORKSPACE_FILE = Path(__file__).resolve().parent.parent / "guild_workspace.json"
KUDOS_FILE = Path(__file__).resolve().parent.parent / "data" / "kudos.json"


def _team_id_for_guild(guild_id: int | None) -> str | None:
    if guild_id is None or not GUILD_WORKSPACE_FILE.exists():
        return None
    try:
        data = json.loads(GUILD_WORKSPACE_FILE.read_text(encoding="utf-8"))
        return data.get(str(guild_id))
    except json.JSONDecodeError:
        return None


def _kudos_recibidos_recientes(discord_id: int, dias: int = 30) -> int:
    if not KUDOS_FILE.exists():
        return 0
    try:
        data = json.loads(KUDOS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    cutoff = (datetime.now(ARG_TZ) - timedelta(days=dias)).isoformat()
    return sum(
        1 for k in data
        if k.get("to_id") == str(discord_id) and k.get("timestamp", "") >= cutoff
    )


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clickup = ClickUpClient()
        self.fallback_team_id = os.getenv("CLICKUP_TEAM_ID") or "9011755800"

    @app_commands.command(
        name="mis-stats",
        description="Tus métricas de los últimos 30 días",
    )
    async def mis_stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        clickup_id = get_clickup_id(interaction.user.id)
        if not clickup_id:
            await interaction.followup.send(
                "❌ No estás vinculada a ClickUp. Usá `/vincular-clickup` primero.",
                ephemeral=True,
            )
            return

        team_id = _team_id_for_guild(interaction.guild_id) or self.fallback_team_id

        thirty_days_ago_ms = int(
            (datetime.now(ARG_TZ) - timedelta(days=30)).timestamp() * 1000
        )
        now_ms = int(time.time() * 1000)

        # Tareas abiertas asignadas
        try:
            abiertas = await self.clickup.get_all_team_tasks(
                team_id,
                assignee_ids=[clickup_id],
                include_closed=False,
            )
        except ClickUpAPIError as e:
            await interaction.followup.send(
                f"⚠️ Error ClickUp: `{e}`", ephemeral=True
            )
            return

        # Filtrar las "done" del set de abiertas
        abiertas_reales = [
            t for t in abiertas
            if (t.get("status") or {}).get("type", "") not in ("closed", "done")
        ]
        atrasadas = [
            t for t in abiertas_reales
            if t.get("due_date") and int(t["due_date"]) < now_ms
        ]

        # Creadas en los últimos 30 días
        try:
            creadas = await self.clickup.get_all_team_tasks(
                team_id,
                assignee_ids=[clickup_id],
                include_closed=True,
                date_created_gt=thirty_days_ago_ms,
            )
        except ClickUpAPIError:
            creadas = []

        # Cerradas en los últimos 30 días
        try:
            cerradas = await self.clickup.get_all_team_tasks(
                team_id,
                assignee_ids=[clickup_id],
                include_closed=True,
                date_closed_gt=thirty_days_ago_ms,
            )
        except ClickUpAPIError:
            cerradas = []

        cerradas_reales = [
            t for t in cerradas
            if (t.get("status") or {}).get("type", "") in ("closed", "done")
        ]

        # Kudos recibidos
        kudos = _kudos_recibidos_recientes(interaction.user.id, 30)

        # Top 3 listas donde más trabajaste
        listas_counter = Counter()
        for t in cerradas_reales:
            lista = (t.get("list") or {}).get("name", "—")
            listas_counter[lista] += 1
        top_listas = listas_counter.most_common(3)

        nombre = display_name(clickup_id)
        embed = discord.Embed(
            title=f"🃏 Stats de {nombre}",
            description="_Últimos 30 días_",
            color=0x4285F4,
        )
        embed.add_field(name="✅ Cerradas", value=f"**{len(cerradas_reales)}**", inline=True)
        embed.add_field(name="➕ Creadas", value=f"**{len(creadas)}**", inline=True)
        embed.add_field(name="🃏 Abiertas hoy", value=f"**{len(abiertas_reales)}**", inline=True)
        embed.add_field(name="⏰ Atrasadas", value=f"**{len(atrasadas)}**", inline=True)
        embed.add_field(name="🏆 Kudos recibidos", value=f"**{kudos}**", inline=True)

        if cerradas_reales:
            ratio = len(cerradas_reales) / max(len(creadas), 1)
            embed.add_field(
                name="📈 Ratio cierre/creación",
                value=f"**{ratio:.0%}**",
                inline=True,
            )

        if top_listas:
            lineas = [f"• {nombre[:35]} — {cant}" for nombre, cant in top_listas]
            embed.add_field(name="🎯 Listas más activas", value="\n".join(lineas), inline=False)

        if len(atrasadas) == 0 and len(cerradas_reales) > 0:
            embed.add_field(
                name="🔥 Estado",
                value="Sin atrasadas + cerrando tareas. La mesa te paga.",
                inline=False,
            )
        elif len(atrasadas) >= 5:
            embed.add_field(
                name="⚠️ Estado",
                value="Tenés varias atrasadas. Considerá repriorizar.",
                inline=False,
            )

        embed.set_footer(text="Stats privadas — solo vos las ves")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
