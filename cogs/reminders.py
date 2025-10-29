import discord
from discord.ext import commands
from aiohttp import web
import json
import os

CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_REMINDERS"))

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

            channel = self.bot.get_channel(CHANNEL_ID)
            if not channel:
                return web.Response(status=500, text="Channel not found")

            message = self.format_message(data)
            await channel.send(message)

            return web.Response(status=200, text="Ok enviado a Discord ✅")

        except Exception as e:
            print("Error Webhook:", e)
            return web.Response(status=500, text=str(e))

    def format_message(self, tasks):
        grouped = {}
        for t in tasks:
            assignee = t["assignees"]
            grouped.setdefault(assignee, []).append(t)

        text = "👋 **¡Buenos días!**\nEstas son tus tareas del día de hoy:\n\n"
        for assignee, tasks in grouped.items():
            text += f"### 👤 {assignee}\n"
            for t in tasks:
                text += f"- **{t['name']}** _(Estado: {t['status']})_\n"
            text += "\n"

        return text

async def setup(bot):
    reminders = Reminders(bot)

    runner = web.AppRunner(reminders.app)
    await runner.setup()
    
    # ✅ Puedes cambiar el puerto si lo necesitas
    site = web.TCPSite(runner, "0.0.0.0", 4000)
    await site.start()

    await bot.add_cog(reminders)
