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
        db, to = self.k.db, req.chat_id
        say = self.k.persona.to(to)
        if req.torrent:
            result = await self.k.automator.torrent_download(req.anilist_id, req.season or None, job_id=req.id)
            admin_txt = describe_torrent(result, req.title)
        else:
            result = await self.k.automator.request_download(req.paste_url, job_id=req.id, movie=req.movie,
                                                             title=req.title)
            admin_txt = describe(result, req.title, for_admin=True)
        st = result.get("status")
        queued = result.get("queued") or []
        movie = req.movie or result.get("kind") == "movie"

        if st == "queued" and queued:
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
            return Outcome(True, admin_txt, approved + "\n" + body + airing + slow)

        if st in ("queued", "in_progress"):  # todo lo que falta ya estaba en cola por otra petición
            db.set_status(req.id, Status.NOTHING_NEW)
            return Outcome(True, admin_txt, say("already_downloading", title=req.title))
        if st == "nothing_new":
            db.set_status(req.id, Status.NOTHING_NEW)
            return Outcome(True, admin_txt, say("movie_already" if movie else "nothing_new", title=req.title))
        if st == "nothing_found":   # por torrent: no hay nada con subtítulos en español (no gasta carro)
            db.set_status(req.id, Status.FAILED)
            return Outcome(False, admin_txt, say("torrent_none", title=req.title))

        db.set_status(req.id, Status.FAILED)
        return Outcome(False, admin_txt, say("tech_failure", title=req.title))
