import asyncio
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

# Cada cuánto refrescamos en segundo plano la lista de tableros/miembros.
REFRESH_EVERY_SECONDS = 300

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
        # Un solo workspace: ya no hace falta /configurar-workspace.
        self.team_id = os.getenv("CLICKUP_TEAM_ID") or "9011755800"  # ronisa

        # Cache en memoria para que el autocomplete responda YA (sin esperar a
        # ClickUp). Se precarga al arrancar y se refresca en segundo plano, así
        # el listado de tableros de ronisa no "falla la primera vez".
        self._lists_cache: list[dict] = []
        self._members_cache: list[dict] = []
        self._refresh_task = None

    # ── Ciclo de vida: precarga en segundo plano ───────────────────────────────

    async def cog_load(self):
        try:
            self._refresh_task = asyncio.create_task(self._refresh_loop())
        except Exception as e:
            log.warning(f"No pude iniciar la precarga de /tarea: {e}")

    def cog_unload(self):
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()

    async def _refresh_loop(self):
        try:
            await self.bot.wait_until_ready()
        except Exception:
            pass
        while True:
            await self._safe_refresh()
            await asyncio.sleep(REFRESH_EVERY_SECONDS)

    async def _safe_refresh(self):
        try:
            lists = await self.clickup.get_all_lists(self.team_id)
            members = await self.clickup.get_members(self.team_id)
            if lists:
                self._lists_cache = lists
            if members:
                self._members_cache = members
            log.info(
                f"Autocomplete precargado: {len(self._lists_cache)} tableros, "
                f"{len(self._members_cache)} miembros."
            )
        except Exception as e:
            log.warning(f"No pude precargar el autocomplete de /tarea: {e}")

    # ── Autocomplete (cache-first, con fallback en vivo; nunca rompe) ───────────

    async def _autocomplete_lista(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            data = self._lists_cache
            if not data:
                # Cache aún fría: la traigo en vivo (como antes) y la guardo.
                data = await self.clickup.get_all_lists(self.team_id)
                if data:
                    self._lists_cache = data
            needle = current.lower()
            choices: list[app_commands.Choice[str]] = []
            for lst in data:
                name = (lst.get("name") or "").strip()
                if not name:
                    continue
                label = f"{lst['folder']} › {name}" if lst.get("folder") else name
                if needle in label.lower():
                    choices.append(app_commands.Choice(
                        name=label[:100],
                        value=_encode(str(lst["id"]), name),
                    ))
                    if len(choices) >= 25:
                        break
            return choices
        except Exception as e:
            log.warning(f"autocomplete /tarea lista: {e}")
            return []

    async def _autocomplete_responsable(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            data = self._members_cache
            if not data:
                data = await self.clickup.get_members(self.team_id)
                if data:
                    self._members_cache = data
            needle = current.lower()
            choices: list[app_commands.Choice[str]] = []
            for m in data:
                name = (m.get("name") or "").strip()
                if not name:
                    continue
                if needle in name.lower():
                    choices.append(app_commands.Choice(
                        name=name[:100],
                        value=_encode(str(m["id"]), name),
                    ))
                    if len(choices) >= 25:
                        break
            return choices
        except Exception as e:
            log.warning(f"autocomplete /tarea responsable: {e}")
            return []

    # ── /tarea ────────────────────────────────────────────────────────────────

    @app_commands.command(name="tarea", description="Crear una tarea en ClickUp")
    @app_commands.describe(
        titulo="Nombre de la tarea",
        lista="Tablero o lista de ClickUp donde crear la tarea",
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
        await interaction.response.defer()

        list_id, list_name = _decode(lista)

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
