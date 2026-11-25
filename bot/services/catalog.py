"""
Animes de AniList para pedir por torrent lo que la web no tiene: opciones de
una búsqueda (con portada, sinopsis y géneros, para las fichas) y el pack de
un anime (para «todo»): sus temporadas y, con ellas, sus OVAs, especiales y
películas.

La sinopsis de AniList está en inglés. Con TMDB_API_KEY se busca antes en
TMDB la de la serie en español; si no hay, va la de AniList.
"""

import html
import logging
import re
from dataclasses import dataclass, field

import httpx

from . import anilist
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

# lo que se puede pedir por torrent
SERIES_FORMATS = ("TV", "TV_SHORT", "ONA", "OVA", "SPECIAL", "MOVIE")
# lo que cuenta como temporada en el pack
MAIN_FORMATS = ("TV", "TV_SHORT", "ONA")
# lo que va en el pack además de las temporadas
EXTRA_FORMATS = ("OVA", "SPECIAL", "MOVIE")
# relaciones de AniList por las que se llega a las temporadas y a los extras
RELATIONS = ("PREQUEL", "SEQUEL", "SIDE_STORY", "PARENT")
MAX_SEASONS = 12
MAX_EXTRAS = 10
MAX_HOPS = 25        # pasos por la cadena, contando especiales y películas
FORMAT_TEXT = {"TV": "TV", "TV_SHORT": "TV corta", "ONA": "ONA", "OVA": "OVA", "SPECIAL": "especial",
               "MOVIE": "película"}
EXTRA_TAG = {"OVA": "OVA", "SPECIAL": "Especial", "MOVIE": "🎬 Película"}
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


def _dig(m: dict, *keys, default=None):
    """m[k1][k2]…, o default si falta algo por el camino (AniList pone null donde no hay dato)."""
    for k in keys:
        m = (m or {}).get(k)
    return default if m is None else m


def _season(m: dict) -> str:
    """«Otoño 2019» (o solo «Otoño» si no trae el año)."""
    season = SEASON_TEXT.get(m.get("season") or "", "")
    return f"{season} {m['seasonYear']}" if season and m.get("seasonYear") else season


def _neighbours(m: dict) -> list[tuple[str, int, str]]:
    """(relación, id, formato) de los animes relacionados por RELATIONS (sin los vídeos musicales)."""
    return [(e["relationType"], int(e["node"]["id"]), e["node"].get("format") or "")
            for e in _dig(m, "relations", "edges", default=[])
            if e.get("relationType") in RELATIONS
            and _dig(e, "node", "type") == "ANIME" and _dig(e, "node", "format") != "MUSIC"]


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
    # (relación, id, formato): por ellas se llega a las temporadas y a los extras (ver RELATIONS)
    neighbours: list[tuple[str, int, str]] = field(default_factory=list)

    @property
    def releasing(self) -> bool:
        return self.status == "RELEASING"

    @property
    def movie(self) -> bool:
        return self.format == "MOVIE"

    @property
    def tag(self) -> str:
        """«OVA», «Especial» o «🎬 Película» para los extras; "" para las temporadas (las numera Anime-Automator)."""
        return EXTRA_TAG.get(self.format, "")

    @property
    def has_pack(self) -> bool:
        """
        ¿Puede tener más cosas (otras temporadas, OVAs, películas)? Si al
        final no hay nada más, se pide sola.
        """
        return any(r in ("PREQUEL", "SEQUEL") or (r == "SIDE_STORY" and f in EXTRA_FORMATS)
                   or (r == "PARENT" and f in MAIN_FORMATS) for r, _, f in self.neighbours)

    def step(self, rel: str, seen: set) -> int | None:
        """La precuela/secuela por la que seguir: mejor una de TV/ONA; si no, un especial, OVA o película."""
        cands = sorted((f not in MAIN_FORMATS, i) for r, i, f in self.neighbours if r == rel and i not in seen)
        return cands[0][1] if cands else None

    def back(self, seen: set) -> int | None:
        """
        Por dónde ir hacia atrás: la precuela; si no la hay y esto es una OVA o
        película, aquello de lo que cuelga (su serie, la OVA de la que sale).
        """
        prev = self.step("PREQUEL", seen)
        if prev is None and self.format not in MAIN_FORMATS:
            prev = self.step("PARENT", seen)
        return prev

    def ahead(self, seen: set) -> int | None:
        return self.step("SEQUEL", seen)

    def aside(self, seen: set):
        """
        Las OVAs, especiales y películas que cuelgan de esta (secuela o historia
        paralela) y aún no se han visto. Se mira `seen` al ir sacándolas.
        """
        return (i for r, i, f in self.neighbours
                if r in ("SEQUEL", "SIDE_STORY") and f in EXTRA_FORMATS and i not in seen)

    def label(self) -> str:
        """«Kono Oto Tomare! 2 · 2019 · TV · 13 caps.» (o «en emisión»)."""
        parts = [self.title]
        if self.year:
            parts.append(str(self.year))
        parts.append(FORMAT_TEXT.get(self.format, self.format.lower()))
        if self.releasing:
            parts.append("en emisión")
        elif self.episodes and not self.movie:
            parts.append(f"{self.episodes} caps.")
        return " · ".join(parts)

    def details(self, spanish: str = "") -> Details:
        """La ficha (portada, sinopsis, datos) como las de la web."""
        eps = "En emisión" if self.releasing else (str(self.episodes) if self.episodes and not self.movie else "")
        return Details(
            cover_url=self.cover_url, synopsis=spanish or self.description, episodes=eps,
            season=self.season or (str(self.year) if self.year else ""),
            genres=", ".join(GENRE_TEXT.get(g, g) for g in self.genres[:5]),
            video=FORMAT_TEXT.get(self.format, self.format.lower()),
            note="" if spanish or not self.description else "🇬🇧 sinopsis en inglés",
        )

    @classmethod
    def from_media(cls, m: dict) -> "Option":
        english = _dig(m, "title", "english", default="")
        return cls(int(m["id"]), _dig(m, "title", "romaji") or english or "?", english,
                   _dig(m, "format", default=""), m.get("episodes"), _dig(m, "startDate", "year"),
                   _dig(m, "status", default=""), _dig(m, "coverImage", "large", default=""),
                   clean_description(m.get("description")), list(_dig(m, "genres", default=[])), _season(m),
                   _dig(m, "title", "native", default=""), _neighbours(m))


class AniListCatalog:
    def __init__(self, tmdb_key: str = ""):
        self.spanish = SpanishSynopsis(tmdb_key) if tmdb_key else None
        self._cache: dict[int, Option] = {}

    def _keep(self, opt: Option) -> Option:
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[opt.anilist_id] = opt
        return opt

    async def options(self, query: str, limit: int = 6) -> list[Option] | None:
        """Animes (series, OVAs, especiales y películas) que encajan con la búsqueda; None si AniList no responde."""
        data = await anilist.query(SEARCH, {"s": query}, timeout=8)
        if data is None:
            return None
        return [self._keep(Option.from_media(m)) for m in anilist.media(data)
                if m.get("format") in SERIES_FORMATS and m.get("status") != "NOT_YET_RELEASED"][:limit]

    async def option(self, anilist_id: int) -> Option | None:
        if anilist_id in self._cache:
            return self._cache[anilist_id]
        data = await anilist.query(BY_ID, {"id": anilist_id}, timeout=8)
        m = (data or {}).get("Media")
        return self._keep(Option.from_media(m)) if m else None

    async def details(self, options: list[Option]) -> dict[int, Details]:
        """Las fichas de las opciones, con la sinopsis en español si se encuentra."""
        out = {}
        for o in options:
            spanish = await self.spanish.find(o) if self.spanish else ""
            out[o.anilist_id] = o.details(spanish)
        return out

    async def pack(self, anilist_id: int) -> list[Option]:
        """
        Todo lo de ese anime que se puede pedir, de lo primero a lo último: las
        temporadas (TV/ONA) y, detrás de cada una, sus OVAs, especiales y
        películas. Se va hacia atrás por las precuelas y luego hacia delante
        por las secuelas, pasando por especiales, OVAs y películas (Dr. Stone va
        de «Stone Wars» al especial «Ryuusei» y de ahí a «New World»); los
        extras que cuelgan aparte («historia paralela», como la OVA de Monster
        Musume) se recogen de cada paso. Si AniList falla a medias, lo que se
        haya reunido.
        """
        start = await self.option(anilist_id)
        if start is None:
            return []
        back, _ = await self._chain(start, Option.back)
        walk, seen = await self._chain(back[-1], Option.ahead)
        out = await self._assemble(walk, seen)
        # lo que aún no se ha estrenado no se puede pedir
        return [o for o in out if o.status != "NOT_YET_RELEASED"]

    async def _chain(self, start: Option, nxt) -> tuple[list[Option], set]:
        """start y lo que se alcanza desde ahí con nxt(opción, vistos), como mucho MAX_HOPS pasos; y los vistos."""
        chain, seen = [start], {start.anilist_id}
        for _ in range(MAX_HOPS):
            i = nxt(chain[-1], seen)
            opt = await self.option(i) if i else None
            if opt is None:
                break
            seen.add(opt.anilist_id)
            chain.append(opt)
        return chain, seen

    async def _assemble(self, walk: list[Option], seen: set) -> list[Option]:
        """
        Las temporadas y extras del camino (hasta MAX_SEASONS y MAX_EXTRAS) y,
        detrás de cada paso, los extras que cuelgan aparte de él.
        """
        out, mains, extras = [], 0, 0
        for o in walk:
            if o.format in MAIN_FORMATS and mains < MAX_SEASONS:
                out.append(o)
                mains += 1
            elif o.format in EXTRA_FORMATS and extras < MAX_EXTRAS:
                out.append(o)
                extras += 1
            side = await self._hanging(o, seen, MAX_EXTRAS - extras)
            out += side
            extras += len(side)
        return out

    async def _hanging(self, o: Option, seen: set, room: int) -> list[Option]:
        """
        Lo que cuelga aparte de o (otra secuela que no es la del camino, historias
        paralelas) y, de eso, sus secuelas (la película 2 de la película 1): como mucho `room`.
        """
        found, pending = [], [o]
        while pending and len(found) < room:
            for i in pending.pop(0).aside(seen):
                if len(found) >= room:
                    break
                seen.add(i)
                side = await self.option(i)
                if side is not None:
                    found.append(side)
                    pending.append(side)
        return found


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
        """La sinopsis en español, o "" (si TMDB falla, se volverá a probar la próxima vez)."""
        if opt.anilist_id in self._cache:
            return self._cache[opt.anilist_id]
        try:
            found = await self._search(opt)
        except (httpx.HTTPError, ValueError) as ex:
            log.info("TMDB no da la sinopsis de %s: %s", opt.title, ex)
            return ""
        self._cache[opt.anilist_id] = found
        return found

    async def _search(self, opt: Option) -> str:
        """Busca por el nombre inglés, luego el romaji y luego el japonés, hasta dar con una."""
        params, headers = self._auth()
        async with httpx.AsyncClient(timeout=6) as c:
            for name in dict.fromkeys(n for n in (opt.english, opt.title, opt.native) if n):
                r = await c.get(self.URL, params={**params, "query": name, "language": "es-ES"}, headers=headers)
                r.raise_for_status()
                overview = _japanese_overview(r.json())
                if overview:
                    return overview
        return ""


def _japanese_overview(data: dict) -> str:
    """La sinopsis del primer anime japonés de una búsqueda de TMDB que la tenga, o ""."""
    hits = [h for h in data.get("results") or []
            if h.get("original_language") == "ja" and (h.get("overview") or "").strip()]
    return hits[0]["overview"].strip() if hits else ""
