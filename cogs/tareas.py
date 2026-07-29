import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from clickup_client import ClickUpClient, ClickUpAPIError
from user_mapping import get_clickup_id

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

PRIORITY_MAP = {"urgente": 1, "alta": 2, "normal": 3, "baja": 4}
PRIORITY_COLOR = {"urgente": 0xE53935, "alta": 0xFB8C00, "normal": 0x1E88E5, "baja": 0x757575}
PRIORITY_EMOJI = {"urgente": "🔴", "alta": "🟠", "normal": "🔵", "baja": "⚪"}


def _parse_date_ms(date_str: str | None) -> int | None:
    """Convierte 'YYYY-MM-DD' a epoch en ms, anclado al mediodía de Argentina.

    El contenedor corre en UTC, así que un datetime naive a medianoche caía en
    el día anterior para la cuenta de ClickUp (de ahí el "día de retraso").
    Anclando al mediodía ART el timestamp cae SIEMPRE en el día correcto, sin
    importar la zona horaria del servidor ni la de la cuenta de ClickUp.
    """
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=12, minute=0, second=0, microsecond=0, tzinfo=ARG_TZ
    )
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
        # Un solo workspace/tablero: ya no hace falta /configurar-workspace.
        self.team_id = os.getenv("CLICKUP_TEAM_ID") or "9011755800"  # ronisa
        self.default_list_id = os.getenv("CLICKUP_LIST_ID") or None
        self.default_list_name = os.getenv("CLICKUP_LIST_NAME") or "Tablero principal"

    # ── Autocomplete ──────────────────────────────────────────────────────────

    async def _autocomplete_lista(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            lists = await self.clickup.get_all_lists(self.team_id)
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
        try:
            members = await self.clickup.get_members(self.team_id)
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
        responsable="Persona asignada",
        descripcion="Descripción (opcional)",
        prioridad="Prioridad de la tarea",
        fecha_limite="Fecha límite en formato YYYY-MM-DD (opcional)",
        lista="Tablero donde crear la tarea (opcional si hay tablero por defecto)",
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
        responsable: str,
        descripcion: str | None = None,
        prioridad: app_commands.Choice[str] | None = None,
        fecha_limite: str | None = None,
        lista: str | None = None,
    ):
        await interaction.response.defer()

        # Resolver tablero destino: el elegido, o el por defecto (CLICKUP_LIST_ID).
        if lista:
            list_id, list_name = _decode(lista)
        elif self.default_list_id:
            list_id, list_name = self.default_list_id, self.default_list_name
        else:
            await interaction.followup.send(
                "❌ No hay un tablero por defecto configurado. Elegí uno en la opción "
                "`lista`, o pedile a un admin que setee `CLICKUP_LIST_ID` en el `.env`."
            )
            return

        try:
            due_ms = _parse_date_ms(fecha_limite)
        except ValueError:
            await interaction.followup.send(
                "❌ La fecha debe estar en formato **YYYY-MM-DD** (ej: `2026-07-30`)."
            )
            return

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
                due_date_time=False if due_ms is not None else None,
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

        try:
            tasks = await self.clickup.get_all_team_tasks(
                self.team_id,
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


async def setup(bot: commands.Bot):
    await bot.add_cog(TareasCog(bot))
