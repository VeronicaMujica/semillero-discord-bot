import random

import discord
from discord.ext import commands


RESPUESTAS_MENCION = [
    "🃏 ¿Me llamaste? El Dealer está en la mesa.",
    "🎲 Acá estoy. ¿Repartimos una mano o hablamos de ClickUp?",
    "☕ Presente. Probá con `/mis-tareas` o `/atrasadas`.",
    "🔥 Listo para jugar. ¿Qué necesitás?",
    "🎯 Dealer a la orden. Mis comandos: `/tarea`, `/mis-tareas`, `/atrasadas`, `/resumen-semanal`, `/motivacion`.",
    "🃏 La casa siempre paga. Decime qué hacemos.",
    "✨ Acá. ¿Una frase del Dealer? Probá `/motivacion`.",
]

TRIGGER_KEYWORDS = {
    "gracias": "🃏 De nada. La casa agradece también.",
    "buen dia": "☕ Buen día. El Dealer ya está calentando la mesa.",
    "buenos dias": "☕ Buenos días. ¿Arrancamos?",
    "buenas noches": "🌙 Buenas noches. Mañana se sigue jugando.",
}


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("🃏 Pong desde Dealer Bot.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Mención directa al bot
        if self.bot.user and self.bot.user.mentioned_in(message):
            # Evitar @everyone / role mentions de trigger
            if message.mention_everyone:
                return
            await message.channel.send(random.choice(RESPUESTAS_MENCION))
            return

        # Trigger por saludo/agradecimiento (bajo para no spamear)
        texto = message.content.lower()
        for kw, reply in TRIGGER_KEYWORDS.items():
            if kw in texto and random.random() < 0.15:
                try:
                    await message.add_reaction("🃏")
                except discord.DiscordException:
                    pass
                await message.channel.send(reply)
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
