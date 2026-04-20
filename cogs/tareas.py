import os
import time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from clickup_client import ClickUpClient, ClickUpAPIError
from user_mapping import get_clickup_id, display_name


def parse_priority(value: str | None) -> int | None:
    if value is None:
        return None

    mapping = {
        "urgente": 1,
        "alta": 2,
        "normal": 3,
        "baja": 4,
    }
    return mapping.get(value.lower())


def parse_date_to_ms(date_str: str | None) -> int | None:
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


CLICKUP_USER_MAP = {
    "isabella": 81513581,
    "sofi": 120079719,
    "veronica": 156006388,
    "mary": 87398967,
    "rochi": 87374445,
    "cami": 81593143,
    "roggert": 81593142,
    "ronald": 81418149
}

CLICKUP_LIST_MAP = {
    "interno": os.getenv("CLICKUP_LIST_INTERNO"),
    "cliente_a": os.getenv("CLICKUP_LIST_CLIENTE_A"),
    "cliente_b": os.getenv("CLICKUP_LIST_CLIENTE_B"),
}


class TareasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clickup = ClickUpClient()

    @app_commands.command(name="tarea", description="Crear una tarea en ClickUp")
    @app_commands.describe(
        titulo="Nombre de la tarea",
        responsable="Responsable",
        proyecto="Proyecto o cliente",
        descripcion="Descripción opcional",
        prioridad="Prioridad",
        fecha_limite="Fecha límite en formato YYYY-MM-DD"
    )
    @app_commands.choices(
        responsable=[
            app_commands.Choice(name="Isabella", value="isabella"),
            app_commands.Choice(name="Sofía", value="sofi"),
            app_commands.Choice(name="Verónica", value="veronica"),
            app_commands.Choice(name="Mery", value="mary"),
            app_commands.Choice(name="Rocío", value="rochi"),
            app_commands.Choice(name="Camila", value="cami"),
            app_commands.Choice(name="Roggert", value="roggert"),
            app_commands.Choice(name="Ronald", value="ronald"),
        ],
        proyecto=[
            app_commands.Choice(name="Interno", value="interno"),
            app_commands.Choice(name="Cliente A", value="cliente_a"),
            app_commands.Choice(name="Cliente B", value="cliente_b"),
        ],
        prioridad=[
            app_commands.Choice(name="Urgente", value="urgente"),
            app_commands.Choice(name="Alta", value="alta"),
            app_commands.Choice(name="Normal", value="normal"),
            app_commands.Choice(name="Baja", value="baja"),
        ]
    )
    async def tarea(
        self,
        interaction: discord.Interaction,
        titulo: str,
        responsable: app_commands.Choice[str],
        proyecto: app_commands.Choice[str],
        descripcion: str | None = None,
        prioridad: app_commands.Choice[str] | None = None,
        fecha_limite: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            assignee_id = CLICKUP_USER_MAP.get(responsable.value)
            if not assignee_id:
                await interaction.followup.send(
                    f"❌ {responsable.name} todavía no tiene user_id de ClickUp configurado.",
                    ephemeral=True
                )
                return

            list_id = CLICKUP_LIST_MAP.get(proyecto.value)
            if not list_id:
                await interaction.followup.send(
                    "❌ Ese proyecto no tiene list_id de ClickUp configurado.",
                    ephemeral=True
                )
                return

            due_date = parse_date_to_ms(fecha_limite)
            priority_value = parse_priority(prioridad.value if prioridad else None)

            task = await self.clickup.create_task(
                list_id=list_id,
                name=titulo,
                description=descripcion or "",
                assignees=[assignee_id],
                priority=priority_value,
                due_date=due_date,
                tags=[proyecto.value],
            )

            task_url = task.get("url")
            msg = f"✅ Tarea creada: **{task.get('name', titulo)}**"

            if task_url:
                msg += f"\n🔗 {task_url}"

            await interaction.followup.send(msg, ephemeral=True)

        except ValueError:
            await interaction.followup.send(
                "❌ La fecha debe estar en formato YYYY-MM-DD.",
                ephemeral=True
            )
        except ClickUpAPIError as e:
            await interaction.followup.send(
                f"❌ Error al crear la tarea en ClickUp:\n`{e}`",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error inesperado:\n`{e}`",
                ephemeral=True
            )


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

        team_id = os.getenv("CLICKUP_TEAM_ID") or "9011755800"

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


async def setup(bot: commands.Bot):
    await bot.add_cog(TareasCog(bot))