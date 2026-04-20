import json
import time
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from clickup_client import ClickUpClient, ClickUpAPIError
from user_mapping import get_clickup_id

WORKSPACE_CONFIG_FILE = Path("guild_workspace.json")

PRIORITY_MAP = {"urgente": 1, "alta": 2, "normal": 3, "baja": 4}
PRIORITY_COLOR = {"urgente": 0xE53935, "alta": 0xFB8C00, "normal": 0x1E88E5, "baja": 0x757575}
PRIORITY_EMOJI = {"urgente": "🔴", "alta": "🟠", "normal": "🔵", "baja": "⚪"}


def _load_workspaces() -> dict:
    if WORKSPACE_CONFIG_FILE.exists():
        with open(WORKSPACE_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_workspaces(data: dict):
    with open(WORKSPACE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _parse_date_ms(date_str: str | None) -> int | None:
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


def _encode(id_: str, name: str) -> str:
    """Empaqueta id::nombre en un string para el valor de autocomplete (máx 100 chars)."""
    raw = f"{id_}::{name}"
    return raw[:100]


def _decode(value: str) -> tuple[str, str]:
    """Desempaqueta 'id::nombre' → (id, nombre)."""
    parts = value.split("::", 1)
    return parts[0], parts[1] if len(parts) > 1 else parts[0]


class TareasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clickup = ClickUpClient()

    def _team_id(self, guild_id: int | None) -> str | None:
        if guild_id is None:
            return None
        return _load_workspaces().get(str(guild_id))

    # ── Autocomplete ──────────────────────────────────────────────────────────

    async def _autocomplete_lista(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        team_id = self._team_id(interaction.guild_id)
        if not team_id:
            return [app_commands.Choice(
                name="⚠️ Primero usa /configurar-workspace",
                value="__no_workspace__"
            )]
        try:
            lists = await self.clickup.get_all_lists(team_id)
            choices = []
            for lst in lists:
                label = f"{lst['folder']} › {lst['name']}" if lst.get("folder") else lst["name"]
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(
                        name=label[:100],
                        value=_encode(lst["id"], lst["name"]),
                    ))
            return choices[:25]
        except Exception:
            return []

    async def _autocomplete_responsable(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        team_id = self._team_id(interaction.guild_id)
        if not team_id:
            return []
        try:
            members = await self.clickup.get_members(team_id)
            choices = []
            for m in members:
                if current.lower() in m["name"].lower():
                    choices.append(app_commands.Choice(
                        name=m["name"][:100],
                        value=_encode(str(m["id"]), m["name"]),
                    ))
            return choices[:25]
        except Exception:
            return []

    # ── /tarea ────────────────────────────────────────────────────────────────

    @app_commands.command(name="tarea", description="Crear una tarea en ClickUp")
    @app_commands.describe(
        titulo="Nombre de la tarea",
        lista="Tablero o lista donde crear la tarea",
        responsable="Persona asignada",
        descripcion="Descripción (opcional)",
        prioridad="Prioridad de la tarea",
        fecha_limite="Fecha límite en formato YYYY-MM-DD (opcional)",
    )
    @app_commands.autocomplete(lista=_autocomplete_lista, responsable=_autocomplete_responsable)
    @app_commands.choices(prioridad=[
        app_commands.Choice(name="🔴 Urgente", value="urgente"),
        app_commands.Choice(name="🟠 Alta",    value="alta"),
        app_commands.Choice(name="🔵 Normal",  value="normal"),
        app_commands.Choice(name="⚪ Baja",    value="baja"),
    ])
    async def tarea(
        self,
        interaction: discord.Interaction,
        titulo: str,
        lista: str,
        responsable: str,
        descripcion: str | None = None,
        prioridad: app_commands.Choice[str] | None = None,
        fecha_limite: str | None = None,
    ):
        if lista == "__no_workspace__":
            await interaction.response.send_message(
                "❌ Este servidor no tiene un workspace configurado. Usa `/configurar-workspace`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            due_ms = _parse_date_ms(fecha_limite)
        except ValueError:
            await interaction.followup.send(
                "❌ La fecha debe estar en formato **YYYY-MM-DD** (ej: `2025-04-30`)."
            )
            return

        list_id, list_name = _decode(lista)
        user_id_str, user_name = _decode(responsable)
        priority_int = PRIORITY_MAP.get(prioridad.value) if prioridad else None

        try:
            task = await self.clickup.create_task(
                list_id=list_id,
                name=titulo,
                description=descripcion or "",
                assignees=[int(user_id_str)] if user_id_str.isdigit() else [],
                priority=priority_int,
                due_date=due_ms,
            )
        except ClickUpAPIError as e:
            await interaction.followup.send(f"❌ Error en ClickUp:\n```{e}```")
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Error inesperado:\n```{e}```")
            return

        pri_val = prioridad.value if prioridad else "normal"
        color = PRIORITY_COLOR.get(pri_val, 0x1E88E5)

        embed = discord.Embed(
            title="🃏 Tarea repartida",
            description=f"### {task.get('name', titulo)}",
            color=color,
            url=task.get("url"),
        )
        embed.add_field(name="👤 Responsable", value=user_name, inline=True)
        embed.add_field(name="📋 Lista", value=list_name, inline=True)

        if prioridad:
            emoji = PRIORITY_EMOJI.get(pri_val, "")
            embed.add_field(name="⚡ Prioridad", value=f"{emoji} {prioridad.name.split()[-1]}", inline=True)

        if fecha_limite:
            embed.add_field(name="📅 Fecha límite", value=fecha_limite, inline=True)

        if descripcion:
            embed.add_field(name="📝 Descripción", value=descripcion[:1024], inline=False)

        if task.get("url"):
            embed.add_field(name="🔗 Ver tarea", value=task["url"], inline=False)

        embed.set_footer(text=f"Repartida por {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    # ── /mis-tareas ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="mis-tareas",
        description="Ver tus tareas abiertas en ClickUp",
    )
    async def mis_tareas(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        clickup_id = get_clickup_id(interaction.user.id)
        if not clickup_id:
            await interaction.followup.send(
                "❌ No estás vinculado. Usá `/vincular-clickup` primero.",
                ephemeral=True,
            )
            return

        team_id = self._team_id(interaction.guild_id)
        if not team_id:
            await interaction.followup.send(
                "❌ Este servidor no tiene workspace configurado. Usá `/configurar-workspace`.",
                ephemeral=True,
            )
            return

        try:
            tasks = await self.clickup.get_all_team_tasks(
                team_id,
                assignee_ids=[clickup_id],
                include_closed=False,
            )
        except ClickUpAPIError as e:
            await interaction.followup.send(f"❌ Error ClickUp: `{e}`", ephemeral=True)
            return

        if not tasks:
            await interaction.followup.send(
                "✨ No tenés tareas abiertas. Mesa limpia.", ephemeral=True
            )
            return

        now_ms = int(time.time() * 1000)
        lineas = [f"🃏 **Tus tareas abiertas ({len(tasks)}):**"]
        for t in tasks[:15]:
            nombre = t.get("name", "sin título")
            url = t.get("url", "")
            due = t.get("due_date")
            icono = "⏰" if due and int(due) < now_ms else "•"
            if url:
                lineas.append(f"{icono} [{nombre}]({url})")
            else:
                lineas.append(f"{icono} {nombre}")

        if len(tasks) > 15:
            lineas.append(f"\n_…y {len(tasks) - 15} más._")

        await interaction.followup.send("\n".join(lineas), ephemeral=True)

    # ── /configurar-workspace ─────────────────────────────────────────────────

    @app_commands.command(
        name="configurar-workspace",
        description="Vincular este servidor a un workspace de ClickUp (solo admins)",
    )
    @app_commands.default_permissions(administrator=True)
    async def configurar_workspace(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            teams = await self.clickup.get_teams()
        except Exception as e:
            await interaction.followup.send(f"❌ No pude conectarme a ClickUp:\n```{e}```", ephemeral=True)
            return

        if not teams:
            await interaction.followup.send("❌ No se encontraron workspaces.", ephemeral=True)
            return

        current_id = self._team_id(interaction.guild_id)
        current_name = next((t["name"] for t in teams if str(t["id"]) == current_id), None)
        hint = f"\n\n*Workspace actual: **{current_name}***" if current_name else ""

        view = _WorkspaceSelectView(teams, interaction.guild_id)
        await interaction.followup.send(
            f"Selecciona el workspace de ClickUp para **{interaction.guild.name}**:{hint}",
            view=view,
            ephemeral=True,
        )


class _WorkspaceSelectView(discord.ui.View):
    def __init__(self, teams: list, guild_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label=t["name"][:100], value=str(t["id"]))
            for t in teams
        ]
        select = discord.ui.Select(placeholder="Elige un workspace...", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        team_id = interaction.data["values"][0]
        data = _load_workspaces()
        data[str(self.guild_id)] = team_id
        _save_workspaces(data)
        await interaction.response.edit_message(
            content=f"✅ Workspace vinculado (`{team_id}`).\nYa puedes usar `/tarea` en este servidor.",
            view=None,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TareasCog(bot))
