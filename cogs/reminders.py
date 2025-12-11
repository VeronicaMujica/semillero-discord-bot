import discord
from discord.ext import commands, tasks
from aiohttp import web
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
import re

# ✅ Conversión robusta del canal
try:
    CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_REMINDERS", "0"))
except:
    CHANNEL_ID = 0

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = web.Application()
        self.setup_routes()

        # ✅ Iniciamos el recordatorio diario
        self.daily_clickup_reminder.start()

    def setup_routes(self):
        self.app.router.add_post("/reminders", self.receive_reminders)

    async def receive_reminders(self, request):
        try:
            data = await request.json()

            # ✅ Si llega solo un objeto, se convierte en lista
            if isinstance(data, dict):
                data = [data]

            channel = self.bot.get_channel(CHANNEL_ID)
            if not channel:
                return web.json_response(
                    {"error": "Channel not found", "channel_id": CHANNEL_ID},
                    status=500
                )

            message = self.format_message(data)
            await channel.send(message)

            return web.json_response({"status": "ok", "sent": len(data)})

        except Exception as e:
            print("Error Webhook:", e)
            return web.json_response({"error": str(e)}, status=500)

    # ✅ ✅ ✅ NUEVO: Recordatorio diario ClickUp — 9:30 ARG
    @tasks.loop(minutes=1)
    async def daily_clickup_reminder(self):
        now = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        target = time(9, 30)

        if now.hour == target.hour and now.minute == target.minute:
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(
                    "⏰ **Recordatorio diario**\n"
                    "Chicos, actualicen los estados en **ClickUp** antes de seguir el día 🙌\n"
                    "Esto nos mantiene sincronizados y evita cuellos de botella 🌱🔥"
                )

    @daily_clickup_reminder.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    def format_message(self, tasks):
        emojis = {
            "Ronald Vargas": "🔥",
            "Isabella Lantieri": "🌱",
            "Sofía Lantieri": "🌻",
            "Roggert Bernal": "☀️",
            "Camila Torres": "🩷",
            "Sin asignar": "👤"
        }

        grouped = {}

        for t in tasks:
            assignee = t.get("assignees")

            if isinstance(assignee, list) and assignee:
                assignee = assignee[0]
            elif not assignee:
                assignee = "Sin asignar"

            grouped.setdefault(assignee, []).append(t)

        now = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
        hour = now.hour

        if 5 <= hour < 12:
            saludo = "☀️ **¡Buenos días!**"
            intro = "Estas son tus tareas del día de hoy:"
        elif 12 <= hour < 18:
            saludo = "🌇 **¡Buenas tardes!**"
            intro = "Aquí va un recordatorio de tus tareas pendientes:"
        else:
            saludo = "🌙 **¡Buenas noches!**"
            intro = "Un último repaso de tus tareas del día:"

        text = f"👋 {saludo}\n{intro}\n\n"

        for assignee, items in grouped.items():
            emoji = emojis.get(assignee, "👤")
            text += f"{emoji} **{assignee}**\n"

            for task in items:
                nombre = task.get("name", "Sin nombre")
                estado = task.get("status", "Sin estado")

                nombre = re.sub(r'[^\w\sÁÉÍÓÚáéíóúñÑüÜ/().,-]', '', nombre)
                nombre = nombre.replace('|', '').strip()

                text += f"- {nombre} (Estado: {estado})\n"

            text += "\n"

        return text.strip()
    
    @commands.command(name="mensaje")
    async def mensaje_clickup(self, ctx):
        await ctx.send(
            "✅ Ya están subidas las tareas a ClickUp chicos.\n"
            "Por favor revisen si todo está correcto 🙌\n"
            "_A veces me puedo equivocar 😅_"
        )

async def setup(bot):
    reminders = Reminders(bot)

    # Registrar los comandos del Cog
    await bot.add_cog(reminders)

    runner = web.AppRunner(reminders.app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 4000)
    await site.start()
