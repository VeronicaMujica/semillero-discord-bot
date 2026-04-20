import discord
from discord import app_commands
from discord.ext import commands

from user_mapping import CLICKUP_TEAM, link, get_clickup_key, load_mapping, display_name


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def say(self, ctx, *, text: str):
        """Repite lo que escribas (!say Hola mundo)"""
        await ctx.send(text)

    @app_commands.command(
        name="vincular-clickup",
        description="Vinculá tu cuenta de Discord con tu usuario de ClickUp",
    )
    @app_commands.describe(persona="Elegí tu nombre en ClickUp")
    @app_commands.choices(
        persona=[
            app_commands.Choice(name="Isabella", value="isabella"),
            app_commands.Choice(name="Sofía", value="sofi"),
            app_commands.Choice(name="Verónica", value="veronica"),
            app_commands.Choice(name="Mery", value="mary"),
            app_commands.Choice(name="Rocío", value="rochi"),
            app_commands.Choice(name="Camila", value="cami"),
            app_commands.Choice(name="Roggert", value="roggert"),
            app_commands.Choice(name="Ronald", value="ronald"),
        ]
    )
    async def vincular_clickup(
        self,
        interaction: discord.Interaction,
        persona: app_commands.Choice[str],
    ):
        link(interaction.user.id, persona.value)
        info = CLICKUP_TEAM[persona.value]
        await interaction.response.send_message(
            f"✅ Vinculado: {interaction.user.mention} ↔ **{info['nombre']}** (ClickUp id `{info['id']}`).",
            ephemeral=True,
        )

    @app_commands.command(
        name="vinculos",
        description="Ver los vínculos Discord ↔ ClickUp registrados",
    )
    async def vinculos(self, interaction: discord.Interaction):
        data = load_mapping()
        if not data:
            await interaction.response.send_message(
                "Todavía no hay vínculos. Cada miembro puede usar `/vincular-clickup`.",
                ephemeral=True,
            )
            return

        lineas = ["🃏 **Vínculos Discord ↔ ClickUp:**"]
        for disc_id, ck_key in data.items():
            nombre = CLICKUP_TEAM.get(ck_key, {}).get("nombre", ck_key)
            lineas.append(f"• <@{disc_id}> → **{nombre}**")
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
