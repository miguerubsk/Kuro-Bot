"""
Estado de emisión de un anime según AniList: si sigue en emisión y cuándo
sale el próximo capítulo (con eso se decide qué días se vigila la web).
"""

import logging
from dataclasses import dataclass

import httpx

from .aliases import ANILIST_URL, related

log = logging.getLogger(__name__)

_FIELDS = "id status episodes title { romaji english } synonyms nextAiringEpisode { airingAt episode }"
SEARCH = f"""
query ($s: String) {{
  Page(perPage: 8) {{ media(search: $s, type: ANIME, sort: SEARCH_MATCH) {{ {_FIELDS} }} }}
}}
"""
BY_ID = f"query ($id: Int) {{ Media(id: $id, type: ANIME) {{ {_FIELDS} }} }}"


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


class AiringClient:
    async def _query(self, query: str, variables: dict) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
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

        def names(m):
            t = m.get("title") or {}
            return [x for x in (t.get("romaji"), t.get("english"), *(m.get("synonyms") or [])) if x]

        media = [m for m in media if any(related(title, n) for n in names(m))]
        if not media:
            return None
        best = next((m for m in media if m.get("nextAiringEpisode")), None) or media[0]
        return Airing.from_media(best)

    async def by_id(self, anilist_id: int) -> Airing | None:
        data = await self._query(BY_ID, {"id": anilist_id})
        m = (data or {}).get("Media")
        return Airing.from_media(m) if m else None
