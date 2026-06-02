import random

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

        # Solo responde si lo mencionan directamente
        if self.bot.user and self.bot.user.mentioned_in(message):
            # Evitar @everyone / role mentions
            if message.mention_everyone:
                return
            await message.channel.send(random.choice(RESPUESTAS_MENCION))


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
