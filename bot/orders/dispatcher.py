"""Envío de una petición a Anime-Automator (común al admin directo y a las aprobaciones)."""

from dataclasses import dataclass

from ..core.models import Status
from ..core.text import compress_ranges
from ..services.automator import describe, describe_torrent


@dataclass
class Outcome:
    ok: bool
    admin_text: str   # detalle técnico
    user_text: str    # para quien lo pidió


class Dispatcher:
    def __init__(self, kuro):
        self.k = kuro

    async def dispatch(self, req) -> Outcome:
        """
        Manda la petición y deja el estado final en la BD. Solo se queda
        consumiendo cupo si de verdad se ha encolado algo.
        """
        result, admin_txt = await self._send(req)
        queued = result.get("queued") or []
        movie = req.movie or result.get("kind") == "movie"
        if result.get("status") == "queued" and queued:
            return Outcome(True, admin_txt, self._queued(req, result, queued, movie))
        status, ok, key = _settled(result.get("status"), movie)
        self.k.db.set_status(req.id, status)
        return Outcome(ok, admin_txt, self.k.persona.say(key, req.chat_id, title=req.title))

    async def _send(self, req) -> tuple[dict, str]:
        """(respuesta de Anime-Automator, detalle técnico para el admin)"""
        if req.torrent:
            result = await self.k.automator.torrent_download(req.anilist_id, req.season or None, job_id=req.id)
            return result, describe_torrent(result, req.title)
        result = await self.k.automator.request_download(req.paste_url, job_id=req.id, movie=req.movie,
                                                         title=req.title)
        return result, describe(result, req.title, for_admin=True)

    def _queued(self, req, result: dict, queued: list, movie: bool) -> str:
        """Algo nuevo en cola: se apunta y se le cuenta a quien lo pidió qué llega."""
        db, to = self.k.db, req.chat_id
        say = self.k.persona.to(to)
        db.set_progress(req.id, total=len(queued))
        tracked = bool(result.get("tracked"))
        approved = say("approved_boss" if self.k.is_admin(to) else "approved", title=req.title)
        if movie:
            body = say("movie_queued")
        else:
            body = say("queued" if tracked else "queued_untracked", count=len(queued),
                       ranges=compress_ranges(queued))
        db.set_status(req.id, Status.APPROVED if tracked else Status.COMPLETED)
        airing = "" if movie else self.k.texts.airing_note(to, req.airing, req.label)
        slow = ("\n\n" + say("torrent_slow")) if req.torrent else ""
        return approved + "\n" + body + airing + slow


def _settled(status: str, movie: bool) -> tuple[str, bool, str]:
    """No se ha encolado nada nuevo: (estado final, ¿ha ido bien?, frase para quien lo pidió)."""
    if status in ("queued", "in_progress"):   # todo lo que falta ya estaba en cola por otra petición
        return Status.NOTHING_NEW, True, "already_downloading"
    if status == "nothing_new":
        return Status.NOTHING_NEW, True, "movie_already" if movie else "nothing_new"
    if status == "nothing_found":   # por torrent: no hay nada con subtítulos en español (no gasta carro)
        return Status.FAILED, False, "torrent_none"
    return Status.FAILED, False, "tech_failure"
