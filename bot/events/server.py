"""Endpoint HTTP /events donde Anime-Automator avisa del progreso."""

import hmac
import logging

from aiohttp import web

log = logging.getLogger(__name__)


class EventServer:
    def __init__(self, router, secret: str, port: int):
        self.router = router
        self.secret = secret
        self.port = port
        self._runner: web.AppRunner | None = None

    def _authorized(self, request: web.Request) -> bool:
        given = request.headers.get("X-Callback-Secret", "")
        return bool(self.secret) and hmac.compare_digest(given.encode(), self.secret.encode())

    async def _events(self, request: web.Request):
        if not self._authorized(request):
            return web.Response(status=403)
        try:
            ev = await request.json()
        except ValueError:
            return web.Response(status=400)
        try:
            await self.router.route(ev)
        except Exception:
            # se responde 200 igualmente: un reintento solo duplicaría mensajes
            log.exception("Fallo procesando el evento %s", ev)
        return web.json_response({"ok": True})

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/events", self._events)
        return app

    async def start(self):
        if not self.secret:
            log.warning("CALLBACK_SECRET vacío: no se recibirán avisos de progreso de Anime-Automator")
            return
        self._runner = web.AppRunner(self.app())
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self.port).start()
        log.info("Escuchando eventos de Anime-Automator en el puerto %s", self.port)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
