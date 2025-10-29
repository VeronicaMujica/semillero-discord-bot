import discord
from discord.ext import commands
from aiohttp import web
import json
import os

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
        if not tasks:
            return "✅ No hay tareas para hoy"

        grouped = {}

        # ✅ Tasks ya llegan una por request → juntaremos todo
        for t in tasks:
            assignee = t.get("assignees", "Sin asignar")
            grouped.setdefault(assignee, []).append(t)

        lines = []
        for assignee, items in grouped.items():
            lines.append(f"👤 **{assignee}**")
            for task in items:
                nombre = task.get("name", "Sin nombre")
                estado = task.get("status", "Sin estado")
                lines.append(f"- {nombre} _(Estado: {estado})_")
            lines.append("")  # salto

        # ✅ Encabezado solo una vez
        return "👋 **¡Buenos días!**\nEstas son tus tareas del día de hoy:\n\n" + "\n".join(lines)


async def setup(bot):
    reminders = Reminders(bot)

    runner = web.AppRunner(reminders.app)
    await runner.setup()

    # ✅ expuesto correctamente
    site = web.TCPSite(runner, "0.0.0.0", 4000)
    await site.start()

    await bot.add_cog(reminders)
