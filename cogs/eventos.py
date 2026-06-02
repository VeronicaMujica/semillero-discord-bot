import calendar
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from google_calendar_client import GoogleCalendarClient, GoogleCalendarError

log = logging.getLogger(__name__)

TZ_NAME = "America/Argentina/Buenos_Aires"
TZ = ZoneInfo(TZ_NAME)

MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _render_month_grid(year: int, month: int) -> str:
    """Dibuja el mes en monospace para el embed."""
    cal = calendar.Calendar(firstweekday=0)  # Lunes
    weeks = cal.monthdayscalendar(year, month)

    lines = ["Lu Ma Mi Ju Vi Sá Do"]
    for week in weeks:
        cells = ["  " if day == 0 else f"{day:>2}" for day in week]
        lines.append(" ".join(cells))
    return "```\n" + "\n".join(lines) + "\n```"


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    new_index = (year * 12 + (month - 1)) + delta
    return new_index // 12, (new_index % 12) + 1


def _build_calendar_embed(year: int, month: int, *, title: str) -> discord.Embed:
    today = datetime.now(TZ).date()
    hint = ""
    if today.year == year and today.month == month:
        hint = f"\n📍 Hoy: **{today.day}**"
    embed = discord.Embed(
        title="🃏 Programar evento",
        description=(
            f"### {title}\n"
            f"📅 **{MONTH_NAMES_ES[month - 1]} {year}**\n"
            f"{_render_month_grid(year, month)}"
            f"{hint}\n"
            f"_Usá los botones para cambiar de mes y el select para elegir el día._"
        ),
        color=0x4285F4,
    )
    embed.set_footer(text="Zona horaria: Argentina/Buenos Aires")
    return embed


class _CalendarView(discord.ui.View):
    def __init__(
        self,
        cog: "EventosCog",
        *,
        title: str,
        descripcion: str | None,
        year: int,
        month: int,
        author_id: int,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.title = title
        self.descripcion = descripcion
        self.year = year
        self.month = month
        self.author_id = author_id
        self._rebuild()

    def _rebuild(self):
        self.clear_items()

        # Row 0: navegación de mes
        prev_btn = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, row=0)
        prev_btn.callback = self._prev_month
        label_btn = discord.ui.Button(
            label=f"{MONTH_NAMES_ES[self.month - 1]} {self.year}",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=True,
        )
        next_btn = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, row=0)
        next_btn.callback = self._next_month
        today_btn = discord.ui.Button(label="Hoy", style=discord.ButtonStyle.success, row=0)
        today_btn.callback = self._jump_today
        self.add_item(prev_btn)
        self.add_item(label_btn)
        self.add_item(next_btn)
        self.add_item(today_btn)

        # Row 1-2: selects de día (split si el mes pasa de 25 días)
        last = _last_day_of_month(self.year, self.month)
        first_chunk = list(range(1, min(25, last) + 1))
        second_chunk = list(range(26, last + 1)) if last > 25 else []

        sel1 = discord.ui.Select(
            placeholder=f"Elegí el día (1 – {first_chunk[-1]})",
            options=[discord.SelectOption(label=str(d), value=str(d)) for d in first_chunk],
            row=1,
        )
        sel1.callback = self._on_day
        self.add_item(sel1)

        if second_chunk:
            sel2 = discord.ui.Select(
                placeholder=f"Elegí el día (26 – {second_chunk[-1]})",
                options=[discord.SelectOption(label=str(d), value=str(d)) for d in second_chunk],
                row=2,
            )
            sel2.callback = self._on_day
            self.add_item(sel2)

        # Row 4: cancelar
        cancel_btn = discord.ui.Button(label="Cancelar", style=discord.ButtonStyle.danger, row=4)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Este calendario lo abrió otra persona.", ephemeral=True
            )
            return False
        return True

    async def _prev_month(self, interaction: discord.Interaction):
        self.year, self.month = _shift_month(self.year, self.month, -1)
        self._rebuild()
        await interaction.response.edit_message(
            embed=_build_calendar_embed(self.year, self.month, title=self.title),
            view=self,
        )

    async def _next_month(self, interaction: discord.Interaction):
        self.year, self.month = _shift_month(self.year, self.month, 1)
        self._rebuild()
        await interaction.response.edit_message(
            embed=_build_calendar_embed(self.year, self.month, title=self.title),
            view=self,
        )

    async def _jump_today(self, interaction: discord.Interaction):
        now = datetime.now(TZ)
        self.year, self.month = now.year, now.month
        self._rebuild()
        await interaction.response.edit_message(
            embed=_build_calendar_embed(self.year, self.month, title=self.title),
            view=self,
        )

    async def _on_day(self, interaction: discord.Interaction):
        day = int(interaction.data["values"][0])
        view = _TimeView(
            cog=self.cog,
            title=self.title,
            descripcion=self.descripcion,
            year=self.year,
            month=self.month,
            day=day,
            author_id=self.author_id,
        )
        await interaction.response.edit_message(
            embed=view.build_embed(),
            view=view,
        )

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="❌ Programación cancelada.",
            embed=None,
            view=None,
        )
        self.stop()


HOURS = [f"{h:02d}" for h in range(0, 24)]
MINUTES = ["00", "15", "30", "45"]


class _TimeView(discord.ui.View):
    def __init__(
        self,
        *,
        cog: "EventosCog",
        title: str,
        descripcion: str | None,
        year: int,
        month: int,
        day: int,
        author_id: int,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.title = title
        self.descripcion = descripcion
        self.year = year
        self.month = month
        self.day = day
        self.author_id = author_id

        now = datetime.now(TZ)
        default_start_h = now.hour + 1 if now.hour < 22 else 9
        self.start_h = f"{default_start_h:02d}"
        self.start_m = "00"
        self.end_h = f"{(default_start_h + 1) % 24:02d}"
        self.end_m = "00"

        self._rebuild()

    def build_embed(self) -> discord.Embed:
        weekday_es = [
            "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
        ][datetime(self.year, self.month, self.day).weekday()]
        embed = discord.Embed(
            title="🃏 Programar evento",
            description=(
                f"### {self.title}\n"
                f"📅 **{weekday_es} {self.day} de {MONTH_NAMES_ES[self.month - 1]} {self.year}**\n\n"
                f"🕐 **Inicio:** `{self.start_h}:{self.start_m}`\n"
                f"🕔 **Fin:** `{self.end_h}:{self.end_m}`\n\n"
                f"_Ajustá los selects y confirmá para crear el evento._"
            ),
            color=0x4285F4,
        )
        if self.descripcion:
            embed.add_field(name="📝 Descripción", value=self.descripcion[:1024], inline=False)
        embed.set_footer(text="Zona horaria: Argentina/Buenos Aires")
        return embed

    def _rebuild(self):
        self.clear_items()

        sh = discord.ui.Select(
            placeholder=f"Hora inicio · actual {self.start_h}",
            options=[
                discord.SelectOption(label=f"{h}:00", value=h, default=(h == self.start_h))
                for h in HOURS
            ],
            row=0,
        )
        sh.callback = self._on_start_h
        self.add_item(sh)

        sm = discord.ui.Select(
            placeholder=f"Minuto inicio · actual {self.start_m}",
            options=[
                discord.SelectOption(label=f":{m}", value=m, default=(m == self.start_m))
                for m in MINUTES
            ],
            row=1,
        )
        sm.callback = self._on_start_m
        self.add_item(sm)

        eh = discord.ui.Select(
            placeholder=f"Hora fin · actual {self.end_h}",
            options=[
                discord.SelectOption(label=f"{h}:00", value=h, default=(h == self.end_h))
                for h in HOURS
            ],
            row=2,
        )
        eh.callback = self._on_end_h
        self.add_item(eh)

        em = discord.ui.Select(
            placeholder=f"Minuto fin · actual {self.end_m}",
            options=[
                discord.SelectOption(label=f":{m}", value=m, default=(m == self.end_m))
                for m in MINUTES
            ],
            row=3,
        )
        em.callback = self._on_end_m
        self.add_item(em)

        back_btn = discord.ui.Button(
            label="◀ Cambiar día", style=discord.ButtonStyle.secondary, row=4
        )
        back_btn.callback = self._back
        self.add_item(back_btn)

        confirm_btn = discord.ui.Button(
            label="✅ Crear evento", style=discord.ButtonStyle.success, row=4
        )
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)

        cancel_btn = discord.ui.Button(
            label="Cancelar", style=discord.ButtonStyle.danger, row=4
        )
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Este calendario lo abrió otra persona.", ephemeral=True
            )
            return False
        return True

    async def _on_start_h(self, interaction: discord.Interaction):
        self.start_h = interaction.data["values"][0]
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_start_m(self, interaction: discord.Interaction):
        self.start_m = interaction.data["values"][0]
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_end_h(self, interaction: discord.Interaction):
        self.end_h = interaction.data["values"][0]
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_end_m(self, interaction: discord.Interaction):
        self.end_m = interaction.data["values"][0]
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _back(self, interaction: discord.Interaction):
        view = _CalendarView(
            cog=self.cog,
            title=self.title,
            descripcion=self.descripcion,
            year=self.year,
            month=self.month,
            author_id=self.author_id,
        )
        await interaction.response.edit_message(
            embed=_build_calendar_embed(self.year, self.month, title=self.title),
            view=view,
        )

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="❌ Programación cancelada.",
            embed=None,
            view=None,
        )
        self.stop()

    async def _confirm(self, interaction: discord.Interaction):
        start_dt = datetime(
            self.year, self.month, self.day, int(self.start_h), int(self.start_m), tzinfo=TZ
        )
        end_dt = datetime(
            self.year, self.month, self.day, int(self.end_h), int(self.end_m), tzinfo=TZ
        )

        if end_dt <= start_dt:
            await interaction.response.send_message(
                "⏰ La hora de fin tiene que ser **después** del inicio.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            event = await self.cog.calendar.create_event(
                title=self.title,
                start_dt=start_dt,
                end_dt=end_dt,
                description=self.descripcion,
                tz=TZ_NAME,
            )
        except GoogleCalendarError as e:
            await interaction.followup.send(
                f"❌ Error creando el evento:\n```{e}```", ephemeral=True
            )
            return
        except Exception as e:
            log.exception("Error inesperado creando evento")
            await interaction.followup.send(
                f"❌ Error inesperado:\n```{e}```", ephemeral=True
            )
            return

        # Cerrar el picker ephemeral
        await interaction.edit_original_response(
            content="✅ Evento creado.", embed=None, view=None
        )

        embed = discord.Embed(
            title="🃏 Evento en la mesa",
            description=f"### {self.title}",
            color=0x4285F4,
            url=event.get("htmlLink"),
        )
        ts_start = int(start_dt.timestamp())
        ts_end = int(end_dt.timestamp())
        embed.add_field(
            name="🕐 Cuándo",
            value=f"<t:{ts_start}:F> → <t:{ts_end}:t>",
            inline=False,
        )
        embed.add_field(
            name="⏳ En tu zona",
            value=f"<t:{ts_start}:R>",
            inline=True,
        )
        if self.descripcion:
            embed.add_field(name="📝 Descripción", value=self.descripcion[:1024], inline=False)
        if event.get("htmlLink"):
            embed.add_field(
                name="🔗 Abrir en Google Calendar",
                value=event["htmlLink"],
                inline=False,
            )
        embed.set_footer(text=f"Programado por {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)
        self.stop()


class EventosCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            self.calendar = GoogleCalendarClient()
            self._ready = True
        except Exception as e:
            log.warning(f"Google Calendar no configurado: {e}")
            self.calendar = None
            self._ready = False
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )

    def _primary_guild_id(self) -> int | None:
        """El server principal es donde vive DEALER_CHANNEL_ID."""
        if not self.channel_id:
            return None
        ch = self.bot.get_channel(self.channel_id)
        if ch is None or ch.guild is None:
            return None
        return ch.guild.id

    @app_commands.command(
        name="evento",
        description="Crear un evento en Google Calendar con un mini-calendario interactivo",
    )
    @app_commands.describe(
        titulo="Nombre del evento",
        descripcion="Descripción (opcional)",
    )
    async def evento(
        self,
        interaction: discord.Interaction,
        titulo: str,
        descripcion: str | None = None,
    ):
        primary = self._primary_guild_id()
        if primary is not None and interaction.guild_id != primary:
            await interaction.response.send_message(
                "🃏 Los eventos del Dealer solo se crean en el server principal "
                "(donde vive el calendar). Acá no.",
                ephemeral=True,
            )
            return

        if not self._ready or self.calendar is None:
            await interaction.response.send_message(
                "❌ Google Calendar no está configurado. "
                "Faltan `GOOGLE_SERVICE_ACCOUNT_FILE` (o `GOOGLE_SERVICE_ACCOUNT_JSON`) "
                "y `GOOGLE_CALENDAR_ID` en el `.env`.",
                ephemeral=True,
            )
            return

        now = datetime.now(TZ)
        view = _CalendarView(
            cog=self,
            title=titulo,
            descripcion=descripcion,
            year=now.year,
            month=now.month,
            author_id=interaction.user.id,
        )
        await interaction.response.send_message(
            embed=_build_calendar_embed(now.year, now.month, title=titulo),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EventosCog(bot))
