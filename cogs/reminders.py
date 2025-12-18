import discord
from discord.ext import commands, tasks
from aiohttp import web
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
import re
import random

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

        # ✅ Plantillas de mensajes (variados)
        self.build_templates()

        # ✅ Iniciamos el recordatorio diario
        self.daily_clickup_reminder.start()

    def setup_routes(self):
        self.app.router.add_post("/reminders", self.receive_reminders)

    def build_templates(self):
        # Mensajes AM (9:30) — variados, con tácticas distintas
        self.templates_am = [
            ("⏰ **Check-in rápido (2 min)**\n"
             "Antes de meterte en modo producción: actualicen estados en **ClickUp**.\n"
             "Si está actualizado, el día rinde el doble 🌱"),

            ("🌱 **Orden = velocidad**\n"
             "Chicos: **ClickUp al día** antes de arrancar fuerte.\n"
             "Cuando no está actualizado, terminamos coordinando por chat (y eso mata foco) 😅"),

            ("🔥 **Anti-cuello de botella**\n"
             "Actualicen **hoy** los estados en ClickUp.\n"
             "Si hay bloqueo, pónganlo en la tarea (no en la mente) 🙌"),

            ("📌 **Micro-hábito**\n"
             "Abrí ClickUp → 3 tareas → actualizá estado.\n"
             "Listo. 90 segundos. Después sí: a romperla ☀️"),

            ("🧠 **Claridad para priorizar**\n"
             "Si ClickUp está desactualizado, la prioridad del equipo también.\n"
             "Actualicen estados ahora y evitamos retrabajo 🌻"),
        ]

        # Mensajes 6pm — “voz Isa”, cercanos
        self.templates_6pm = [
            ("🌙 **Antes de cerrar el día…**\n"
             "chee, actualicen las tareas en **ClickUp** así mañana arrancamos sin caos 😌🌱"),

            ("✨ **Último empujón**\n"
             "chee, no me dejen ClickUp en misterio 😅\n"
             "Actualicen estados y si algo quedó trabado, déjenlo marcado 🙏"),

            ("🧡 **Cierre prolijo**\n"
             "Antes de terminar: actualicen ClickUp.\n"
             "Gracias, los quiero, pero los quiero más cuando está todo ordenado 😂🌱"),
        ]

        self._last_am_idx = None
        self._last_6pm_idx = None

    def pick_template(self, templates, last_idx, now):
        """
        Elige un template evitando repetir el último.
        Random controlado por fecha para que tenga "variedad estable" por día.
        """
        if not templates:
            return None, last_idx

        seed = int(now.strftime("%Y%m%d"))  # cambia día a día
        rng = random.Random(seed)

        indices = list(range(len(templates)))
        if last_idx is not None and len(indices) > 1 and last_idx in indices:
            indices.remove(last_idx)

        idx = rng.choice(indices)
        return templates[idx], idx

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

    # ✅ ✅ ✅ Recordatorios diarios ClickUp — 9:30 y 18:00 ARG
    @tasks.loop(minutes=1)
    async def daily_clickup_reminder(self):
        now = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            return

        # 9:30 AM
        if now.hour == 10 and now.minute == 0:
            msg, idx = self.pick_template(self.templates_am, self._last_am_idx, now)
            self._last_am_idx = idx
            if msg:
                await channel.send(msg)

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
