"""
Animes de AniList para pedir por torrent lo que la web no tiene: opciones de
una búsqueda (con portada, sinopsis y géneros, para las fichas) y la cadena
de temporadas de un anime (para «todas las temporadas»).

La sinopsis de AniList está en inglés. Con TMDB_API_KEY se busca antes en
TMDB la de la serie en español; si no hay, va la de AniList.
"""

import html
import logging
import re
from dataclasses import dataclass, field

import httpx

from .aliases import ANILIST_URL
from .japanpaw import Details

log = logging.getLogger(__name__)

_FIELDS = """
id status episodes format season seasonYear genres description(asHtml: false)
title { romaji english native } startDate { year } coverImage { large }
relations { edges { relationType node { id format type } } }
"""
SEARCH = ("query ($s: String) { Page(perPage: 8) { media(search: $s, type: ANIME, sort: SEARCH_MATCH, "
          "isAdult: false) {" + _FIELDS + "} } }")
BY_ID = "query ($id: Int) { Media(id: $id, type: ANIME) {" + _FIELDS + "} }"

# lo que se puede pedir por torrent (por número de capítulo: nada de películas)
SERIES_FORMATS = ("TV", "TV_SHORT", "ONA", "OVA", "SPECIAL")
# lo que cuenta como temporada en la cadena de «todas»
MAIN_FORMATS = ("TV", "TV_SHORT", "ONA")
MAX_SEASONS = 12
MAX_HOPS = 25        # pasos por la cadena, contando especiales y películas
FORMAT_TEXT = {"TV": "TV", "TV_SHORT": "TV corta", "ONA": "ONA", "OVA": "OVA", "SPECIAL": "especial"}
SEASON_TEXT = {"WINTER": "Invierno", "SPRING": "Primavera", "SUMMER": "Verano", "FALL": "Otoño"}
GENRE_TEXT = {
    "Action": "Acción", "Adventure": "Aventura", "Comedy": "Comedia", "Drama": "Drama", "Ecchi": "Ecchi",
    "Fantasy": "Fantasía", "Horror": "Terror", "Mahou Shoujo": "Mahou shoujo", "Mecha": "Mecha",
    "Music": "Música", "Mystery": "Misterio", "Psychological": "Psicológico", "Romance": "Romance",
    "Sci-Fi": "Ciencia ficción", "Slice of Life": "Recuentos de la vida", "Sports": "Deportes",
    "Supernatural": "Sobrenatural", "Thriller": "Suspense", "Hentai": "Hentai",
}


def clean_description(text: str) -> str:
    """La sinopsis de AniList sin etiquetas, sin «(Source: …)» y en un solo párrafo largo."""
    t = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"\s*[\[(](?:source|written by|note)[^\])]*[\])]\s*$", "", t.strip(), flags=re.I)
    return re.sub(r"\n{2,}", "\n", t).strip()


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
    cover_url: str = ""
    description: str = ""
    genres: list[str] = field(default_factory=list)
    season: str = ""                # «Otoño 2019»
    native: str = ""
    # (PREQUEL/SEQUEL, id, formato): por ellas se recorre la cadena de temporadas
    neighbours: list[tuple[str, int, str]] = field(default_factory=list)

    @property
    def releasing(self) -> bool:
        return self.status == "RELEASING"

    @property
    def has_seasons(self) -> bool:
        """¿Puede tener otras temporadas? (tiene precuela o secuela; si al final no hay más, se pide sola)"""
        return bool(self.neighbours)

    def step(self, rel: str, seen: set) -> int | None:
        """La precuela/secuela por la que seguir: mejor una de TV/ONA; si no, un especial, OVA o película."""
        cands = sorted((f not in MAIN_FORMATS, i) for r, i, f in self.neighbours if r == rel and i not in seen)
        return cands[0][1] if cands else None

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

    def details(self, spanish: str = "") -> Details:
        """La ficha (portada, sinopsis, datos) como las de la web."""
        eps = "En emisión" if self.releasing else (str(self.episodes) if self.episodes else "")
        return Details(
            cover_url=self.cover_url, synopsis=spanish or self.description, episodes=eps,
            season=self.season or (str(self.year) if self.year else ""),
            genres=", ".join(GENRE_TEXT.get(g, g) for g in self.genres[:5]),
            video=FORMAT_TEXT.get(self.format, self.format.lower()),
            note="" if spanish or not self.description else "🇬🇧 sinopsis en inglés",
        )

    @classmethod
    def from_media(cls, m: dict) -> "Option":
        t = m.get("title") or {}
        season = SEASON_TEXT.get(m.get("season") or "", "")
        if season and m.get("seasonYear"):
            season += f" {m['seasonYear']}"
        neighbours = [(e["relationType"], int(e["node"]["id"]), e["node"].get("format") or "")
                      for e in ((m.get("relations") or {}).get("edges") or [])
                      if e.get("relationType") in ("PREQUEL", "SEQUEL")
                      and (e.get("node") or {}).get("type") == "ANIME"
                      and (e.get("node") or {}).get("format") != "MUSIC"]
        return cls(int(m["id"]), t.get("romaji") or t.get("english") or "?", t.get("english") or "",
                   m.get("format") or "", m.get("episodes"), (m.get("startDate") or {}).get("year"),
                   m.get("status") or "", (m.get("coverImage") or {}).get("large") or "",
                   clean_description(m.get("description") or ""), list(m.get("genres") or []), season,
                   t.get("native") or "", neighbours)


class AniListCatalog:
    def __init__(self, tmdb_key: str = ""):
        self.spanish = SpanishSynopsis(tmdb_key) if tmdb_key else None
        self._cache: dict[int, Option] = {}

    async def _query(self, query: str, variables: dict, timeout: float = 10) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(ANILIST_URL, json={"query": query, "variables": variables})
                r.raise_for_status()
                return r.json().get("data") or {}
        except Exception as ex:
            log.warning("AniList no ha respondido (%s): %s", variables, ex)
            return None

    def _keep(self, opt: Option) -> Option:
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[opt.anilist_id] = opt
        return opt

    async def options(self, query: str, limit: int = 6) -> list[Option] | None:
        """Animes (no películas) que encajan con la búsqueda; None si AniList no responde."""
        data = await self._query(SEARCH, {"s": query}, timeout=8)
        if data is None:
            return None
        media = ((data.get("Page") or {}).get("media")) or []
        return [self._keep(Option.from_media(m)) for m in media
                if m.get("format") in SERIES_FORMATS and m.get("status") != "NOT_YET_RELEASED"][:limit]

    async def option(self, anilist_id: int) -> Option | None:
        if anilist_id in self._cache:
            return self._cache[anilist_id]
        data = await self._query(BY_ID, {"id": anilist_id}, timeout=8)
        m = (data or {}).get("Media")
        return self._keep(Option.from_media(m)) if m else None

    async def details(self, options: list[Option]) -> dict[int, Details]:
        """Las fichas de las opciones, con la sinopsis en español si se encuentra."""
        out = {}
        for o in options:
            spanish = await self.spanish.find(o) if self.spanish else ""
            out[o.anilist_id] = o.details(spanish)
        return out

    async def seasons(self, anilist_id: int) -> list[Option]:
        """
        Todas las temporadas (TV/ONA) del anime, de la primera a la última:
        se va hacia atrás por las precuelas y luego hacia delante por las
        secuelas, pasando por especiales, OVAs y películas (Dr. Stone va de
        «Stone Wars» al especial «Ryuusui» y de ahí a «New World»), pero solo
        cuentan las de TV/ONA. Si AniList falla a medias, lo que se haya reunido.
        """
        start = await self.option(anilist_id)
        if start is None:
            return []
        first, seen = start, {start.anilist_id}
        for _ in range(MAX_HOPS):
            prev = first.step("PREQUEL", seen)
            opt = await self.option(prev) if prev else None
            if opt is None:
                break
            seen.add(opt.anilist_id)
            first = opt
        walk, seen = [first], {first.anilist_id}
        for _ in range(MAX_HOPS):
            nxt = walk[-1].step("SEQUEL", seen)
            opt = await self.option(nxt) if nxt else None
            if opt is None:
                break
            seen.add(opt.anilist_id)
            walk.append(opt)
        # las que aún no se han estrenado no se pueden pedir
        return [o for o in walk if o.format in MAIN_FORMATS and o.status != "NOT_YET_RELEASED"][:MAX_SEASONS]


class SpanishSynopsis:
    """Sinopsis en español de TMDB (de la serie entera: TMDB no separa bien las temporadas)."""
    URL = "https://api.themoviedb.org/3/search/tv"

    def __init__(self, key: str):
        self.key = key
        self._cache: dict[int, str] = {}

    def _auth(self) -> tuple[dict, dict]:
        # clave v3 (32 caracteres) por parámetro; el token de lectura v4 (JWT) por cabecera
        if len(self.key) > 40:
            return {}, {"Authorization": f"Bearer {self.key}"}
        return {"api_key": self.key}, {}

    async def find(self, opt: Option) -> str:
        if opt.anilist_id in self._cache:
            return self._cache[opt.anilist_id]
        params, headers = self._auth()
        found = ""
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                for name in dict.fromkeys(n for n in (opt.english, opt.title, opt.native) if n):
                    r = await c.get(self.URL, params={**params, "query": name, "language": "es-ES"},
                                    headers=headers)
                    r.raise_for_status()
                    hits = [h for h in r.json().get("results") or []
                            if h.get("original_language") == "ja" and (h.get("overview") or "").strip()]
                    if hits:
                        found = hits[0]["overview"].strip()
                        break
        except (httpx.HTTPError, ValueError) as ex:
            log.info("TMDB no da la sinopsis de %s: %s", opt.title, ex)
            return ""
        self._cache[opt.anilist_id] = found
        return found
