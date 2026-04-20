import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"🃏 Dealer Bot conectado como {bot.user}")
    # Sync por servidor (instantáneo) + sync global (hasta 1h)
    for guild in bot.guilds:
        try:
            await bot.tree.sync(guild=guild)
            print(f"🔁 Slash commands sincronizados en: {guild.name}")
        except Exception as e:
            print(f"⚠️ Error sincronizando en {guild.name}: {e}")
    try:
        await bot.tree.sync()
        print("🌐 Sync global completado")
    except Exception as e:
        print(f"⚠️ Error en sync global: {e}")


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
