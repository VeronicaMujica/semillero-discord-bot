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
    "🃏 Buen día, equipo. Algunas semanas se ganan con arranque; otras, con paciencia. Elegí qué necesita hoy.",
    "☕ Buen día. Que hoy no gane la lista: que gane la cabeza clara.",
    "🌱 Hay días para plantar y días para cosechar. Cualquiera de los dos ya es avanzar.",
    "🎴 Buen día. La casa observa, pero no juzga. Solo reparte.",
    "🌅 Todo lo que hoy hagas con presencia cuenta doble. Empezamos suave.",
    "☁️ Que la mañana te encuentre despacio, y el día en marcha.",
    "🎵 Cada semana es una canción distinta. Hoy elegí vos el ritmo.",
    "🧭 A veces el mejor plan es empezar con lo más simple. Después el día se acomoda.",
    "🃏 El Dealer no reparte suerte. Reparte oportunidades.",
    "🌿 Buen día. Si hoy solo podés con poco, que ese poco valga.",
    "☕ Uno se equivoca menos con la primera taza de café que con la tercera reunión.",
    "🕰️ El tiempo se estira cuando se lo respeta. Buen día.",
    "🎯 No mires el mapa entero. Mirá el siguiente paso — y hacelo.",
    "🃏 A veces avanzar es no retroceder. También cuenta como triunfo.",
    "🌻 Buen día. Que hoy la energía te alcance donde importa.",
    "🎼 Un movimiento bien pensado vale más que veinte apurados.",
    "☁️ Dejá que el día se acomode antes de exigirle demasiado.",
    "🌱 Lo que hoy parece un desorden, mañana empieza a mostrar su patrón.",
    "🃏 Hay manos que se juegan con estrategia. Otras, con corazón. Vos elegís.",
    "☕ Buen día. La calidad de la mañana define el tono del día.",
    "🎨 Nada tiene que salir perfecto. Solo salir.",
    "🌤️ La productividad también es saber cuándo parar. Empecemos sin apuro.",
    "🃏 El Dealer dice: la constancia es un secreto ruidoso.",
    "🌿 Que hoy sea un día honesto: ni más ni menos que lo que puedas.",
    "🎪 A veces el día importante es el que no lo parece.",
    "☕ Buen día. Que las decisiones de hoy tengan aire, no urgencia.",
    "🎴 Cada tarea es una excusa para practicar el foco.",
    "🌅 Hay algo lindo en empezar sin saber cómo va a terminar.",
    "🃏 Buen día. Elegí una cosa. Solo una. Y hacela con presencia.",
    "🕊️ Que hoy no te falte paciencia — ni con vos, ni con lo que hacés.",
    "🎼 Buen día. El ritmo lo marca quien decide no correr.",
    "🍃 Hay días que piden empuje y otros que piden pausa. Ambos suman.",
    "🃏 Empezar temprano no es urgencia. Es privilegio.",
    "🌾 Sembrar no siempre se ve. Igual sirve. Buen día.",
]

FRASES_RANDOM_DEALER = [
    "🎴 Un pequeño impulso ahora se agradece mucho más tarde.",
    "🃏 A veces la mejor decisión es hacer una pausa.",
    "🌿 Estirate. El cuerpo te viene aguantando desde la mañana.",
    "☕ Un vaso de agua, tres respiraciones profundas, y seguimos.",
    "🕊️ Hay tareas que rinden más si primero les das aire.",
    "🎵 Cambiá de canción. La cabeza lo agradece.",
    "🃏 Caminá 3 minutos. Vuelvas más liviano.",
    "☁️ Si estás en modo automático, apagalo un ratito.",
    "🌱 Un paso pequeño en la dirección correcta ya es un buen día.",
    "🎨 Terminar algo, aunque sea chico, alivia como pocas cosas.",
    "☕ Un ratito lejos de la pantalla suele destrabar más que insistir.",
    "🃏 A veces la solución aparece cuando dejamos de buscarla.",
    "🌤️ Asomate a la ventana un minuto. El aire fresco cambia el ánimo.",
    "🎴 Elegí una tarea abierta, la más chica. Cerrala. Sentí el clic.",
    "🃏 Un respiro corto ahora rinde más que uno largo cuando ya no das más.",
    "🌿 Tu cabeza rinde más si le das oxígeno.",
    "☁️ Cuando algo se traba, a veces conviene dejarlo descansar y probar con otra cosa.",
    "🎶 Los días buenos también piden respiros.",
    "🃏 Cada bloque de foco que sostenés hoy es un pequeño triunfo. Sumá otro.",
    "☕ Dejá la pestaña 12 abierta y andate a caminar 5 minutos.",
    "🌱 A veces el mejor consejo es: comé algo.",
    "🃏 Descansar es parte del trabajo, no lo contrario.",
    "🕰️ Si sentís apuro, respirá tres veces. Y volvé.",
    "🎴 Elegí la tarea que más alivio te va a dar cerrar. Empezá por ahí.",
    "🃏 A veces hay que salir de la mesa para volver a ver el juego.",
    "🌤️ Si tenés dudas, elegí lo más simple.",
    "☕ El cuerpo también te está trabajando. Cuidalo un poco.",
    "🎵 Si el aire está pesado, cambialo: música, ventana, o silencio.",
    "🃏 Todo lo que hoy se sostiene con calma dura más.",
    "🌾 Todo lo que hiciste hoy va sumando, aunque no lo veas todavía.",
    "🎨 Los días que rinden distinto también rinden.",
    "🃏 A veces avanzar es ordenar un poco antes de seguir.",
    "🍃 No todo lo importante se ve en tu lista de tareas.",
    "🌤️ Recordá: el ritmo que sostenés es más importante que el ritmo que empezás.",
    "🃏 Cada cosa que cerrás hoy libera espacio para lo que viene mañana.",
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
        if not _is_weekday(datetime.now(ARG_TZ)):
            return
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            log.warning(f"Canal {self.channel_id} no encontrado.")
            return
        frase = random.choice(FRASES_DEALER)
        try:
            await channel.send(frase)
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


async def setup(bot: commands.Bot):
    await bot.add_cog(MotivationCog(bot))
