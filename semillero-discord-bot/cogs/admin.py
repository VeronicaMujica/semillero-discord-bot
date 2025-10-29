from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def say(self, ctx, *, text: str):
        """Repite lo que escribas (comando !say Hola mundo)"""
        await ctx.send(text)

async def setup(bot):
    await bot.add_cog(Admin(bot))