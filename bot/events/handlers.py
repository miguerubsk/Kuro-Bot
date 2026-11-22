"""
Eventos de progreso que envía Anime-Automator (patrón estrategia + registro).

Cada tipo de evento («episode_done», «job_complete»…) tiene su clase. Para
atender uno nuevo basta con escribir otra subclase con @on_event: el router
no se toca (abierto-cerrado).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.models import Status
from ..core.text import compress_ranges, e

log = logging.getLogger(__name__)

_HANDLERS: dict[str, type["EventHandler"]] = {}


def on_event(kind: str):
    def deco(cls):
        _HANDLERS[kind] = cls
        cls.kind = kind
        return cls
    return deco


@dataclass
class Event:
    raw: dict
    req: object
    name: str
    ep: int
    movie: bool
    error: str

    @property
    def to(self) -> int:
        return self.req.chat_id

    def get(self, key, default=None):
        return self.raw.get(key, default)


class EventHandler(ABC):
    kind = ""

    def __init__(self, kuro):
        self.k = kuro

    async def _tell(self, to: int, key: str, suffix: str = "", **kw):
        await self.k.messenger.send(to, self.k.persona.say(key, to, **kw) + suffix)

    def _to_admin(self, ev: Event) -> bool:
        """Si lo pidió el admin, ya le llega como cliente: no se le avisa dos veces."""
        return not self.k.is_admin(ev.to)

    def _progress(self, ev: Event):
        self.k.db.set_progress(ev.req.id, total=ev.get("total"), done=ev.get("done"), failed=ev.get("failed"))

    @abstractmethod
    async def handle(self, ev: Event): ...


@on_event("episode_done")
class EpisodeDone(EventHandler):
    async def handle(self, ev):
        self._progress(ev)
        if not ev.movie:  # en películas avisa job_complete, para no repetir
            await self._tell(ev.to, "ep_done", name=ev.name, ep=ev.ep, n=ev.get("done"), total=ev.get("total"))


@on_event("episode_retry")
class EpisodeRetry(EventHandler):
    async def handle(self, ev):
        if int(ev.get("attempt") or 1) == 1:  # solo el primero, sin agobiar
            await self._tell(ev.to, "movie_retry" if ev.movie else "ep_retry", name=ev.name, ep=ev.ep,
                             delay=ev.get("delay", "un rato"))


@on_event("episode_fallback")
class EpisodeFallback(EventHandler):
    async def handle(self, ev):
        await self._tell(ev.to, "ep_fallback", name=ev.name, ep=ev.ep)


@on_event("episode_failed")
class EpisodeFailed(EventHandler):
    async def handle(self, ev):
        self._progress(ev)
        to_admin = self._to_admin(ev)
        detail = f"\n<code>{e(ev.error)}</code>"
        if not ev.movie:
            await self._tell(ev.to, "ep_failed", "" if to_admin else detail, name=ev.name, ep=ev.ep)
        if to_admin:
            await self._tell(self.k.admin, "admin_movie_failed" if ev.movie else "admin_ep_failed",
                             name=ev.name, ep=ev.ep, req_id=ev.req.id, who=ev.req.user_name, error=ev.error)
        elif ev.movie:  # el admin pidió la peli: el detalle del error va en su mensaje
            await self._tell(ev.to, "movie_failed", detail, name=ev.name)


@on_event("job_complete")
class JobComplete(EventHandler):
    async def handle(self, ev):
        done, failed = ev.get("done") or [], ev.get("failed") or []
        req, to, to_admin = ev.req, ev.to, self._to_admin(ev)
        self.k.db.set_progress(req.id, total=len(done) + len(failed), done=len(done), failed=len(failed))
        say = self.k.persona.to(to)
        if done:
            self.k.db.set_status(req.id, Status.COMPLETED)
            if ev.movie:
                msg = say("movie_done", name=ev.name)
            elif failed:
                msg = say("job_done_partial", name=ev.name, done=len(done), failed=len(failed),
                          failed_ranges=compress_ranges(failed))
            else:
                msg = say("job_done_all", name=ev.name, done=len(done))
        else:
            self.k.db.set_status(req.id, Status.FAILED)  # no se ha descargado nada: devuelve el cupo
            msg = None if (ev.movie and not to_admin) else say("movie_failed" if ev.movie else "job_failed",
                                                               name=ev.name)
        if msg:
            await self.k.messenger.send(to, msg)
        if to_admin:
            failed_html = f" ({compress_ranges(failed)})" if failed and not ev.movie else ""
            await self._tell(self.k.admin, "admin_job_done", req_id=req.id, who=req.user_name, name=ev.name,
                             done=len(done), failed=len(failed), failed_html=failed_html)


class WatchEvents:
    """
    Capítulos que llegan por un seguimiento semanal (webhook de change-detection
    en Anime-Automator, job_id «watch:…»). Kuro avisa a los clientes que siguen
    esa URL. Al miauestro no: esos avisos ya le llegan por el Telegram de
    Anime-Automator, como siempre.
    """

    async def handle(self, k, raw: dict):
        if raw.get("event") != "episode_done" or raw.get("kind") == "movie":
            return
        url = raw.get("watch_url") or ""
        name, ep = raw.get("name") or "", int(raw.get("episode") or 0)
        told = set()
        for t in k.db.track_active_for_url(url):
            if k.is_admin(t.chat_id) or t.chat_id in told:
                continue
            told.add(t.chat_id)
            await k.messenger.send(t.chat_id, k.persona.say("track_ep_done", t.chat_id,
                                                            name=name or t.title, ep=ep))
        if told:
            log.info("Capítulo %s de %s (seguimiento): avisados %s cliente(s)", ep, name, len(told))


class EventRouter:
    def __init__(self, kuro):
        self.k = kuro
        self.handlers = {kind: cls(kuro) for kind, cls in _HANDLERS.items()}
        self.watch = WatchEvents()

    def _parse(self, raw: dict) -> Event | None:
        try:
            req = self.k.db.get(int(raw.get("job_id")))
        except (TypeError, ValueError):
            req = None
        if not req:
            return None
        return Event(raw=raw, req=req, name=raw.get("name") or req.title, ep=int(raw.get("episode") or 0),
                     movie=raw.get("kind") == "movie" or req.movie, error=str(raw.get("error", ""))[:500])

    async def route(self, raw: dict):
        if str(raw.get("job_id") or "").startswith("watch:"):
            return await self.watch.handle(self.k, raw)
        ev = self._parse(raw)
        if ev is None:
            log.warning("Evento de una petición desconocida: %s", raw)
            return
        kind = raw.get("event")
        log.info("Evento %s de la petición #%s (cap. %s)", kind, ev.req.id, ev.ep or "-")
        handler = self.handlers.get(kind)
        if handler is None:
            log.warning("Tipo de evento desconocido: %s", raw)
            return
        await handler.handle(ev)
