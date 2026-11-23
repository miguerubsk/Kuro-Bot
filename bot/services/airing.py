"""
Estado de emisión de un anime según AniList: si sigue en emisión y cuándo
sale el próximo capítulo (con eso se decide qué días se vigila la web).
"""

import logging
import re
from dataclasses import dataclass

import httpx

from .aliases import ANILIST_URL, related
from .japanpaw.ranking import norm

log = logging.getLogger(__name__)

_FIELDS = "id status episodes title { romaji english } synonyms nextAiringEpisode { airingAt episode }"
SEARCH = f"""
query ($s: String) {{
  Page(perPage: 8) {{ media(search: $s, type: ANIME, sort: SEARCH_MATCH) {{ {_FIELDS} }} }}
}}
"""
BY_ID = f"query ($id: Int) {{ Media(id: $id, type: ANIME) {{ {_FIELDS} }} }}"
OPTIONS = """
query ($s: String) {
  Page(perPage: 8) { media(search: $s, type: ANIME, sort: SEARCH_MATCH, isAdult: false) {
    id status episodes format title { romaji english } startDate { year } } }
}
"""
OPTION_BY_ID = """
query ($id: Int) { Media(id: $id, type: ANIME) { id status episodes format title { romaji english } startDate { year } } }
"""
# lo que se puede pedir por torrent (por número de capítulo: nada de películas)
SERIES_FORMATS = ("TV", "TV_SHORT", "ONA", "OVA", "SPECIAL")
FORMAT_TEXT = {"TV": "TV", "TV_SHORT": "TV corta", "ONA": "ONA", "OVA": "OVA", "SPECIAL": "especial"}


@dataclass
class Option:
    """Un anime de AniList para elegir cuando la web no lo tiene."""
    anilist_id: int
    title: str
    english: str
    format: str
    episodes: int | None
    year: int | None
    status: str

    @property
    def releasing(self) -> bool:
        return self.status == "RELEASING"

    def label(self) -> str:
        """«Kono Oto Tomare! 2 · 2019 · TV · 13 caps.» (o «en emisión»)."""
        parts = [self.title]
        if self.year:
            parts.append(str(self.year))
        parts.append(FORMAT_TEXT.get(self.format, self.format.lower()))
        if self.releasing:
            parts.append("en emisión")
        elif self.episodes:
            parts.append(f"{self.episodes} caps.")
        return " · ".join(parts)

    @classmethod
    def from_media(cls, m: dict) -> "Option":
        t = m.get("title") or {}
        return cls(int(m["id"]), t.get("romaji") or t.get("english") or "?", t.get("english") or "",
                   m.get("format") or "", m.get("episodes"), (m.get("startDate") or {}).get("year"),
                   m.get("status") or "")


@dataclass
class Airing:
    anilist_id: int
    status: str                  # RELEASING, FINISHED, NOT_YET_RELEASED, HIATUS…
    next_at: float | None        # timestamp del próximo capítulo
    next_ep: int | None
    episodes: int | None

    @property
    def releasing(self) -> bool:
        return self.status in ("RELEASING", "NOT_YET_RELEASED", "HIATUS")

    @classmethod
    def from_media(cls, m: dict) -> "Airing":
        nxt = m.get("nextAiringEpisode") or {}
        return cls(int(m["id"]), m.get("status") or "", nxt.get("airingAt"), nxt.get("episode"), m.get("episodes"))


def title_key(text: str) -> str:
    """Para comparar títulos: sin tildes, signos ni espacios, y «ō» = «ou» = «oo» = «o»."""
    t, prev = norm(text).replace(" ", ""), None
    while prev != t:
        prev = t
        t = re.sub(r"o[ou]", "o", t)
        t = re.sub(r"u+", "u", t)
    return t


def _names(m: dict) -> list[str]:
    t = m.get("title") or {}
    return [x for x in (t.get("romaji"), t.get("english"), *(m.get("synonyms") or [])) if x]


class AiringClient:
    async def _query(self, query: str, variables: dict, timeout: float = 10) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(ANILIST_URL, json={"query": query, "variables": variables})
                r.raise_for_status()
                return r.json().get("data") or {}
        except Exception as ex:
            log.warning("AniList no ha respondido (%s): %s", variables, ex)
            return None

    async def lookup(self, title: str) -> Airing | None:
        """El anime de ese título; entre los parecidos, mejor uno que siga en emisión."""
        data = await self._query(SEARCH, {"s": title})
        media = ((data or {}).get("Page") or {}).get("media") or []
        media = [m for m in media if any(related(title, n) for n in _names(m))]
        if not media:
            return None
        best = next((m for m in media if m.get("nextAiringEpisode")), None) or media[0]
        return Airing.from_media(best)

    async def exact(self, title: str) -> Airing | None:
        """
        El anime que se llama exactamente así (título o sinónimo), o None. Para
        decidir si algo está en emisión no vale lookup(): aceptaría otra
        temporada o un spin-off que sí se emita.
        """
        want = title_key(title)
        if len(want) < 3:
            return None
        data = await self._query(SEARCH, {"s": title}, timeout=6)
        for m in ((data or {}).get("Page") or {}).get("media") or []:
            if want in {title_key(n) for n in _names(m)}:
                return Airing.from_media(m)
        return None

    async def options(self, query: str, limit: int = 6) -> list[Option] | None:
        """Animes (no películas) que encajan con la búsqueda; None si AniList no responde."""
        data = await self._query(OPTIONS, {"s": query}, timeout=8)
        if data is None:
            return None
        media = ((data.get("Page") or {}).get("media")) or []
        return [Option.from_media(m) for m in media
                if m.get("format") in SERIES_FORMATS and m.get("status") != "NOT_YET_RELEASED"][:limit]

    async def option(self, anilist_id: int) -> Option | None:
        data = await self._query(OPTION_BY_ID, {"id": anilist_id}, timeout=8)
        m = (data or {}).get("Media")
        return Option.from_media(m) if m else None

    async def by_id(self, anilist_id: int) -> Airing | None:
        data = await self._query(BY_ID, {"id": anilist_id})
        m = (data or {}).get("Media")
        return Airing.from_media(m) if m else None
