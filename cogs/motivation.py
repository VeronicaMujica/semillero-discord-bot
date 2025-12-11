import discord
from discord.ext import commands, tasks
from pytz import timezone
import random
import datetime
import asyncio

# --- CONFIG USUARIOS / MENSAJES INTERACTIVOS ---

NOMBRES_BOT = ["semillero bot", "semillero-bot", "semillerobot"]

RESPUESTAS_MENCION = [
    "¿Me llamaron? 🌱 Estoy acá regando ideas.",
    "Presente, Semillero Bot reportándose 💻🌿",
    "Acá estoy, ¿qué vamos a sembrar hoy? ✨",
    "Yo escuché *Semillero bot* y vine corriendo 🌾"
]

RESPUESTAS_SALUDO = [
    "¡Hola equipo! 👋",
    "Ey, ¿cómo va ese jardín de ideas? 🌱",
    "Presente en la daily emocional ✋",
]

# --- HORARIO DEL SALUDO ---

TZ_ARG = timezone("America/Argentina/Buenos_Aires")
TARGET_HOUR_SALUDO = 8
TARGET_MIN_SALUDO = 20  # 👈 08:20

CHANNEL_ID = 1403086626149896283  # Canal del equipo


class MotivationCog(commands.Cog):
    """Cog de interacción y saludo diario para el equipo Semillero 🌱"""

    def __init__(self, bot):
        self.bot = bot
        self.saludo_inicial_loop.start()
        print("🗓️ Loop de saludo inicial iniciado (08:20 ARG)")

    # ======================================================
    # INTERACCIÓN CUANDO HABLAN DEL BOT
    # ======================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        contenido = message.content.lower()

        if any(nombre in contenido for nombre in NOMBRES_BOT):
            respuesta = random.choice(RESPUESTAS_MENCION)
            await message.channel.send(respuesta)

            try:
                await message.add_reaction("🌱")
            except:
                pass

        saludos = ["hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"]
        if any(s in contenido for s in saludos) and any(n in contenido for n in NOMBRES_BOT):
            await message.channel.send(random.choice(RESPUESTAS_SALUDO))

    # ======================================================
    # LOOP QUE ENVÍA EL SALUDO A LAS 08:20
    # ======================================================

    @tasks.loop(minutes=1)
    async def saludo_inicial_loop(self):
        ahora = datetime.datetime.now(TZ_ARG)

        if ahora.hour == TARGET_HOUR_SALUDO and ahora.minute == TARGET_MIN_SALUDO:
            await self.saludo_inicial()

    @saludo_inicial_loop.before_loop
    async def before_saludo_inicial(self):
        await self.bot.wait_until_ready()
        print("✅ Bot listo, saludo_inicial_loop corriendo...")

    # ======================================================
    # FUNCIÓN DEL SALUDO INICIAL
    # ======================================================

    async def saludo_inicial(self):
        """Mensaje inicial diario."""
        try:
            canal = self.bot.get_channel(CHANNEL_ID) or await self.bot.fetch_channel(CHANNEL_ID)

            mensaje = (
                "🌿 Equipo, acabo de ver ClickUp y está todo actualizado. Muy bien ahí 👀✨"
            )

            await canal.send(mensaje)
            print("[Motivation] ✅ Saludo inicial enviado.")
        except Exception as e:
            print(f"❌ Error en saludo_inicial: {e}")

    # ======================================================
    # 👉 COMANDO MANUAL PARA PROBAR EL SALUDO
    # ======================================================

    @commands.command(name="saludo")
    async def saludo_manual(self, ctx):
        """Permite ejecutar el saludo inicial manualmente."""
        await self.saludo_inicial()
        await ctx.send("🌱 Listo, saludo enviado manualmente.")

# --- SETUP DEL COG ---
async def setup(bot):
    await bot.add_cog(MotivationCog(bot))
