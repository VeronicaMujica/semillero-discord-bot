import os
import random
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

FRASES_DEALER = [
    "🃏 Buen día, equipo. Hoy las cartas están a favor del que se sienta a jugarlas.",
    "🎲 La suerte es para el que aparece. Empezamos.",
    "🔥 Otra jornada, otra mano. El Dealer reparte, ustedes juegan.",
    "☕ Buen día. Recuerden: una tarea cerrada hoy vale más que diez pendientes mañana.",
    "💼 El que sostiene el ritmo, gana el juego. Arrancamos.",
    "⚡ Mover una sola cosa hoy ya es avanzar. No hace falta más.",
    "🎯 No hace falta terminar todo. Hace falta empezar.",
    "🌱 Sembrando desde temprano. El día rinde cuando se agarra al vuelo.",
    "🃏 El Dealer saluda. Hoy vamos por lo importante, no por lo urgente.",
    "🚀 Menos scroll, más foco. Vamos con una primera tarea bien hecha.",
    "💡 La disciplina cansa menos que la culpa. Buen día, equipo.",
    "🎶 Pongan música, abran ClickUp, y hagamos magia.",
    "🧠 Cerebro fresco, decisiones claras. Aprovechen la mañana.",
    "🌞 Buen día. Hoy el Dealer reparte foco y café.",
    "🪙 Una decisión pequeña tomada hoy, gana al plan perfecto de mañana.",
    "🎴 El Dealer abre la mesa. Hoy se juega con lo que hay, no con lo que falta.",
    "🛠️ Buen día. La diferencia entre 'genial' y 'hecho' es que 'hecho' está terminado.",
    "📿 Empezar mal es mejor que no empezar. Dale.",
    "🪴 La planta no crece más rápido por mirarla. Movete a otra cosa mientras.",
    "🎵 ¿Sabés qué es elegante? Cumplir lo que dijiste que ibas a hacer.",
    "🪞 Buen día. Tu yo del viernes te lo va a agradecer.",
    "🃏 La casa siempre paga, pero solo a quien apuesta. Arranquen.",
    "🌅 Hoy no se trata de ser productivo. Se trata de no postergar lo importante.",
    "🪁 Buen día. El plan perfecto es el que entra en marcha hoy.",
    "🍃 Respiren, organicen, y avancen. En ese orden.",
    "🎁 Buen día. Una tarea que llevás 3 días posponiendo te roba más energía que hacerla.",
    "🪨 Lo difícil primero. El resto del día se vuelve fácil.",
    "🃏 El Dealer dice: planificar es decidir qué NO vas a hacer hoy.",
    "🌻 Buenos días. La mejor versión de hoy es la que aparece a horario.",
    "🛤️ Una semana se gana con lunes a miércoles. Arranquemos firme.",
]

# GIFs que el Dealer manda los lunes después del mensaje motivador.
# Editá esta lista con los GIFs que te gusten — pegá la URL pública
# (de Tenor https://tenor.com/view/... o Giphy https://giphy.com/gifs/...).
# Discord los autoembebe.
GIFS_LUNES = [
    "https://tenor.com/view/lets-do-this-monday-monday-motivation-motivation-gif-15745113",
    "https://tenor.com/view/monday-morning-coffee-monday-mood-cat-gif-15068193",
    "https://tenor.com/view/lunes-monday-mood-gif-22327921",
    "https://tenor.com/view/feliz-lunes-feliz-inicio-de-semana-buen-dia-gif-25027706",
    "https://tenor.com/view/monday-mood-monday-vibes-monday-energy-gif-25949881",
]


FRASES_RANDOM_DEALER = [
    "🃏 Pausá un toque. Volvé a la mesa con cabeza fresca.",
    "🎲 Si una tarea lleva más de 1 hora trabada, dejala marinar y pasá a otra.",
    "☕ ¿Hace cuánto que no tomás agua? La casa observa.",
    "💼 Una tarea sin fecha es una tarea sin compromiso. Pongan fecha.",
    "🔥 La consistencia gana al heroismo. Una hora hoy > maratón el viernes.",
    "🎯 ¿Tu próxima tarea está clara? Si no, te recomiendo abrir ClickUp.",
    "✨ Si terminaste algo hoy, marcalo. Sentir el cierre es parte del trabajo.",
    "🃏 El Dealer pasa a saludar. ¿Cómo va la mano?",
    "🌿 Levantate, estirate, respirá. Es gratis y rinde.",
    "📋 Una idea suelta hoy es una tarea bien capturada mañana. `/tarea` está ahí.",
    "⚡ Enfocarse en 1 cosa por 25 min rinde más que 3 cosas en 2 horas.",
    "🎶 Cambialé la música. El cerebro lo nota.",
    "🃏 Tu yo de la noche te va a agradecer cerrar 1 tarea ahora.",
    "💪 Si llegaste hasta acá del día, ya ganaste. Cerrá una más y rematás bien.",
    "🪟 Asomate por la ventana 1 minuto. Vuelvas, retomá.",
    "🍵 Recordatorio del Dealer: una pausa de 5 minutos no es perder tiempo, es invertirlo.",
    "📵 Cerrá una pestaña. Cualquiera. Vas a respirar mejor.",
    "🃏 Si la tarea que estás haciendo no la elegirías ahora con cabeza fresca, está bien parar.",
    "🍊 Comé algo. Hidrate. Volvé en 10.",
    "🔔 ¿Cuánto hace que no actualizás el estado de una tarea? Probablemente toca.",
    "🪷 Multitarea es ilusión de productividad. Una a la vez.",
    "🎭 Si te dispersaste, no te culpes. Anotá dónde estabas y volvé.",
    "🌬️ Respiración 4-7-8: 4 segundos inhalando, 7 reteniendo, 8 exhalando. Probalo.",
    "🃏 Pregunta del Dealer: ¿qué tarea de las abiertas te da más alivio cerrar hoy?",
    "🧩 Si la tarea es muy grande, partila en dos. La grande no se termina; las chicas sí.",
    "📊 ¿Mirás la lista de pendientes y no sabés por dónde? Elegí la más vieja. Suele ser la culpa silenciosa.",
    "🍀 Recordatorio: el avance no se nota día a día. Se nota viernes a viernes.",
    "🃏 El Dealer pregunta: ¿qué tarea importante estás esquivando? Esa misma.",
    "🌊 Si te trabaste, cambiá de lugar. Caminá. La cabeza se desbloquea sola.",
    "📞 ¿Hay algo que se resuelve con un mensaje de 30 segundos en vez de quedar en tu cabeza? Mándalo.",
    "🪙 El éxito de hoy es haber sostenido el foco aunque sea 2 bloques de 25 min.",
    "🎨 La perfección es enemiga del envío. Mandá la versión 80%.",
]


def _is_weekday(dt: datetime) -> bool:
    # 0 = lunes, 6 = domingo
    return dt.weekday() < 5


class MotivationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=ARG_TZ)
        self.channel_id = int(
            os.getenv("DEALER_CHANNEL_ID")
            or os.getenv("DISCORD_CHANNEL_REMINDERS")
            or 0
        )

    async def cog_load(self):
        # Motivación matutina: lunes y miércoles 9:00 (sin findes)
        self.scheduler.add_job(
            self.enviar_motivacion,
            "cron",
            day_of_week="mon,wed",
            hour=9,
            minute=0,
            id="motivation_job",
            replace_existing=True,
        )
        # Frase suelta en hora random: martes y jueves 10:00 elige hora del día
        self.scheduler.add_job(
            self._programar_frase_random_del_dia,
            "cron",
            day_of_week="tue,thu",
            hour=10,
            minute=0,
            id="motivation_random_selector",
            replace_existing=True,
        )
        self.scheduler.start()
        # Si el bot arranca un día válido después de las 10:00, intentar programar para hoy
        try:
            now = datetime.now(ARG_TZ)
            if now.weekday() in (1, 3):  # martes=1, jueves=3
                await self._programar_frase_random_del_dia()
        except Exception as e:
            log.warning(f"No pude programar frase random de hoy: {e}")
        log.info("MotivationCog scheduler iniciado.")

    def cog_unload(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def enviar_motivacion(self):
        if not self.channel_id:
            log.warning("No hay DEALER_CHANNEL_ID configurado.")
            return
        now = datetime.now(ARG_TZ)
        if not _is_weekday(now):
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            log.warning(f"Canal {self.channel_id} no encontrado.")
            return
        frase = random.choice(FRASES_DEALER)
        try:
            await channel.send(frase)
            # Bonus de lunes: GIF random para arrancar la semana
            if now.weekday() == 0 and GIFS_LUNES:
                await channel.send(random.choice(GIFS_LUNES))
        except discord.DiscordException as e:
            log.error(f"Error enviando motivación: {e}")

    async def _programar_frase_random_del_dia(self):
        now = datetime.now(ARG_TZ)
        if not _is_weekday(now):
            return
        target_hour = random.randint(11, 16)
        target_minute = random.randint(0, 59)
        run_at = now.replace(
            hour=target_hour, minute=target_minute, second=0, microsecond=0
        )
        if run_at <= now:
            log.info(
                f"Hora random {run_at.strftime('%H:%M')} ya pasó hoy — salteo."
            )
            return
        self.scheduler.add_job(
            self.enviar_frase_random,
            "date",
            run_date=run_at,
            id=f"random_phrase_{now.date()}",
            replace_existing=True,
        )
        log.info(f"Frase random programada para hoy {run_at.strftime('%H:%M')}")

    async def enviar_frase_random(self):
        if not self.channel_id:
            return
        if not _is_weekday(datetime.now(ARG_TZ)):
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        frase = random.choice(FRASES_RANDOM_DEALER)
        try:
            await channel.send(frase)
        except discord.DiscordException as e:
            log.error(f"Error enviando frase random: {e}")

    @app_commands.command(
        name="motivacion",
        description="Pedile al Dealer una frase motivadora ahora mismo",
    )
    async def motivacion(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(FRASES_DEALER))

    @app_commands.command(
        name="gif-lunes",
        description="Probar un GIF random del repertorio de lunes",
    )
    async def gif_lunes(self, interaction: discord.Interaction):
        if not GIFS_LUNES:
            await interaction.response.send_message(
                "🃏 La baraja de GIFs de lunes está vacía. Editá `GIFS_LUNES` en `cogs/motivation.py`.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(random.choice(GIFS_LUNES))


async def setup(bot: commands.Bot):
    await bot.add_cog(MotivationCog(bot))
