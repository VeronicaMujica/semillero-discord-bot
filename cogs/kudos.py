import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
KUDOS_FILE = Path(__file__).resolve().parent.parent / "data" / "kudos.json"


def _ensure_file():
    KUDOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not KUDOS_FILE.exists():
        KUDOS_FILE.write_text("[]", encoding="utf-8")


def _load() -> list[dict]:
    _ensure_file()
    try:
        return json.loads(KUDOS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save(data: list[dict]):
    _ensure_file()
    KUDOS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _since(days: int) -> list[dict]:
    cutoff = (datetime.now(ARG_TZ) - timedelta(days=days)).isoformat()
    return [k for k in _load() if k.get("timestamp", "") >= cutoff]


class KudosCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )

    def _primary_guild_id(self) -> int | None:
        """El server 'principal' es donde vive DEALER_CHANNEL_ID."""
        if not self.channel_id:
            return None
        ch = self.bot.get_channel(self.channel_id)
        if ch is None or ch.guild is None:
            return None
        return ch.guild.id

    async def _reject_if_not_primary(self, interaction: discord.Interaction) -> bool:
        """True si fue rechazada (no es el server principal)."""
        primary = self._primary_guild_id()
        if primary is None or interaction.guild_id == primary:
            return False
        await interaction.response.send_message(
            "🃏 El sistema de **kudos** vive solo en el server principal del Dealer. "
            "Acá no se registran.",
            ephemeral=True,
        )
        return True

    async def cog_load(self):
        # Viernes 17:30 → ranking semanal
        self.scheduler.add_job(
            self.post_ranking_semanal,
            "cron",
            day_of_week="fri",
            hour=17,
            minute=30,
            id="kudos_weekly",
            replace_existing=True,
        )
        self.scheduler.start()
        log.info("KudosCog scheduler iniciado.")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # ── /kudos ─────────────────────────────────────────────────────────────

    @app_commands.command(
        name="kudos",
        description="Reconocé a alguien del equipo por algo que hizo bien",
    )
    @app_commands.describe(
        persona="A quién va el reconocimiento",
        razon="Por qué se lo merece",
    )
    async def kudos(
        self,
        interaction: discord.Interaction,
        persona: discord.Member,
        razon: str,
    ):
        if await self._reject_if_not_primary(interaction):
            return
        if persona.id == interaction.user.id:
            await interaction.response.send_message(
                "🙃 No te podés dar kudos a vos misma. Convocá a alguien más.",
                ephemeral=True,
            )
            return
        if persona.bot:
            await interaction.response.send_message(
                "🤖 Los bots no juntan kudos (todavía).", ephemeral=True
            )
            return

        data = _load()
        data.append({
            "timestamp": datetime.now(ARG_TZ).isoformat(),
            "from_id": str(interaction.user.id),
            "from_name": interaction.user.display_name,
            "to_id": str(persona.id),
            "to_name": persona.display_name,
            "reason": razon[:500],
            "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
        })
        _save(data)

        embed = discord.Embed(
            title="🏆 Kudos repartidos",
            description=f"### Para {persona.mention}\n_{razon}_",
            color=0xFFD700,
        )
        embed.set_footer(
            text=f"Reconocido por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.response.send_message(embed=embed)

    # ── /kudos-ranking ─────────────────────────────────────────────────────

    @app_commands.command(
        name="kudos-ranking",
        description="Ver el ranking de kudos (últimos 7 días por default)",
    )
    @app_commands.describe(dias="Días hacia atrás (default 7)")
    async def kudos_ranking(
        self,
        interaction: discord.Interaction,
        dias: int | None = 7,
    ):
        if await self._reject_if_not_primary(interaction):
            return
        dias = max(1, min(dias or 7, 365))
        await interaction.response.defer()

        items = _since(dias)
        if not items:
            await interaction.followup.send(
                f"✨ Sin kudos en los últimos {dias} días. Tiempo de empezar a repartir."
            )
            return

        # Top recibidos
        recibidos = Counter((k["to_id"], k["to_name"]) for k in items)
        # Top dadores
        dados = Counter((k["from_id"], k["from_name"]) for k in items)

        medallas = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(
            title=f"🏆 Ranking de kudos · últimos {dias} días",
            color=0xFFD700,
            description=f"Total repartidos: **{len(items)}**",
        )

        top_rec = recibidos.most_common(5)
        if top_rec:
            lineas = []
            for idx, ((uid, name), cant) in enumerate(top_rec):
                m = medallas[idx] if idx < 3 else "•"
                lineas.append(f"{m} <@{uid}> — **{cant}**")
            embed.add_field(name="📥 Más reconocidos", value="\n".join(lineas), inline=False)

        top_dad = dados.most_common(3)
        if top_dad:
            lineas = [f"💛 <@{uid}> — {cant}" for (uid, name), cant in top_dad]
            embed.add_field(name="🎁 Más generosos", value="\n".join(lineas), inline=False)

        await interaction.followup.send(embed=embed)

    # ── job semanal ────────────────────────────────────────────────────────

    async def post_ranking_semanal(self):
        if not self.channel_id:
            log.warning("No hay DEALER_CHANNEL_ID configurado.")
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            log.warning(f"Canal {self.channel_id} no encontrado para kudos.")
            return

        items = _since(7)
        if not items:
            return  # no spamear si no hubo kudos

        recibidos = Counter((k["to_id"], k["to_name"]) for k in items)
        medallas = ["🥇", "🥈", "🥉"]
        lineas = ["🏆 **Kudos de la semana**\n"]
        for idx, ((uid, name), cant) in enumerate(recibidos.most_common(5)):
            m = medallas[idx] if idx < 3 else "•"
            lineas.append(f"{m} <@{uid}> — **{cant}** kudos")
        lineas.append(f"\n_{len(items)} reconocimientos repartidos esta semana 💛_")

        try:
            await channel.send("\n".join(lineas))
        except discord.DiscordException as e:
            log.error(f"Error posteando ranking kudos: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(KudosCog(bot))
