import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Intents: controlan qué eventos puede ver tu bot
intents = discord.Intents.default()
intents.message_content = True

# Crear la instancia del bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Evento: cuando el bot está listo
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# Cargar módulos (cogs) de forma asíncrona
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"🔹 Módulo cargado: {filename}")
            except Exception as e:
                print(f"⚠️ Error cargando {filename}: {e}")

# Función principal asincrónica
async def main():
    async with bot:
        await load_extensions()
        await bot.start(os.getenv("DISCORD_TOKEN"))

# Ejecutar el bot
if __name__ == "__main__":
    asyncio.run(main())
