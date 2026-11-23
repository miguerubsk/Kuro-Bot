"""Kuro: bot de Telegram para pedir animes a Anime-Automator (arranque y ciclo de vida)."""

import asyncio
import logging

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.error import TelegramError
from telegram.ext import Application, ApplicationBuilder, ContextTypes, TypeHandler

from . import config
from .core.text import e
from .events.server import EventServer
from .handlers import REGISTRY
from .kuro import Kuro

log = logging.getLogger("requester-bot")

USER_COMMANDS = [
    BotCommand("pedir", "Pedir un anime"),
    BotCommand("carros", "Carros que te quedan esta semana"),
    BotCommand("seguimientos", "Lo que vigilo cada semana"),
    BotCommand("ayuda", "Cómo funciona"),
    BotCommand("id", "Tu código de cliente"),
]
ADMIN_COMMANDS = [
    BotCommand("pedir", "Pedir un anime"),
    BotCommand("descargados", "Lo descargado, por cliente"),
    BotCommand("pendientes", "Encargos por aprobar"),
    BotCommand("seguimientos", "Lo que se vigila cada semana"),
    BotCommand("carros", "Carros que te quedan esta semana"),
    BotCommand("resetcupo", "Devolver los carros"),
    BotCommand("alta", "Dejar pasar a alguien por su código"),
    BotCommand("ayuda", "Cómo funciona"),
]


class KuroBot:
    def __init__(self, kuro: Kuro):
        self.k = kuro
        self.server = EventServer(kuro.events, kuro.cfg.callback_secret, kuro.cfg.events_port)
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------- ciclo de vida
    async def post_init(self, application: Application):
        k = self.k
        k.messenger.attach(application.bot)
        self._tasks = [asyncio.create_task(k.messenger.run_outbox()), asyncio.create_task(k.lonely.loop()),
                       asyncio.create_task(k.tracker.loop())]
        for req in k.db.fail_stuck_processing():
            log.warning("La petición #%s se quedó a medias al apagarse: pasa a fallida", req.id)
            await k.messenger.send(
                k.admin,
                f"⚠️ La petición #{req.id} (<b>{e(req.title)}</b>, de {e(req.user_name)}) se estaba "
                f"enviando a Anime-Automator cuando se apagó el bot. Revísala en /pendientes y "
                f"reinténtala si hace falta.",
            )
        await application.bot.set_my_commands(USER_COMMANDS)
        try:  # el admin ve además sus comandos
            await application.bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(k.admin))
        except TelegramError:
            log.warning("No se pudieron poner los comandos del admin", exc_info=True)
        await self.server.start()

    async def post_shutdown(self, application: Application):
        for task in self._tasks:
            task.cancel()
        await self.server.stop()
        await self.k.site.close()

    # ----------------------------------------------------------- handlers
    async def track_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cualquier cosa que haga el admin con Kuro cuenta como «ha venido a verme»."""
        chat = update.effective_chat
        if chat is not None and self.k.is_admin(chat.id):
            try:
                await self.k.lonely.touch()
            except Exception:
                log.exception("Fallo registrando la visita del admin")

    @staticmethod
    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
        log.error("Error no controlado procesando %s", update, exc_info=context.error)

    def build(self) -> Application:
        app = (ApplicationBuilder().token(self.k.cfg.token).concurrent_updates(True)
               .post_init(self.post_init).post_shutdown(self.post_shutdown).build())
        # antes que el resto (grupo -1): registra las visitas del admin sin cortar nada
        app.add_handler(TypeHandler(Update, self.track_admin), group=-1)
        for command_cls in REGISTRY:
            command = command_cls(self.k)
            app.add_handler(command.handler(), group=command.group)
        app.add_error_handler(self.on_error)
        return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    # httpx registra cada URL a nivel INFO, y la de Telegram contiene el token
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = config.load()
    watchers = []
    if "changedetection" in cfg.tracking_sources:
        watchers.append(f"change-detection en {cfg.cd_url} cada {cfg.tracking_check_minutes} min"
                        if cfg.cd_url and cfg.cd_api_key else
                        "change-detection NO (faltan CHANGEDETECTION_URL / CHANGEDETECTION_API_KEY)")
    if "drive" in cfg.tracking_sources:
        watchers.append("el Drive (Anime-Automator)")
    log.info("Seguimiento semanal: %s; ventana de %s h", " + ".join(watchers) or "desactivado",
             min(cfg.tracking_window_hours, 24))
    log.info("Arrancando Kuro (admin=%s, lista blanca=%s, palabra clave=%s, límite=%s/semana)",
             cfg.admin_chat_id, len(cfg.allowed_chat_ids), "sí" if cfg.access_keyword else "no", cfg.weekly_limit)
    KuroBot(Kuro(cfg)).build().run_polling(allowed_updates=Update.ALL_TYPES)
