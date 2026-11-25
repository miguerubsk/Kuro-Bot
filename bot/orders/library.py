"""¿Ya está en la biblioteca? (antes de gastar cupo o molestar al admin)"""

import logging
from dataclasses import dataclass, field

from ..core.text import compress_ranges, e

log = logging.getLogger(__name__)


@dataclass
class Assessment:
    COMPLETE = "complete"   # está todo en .mkv
    BUSY = "busy"           # lo que falta ya se está bajando
    REQUEST = "request"     # hay que pedirlo

    state: str = REQUEST
    exempt: bool = False    # ya tenemos parte, o todo en peor calidad: no gasta cupo
    user_note: str = ""
    admin_note: str = ""
    lib: dict = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.state == self.REQUEST


class LibraryChecker:
    def __init__(self, kuro):
        self.k = kuro

    async def assess(self, post, chat_id: int) -> Assessment:
        """
        Si la consulta falla se trata como "request" (Anime-Automator lo vuelve
        a comprobar al descargar y no cobra si no hay nada nuevo).
        """
        lib = await self.k.automator.check_library(post.paste_url, movie=post.movie, title=post.title)
        out = Assessment(lib=lib)
        st = lib.get("status")
        if st == "nothing_new":
            out.state = Assessment.COMPLETE
            return out
        if st == "in_progress":
            out.state = Assessment.BUSY
            return out
        if st != "missing":
            log.warning("Consulta de biblioteca sin resultado para %s: %s", post.paste_url, lib)
            return out

        missing = lib.get("missing") or []
        upgrade = lib.get("upgrade") or []
        # completar lo que ya está a medias, o mejorar la calidad, no gasta cupo
        out.exempt = bool(missing) and (bool(lib.get("have")) or set(missing) <= set(upgrade))
        out.user_note = self._user_note(lib, missing, out.exempt, chat_id)
        out.admin_note = _admin_note(lib, missing, upgrade, out.exempt)
        return out

    def _user_note(self, lib: dict, missing: list, exempt: bool, chat_id: int) -> str:
        """Si ya tiene parte, qué falta; si solo mejora la calidad, eso (las dos no gastan cupo)."""
        say = self.k.persona.to(chat_id)
        if lib.get("kind") != "movie" and lib.get("have"):
            return say("library_partial", have=lib["have"], available=lib.get("available", "?"),
                       count=len(missing), ranges=compress_ranges(missing))
        if exempt:
            return say("library_upgrade")
        return ""


def _admin_note(lib: dict, missing: list, upgrade: list, exempt: bool) -> str:
    """Lo que hay en la biblioteca, para que el admin decida (HTML)."""
    where = e(lib.get("folder") or "")
    return (
        f"\n📚 En biblioteca (.mkv): {lib.get('have', 0)} de {lib.get('available', '?')}"
        + (f" (faltan {compress_ranges(missing)})" if lib.get("have") else "")
        + (f"\n📀 Mejora de calidad (hay otro formato): {compress_ranges(upgrade)}" if upgrade else "")
        + (" — <b>no gasta cupo</b>" if exempt else "")
        + (f"\nCarpeta: <code>{where}</code>" if where else "")
        + (" — nueva" if lib.get("new_folder") else "")
    )
