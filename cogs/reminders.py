import discord
from discord.ext import commands
from aiohttp import web
import json
import os
import re  

# ✅ Conversion robusta del canal
try:
    CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_REMINDERS", "0"))
except:
    CHANNEL_ID = 0

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        self.app.router.add_post("/reminders", self.receive_reminders)

    async def receive_reminders(self, request):
        try:
            data = await request.json()

            # ✅ Si llega solo un objeto, lo convertimos a lista
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

            # ✅ Respuesta JSON válida
            return web.json_response({"status": "ok", "sent": len(data)})

        except Exception as e:
            print("Error Webhook:", e)
            return web.json_response({"error": str(e)}, status=500)

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

        text = "👋 **¡Buenos días!**\nEstas son tus tareas del día de hoy:\n\n"

        for assignee, items in grouped.items():
            emoji = emojis.get(assignee, "👤")
            text += f"{emoji} **{assignee}**\n"

            for task in items:
                nombre = task.get("name", "Sin nombre")
                estado = task.get("status", "Sin estado")

                # 🧹 Limpieza: quita emojis, barras y espacios extra
                nombre = re.sub(r'[^\w\sÁÉÍÓÚáéíóúñÑüÜ/().,-]', '', nombre)
                nombre = nombre.replace('|', '').strip()

                text += f"- {nombre} (Estado: {estado})\n"

            text += "\n"

        return text.strip()

async def setup(bot):
    reminders = Reminders(bot)

    runner = web.AppRunner(reminders.app)
    await runner.setup()

    # ✅ expuesto correctamente
    site = web.TCPSite(runner, "0.0.0.0", 4000)
    await site.start()

    await bot.add_cog(reminders)
