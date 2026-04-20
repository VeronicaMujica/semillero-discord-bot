import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"🃏 Dealer Bot conectado como {bot.user}")
        print(f"🔁 Slash commands sincronizados: {len(synced)}")
    except Exception as e:
        print(f"⚠️ Error sincronizando slash commands: {e}")


async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"🔹 Módulo cargado: {filename}")
            except Exception as e:
                print(f"⚠️ Error cargando {filename}: {e}")


async def main():
    async with bot:
        await load_extensions()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("Falta DISCORD_TOKEN en el archivo .env")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
