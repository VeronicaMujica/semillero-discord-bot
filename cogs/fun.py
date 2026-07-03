import random
import re

import discord
from discord.ext import commands


RESPUESTAS_MENCION = [
    "🃏 ¿Me llamaste? El Dealer está en la mesa.",
    "🎲 Acá estoy. ¿Repartimos una mano o hablamos de ClickUp?",
    "☕ Presente. Probá con `/mis-tareas` o `/atrasadas`.",
    "🔥 Listo para jugar. ¿Qué necesitás?",
    "🎯 Dealer a la orden. Mis comandos: `/tarea`, `/evento`, `/mis-tareas`, `/atrasadas`, `/resumen-semanal`, `/motivacion`.",
    "🃏 La casa siempre paga. Decime qué hacemos.",
    "✨ Acá. ¿Una frase del Dealer? Probá `/motivacion`.",
]


# Reacciones automáticas por palabras clave — SOLO emojis, sin texto.
# Cada regla es (regex compilado, lista de emojis a poner como reacción).
# Máx 3 emojis por mensaje. Silencioso si no matchea.
REACCIONES_AUTO = [
    # Celebrar cierres / logros / entregas
    (
        re.compile(
            r"\b(cerr[eé]|cerrad[ao]s?|termin[eéo]|terminad[ao]s?|"
            r"logr[eé]|logrado|logrados|logrados?|completad[ao]s?|listo)\b",
            re.IGNORECASE,
        ),
        ["🎉", "🃏"],
    ),
    # Agradecimientos
    (
        re.compile(r"\bgracias\b|\bgrax\b", re.IGNORECASE),
        ["🙏"],
    ),
    # Cumpleaños
    (
        re.compile(r"\bfeliz\s+cumple(años)?\b|\bcumplea[ñn]os\b", re.IGNORECASE),
        ["🎂", "🎉"],
    ),
    # Buen finde
    (
        re.compile(r"\bbuen\s+(finde|fin\s+de\s+semana)\b", re.IGNORECASE),
        ["🌴"],
    ),
    # Link a tarea de ClickUp
    (
        re.compile(r"app\.clickup\.com/t/", re.IGNORECASE),
        ["🃏"],
    ),
    # Aprobación / confirmación
    (
        re.compile(r"\baprobad[ao]s?\b|\bconfirmad[ao]s?\b", re.IGNORECASE),
        ["✅"],
    ),
    # Ideas / propuestas
    (
        re.compile(r"\bidea\b|\bpropongo\b", re.IGNORECASE),
        ["💡"],
    ),
    # Reunión / meet / call
    (
        re.compile(r"\b(reuni[oó]n|meet|call|junta)\b", re.IGNORECASE),
        ["📞"],
    ),
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("🃏 Pong desde Dealer Bot.")

    async def _reaccionar_por_keywords(self, message: discord.Message) -> None:
        text = message.content or ""
        if not text:
            return
        # Evitar sobre-reaccionar: máximo 3 emojis por mensaje
        emojis: list[str] = []
        for pattern, candidatos in REACCIONES_AUTO:
            if pattern.search(text):
                for e in candidatos:
                    if e not in emojis:
                        emojis.append(e)
            if len(emojis) >= 3:
                break
        for emoji in emojis[:3]:
            try:
                await message.add_reaction(emoji)
            except discord.DiscordException:
                # Sin permisos, emoji inválido, mensaje borrado, etc. — ignorar
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Mención directa al bot → responde con texto
        if self.bot.user and self.bot.user.mentioned_in(message):
            if message.mention_everyone:
                return
            await message.channel.send(random.choice(RESPUESTAS_MENCION))
            return

        # Sino, reaccionar con emojis según keywords
        await self._reaccionar_por_keywords(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
