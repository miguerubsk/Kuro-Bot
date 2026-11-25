"""
Nombres alternativos de un anime vía AniList (API pública, sin clave).

La gente busca con el nombre en inglés de Crunchyroll («Frieren: Beyond
Journey's End») o con el romaji de MyAnimeList, y japanpaw no siempre los
reconoce. AniList devuelve de cada anime el romaji (prácticamente el de
MyAnimeList), el inglés y los sinónimos; con eso se vuelve a buscar en japanpaw.
"""

import logging
import re
import time
import unicodedata

from . import anilist
from .anilist import names

log = logging.getLogger(__name__)

QUERY = """
query ($s: String) {
  Page(perPage: 4) {
    media(search: $s, type: ANIME, sort: SEARCH_MATCH) {
      idMal
      title { romaji english }
      synonyms
    }
  }
}
"""
CACHE_TTL = 24 * 3600
_cache: dict[str, tuple[float, list[str]]] = {}

# solo alfabeto latino (los sinónimos traen coreano, tailandés, japonés...)
_LATIN_RE = re.compile(r"^[\x20-\x7EÀ-ɏ‘’×]+$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower().replace("’", "'")).strip()


# ------------------------------------------------------------------ #
# ¿Se parecen dos títulos?
# ------------------------------------------------------------------ #
# lo que no identifica a un anime: temporadas, partes, partículas...
_SEASON_RE = re.compile(
    r"\b(?:\d+(?:st|nd|rd|th)|season|part|cour|temporada|movie|the|\d+)\b", re.IGNORECASE
)
_FILLER = {"no", "wa", "ga", "wo", "ni", "de", "to", "e", "mo", "na", "the", "a", "an", "of",
           "and", "in", "on", "ii", "iii", "iv", "s"}


def _words(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    t = _SEASON_RE.sub(" ", t.replace("&", " and "))
    words = []
    for w in re.findall(r"[^\W_]+", t):
        w = re.sub(r"o[ou]", "o", w)  # romanizaciones: ou / oo / ō -> o, uu / ū -> u
        w = re.sub(r"u+", "u", w)
        words.append(w)
    return words


def related(a: str, b: str) -> bool:
    """
    True si los dos títulos hablan del mismo anime (o de una temporada,
    película o spin-off suyo): uno contiene al otro sin contar espacios ni
    signos ("Dandadan" ⊂ "DAN DA DAN Season 2"), o comparten la mayoría de
    sus palabras significativas. "Space☆Dandy" no se parece a "Dan Da Dan".
    """
    wa, wb = _words(a), _words(b)
    ca, cb = "".join(wa), "".join(wb)
    if min(len(ca), len(cb)) >= 4 and (ca in cb or cb in ca):
        return True
    sa = {w for w in wa if w not in _FILLER}
    sb = {w for w in wb if w not in _FILLER}
    if not sa or not sb:
        return False
    common = len(sa & sb)
    return common / min(len(sa), len(sb)) >= 0.6 and common >= min(2, len(sa), len(sb))


def about(query: str, media: list[dict]) -> list[dict]:
    """
    Las entradas de AniList con algún título parecido a la búsqueda: AniList
    devuelve también animes que no tienen nada que ver con lo buscado.
    """
    return [m for m in media if any(related(query, n) for n in names(m))]


async def alternative_titles(query: str, limit: int = 3) -> list[str]:
    """
    Títulos con los que probar en japanpaw, de más a menos prometedor:
    romaji de cada resultado de AniList y, si no, su título inglés. Nunca
    lanza excepciones: si AniList falla, devuelve [].
    """
    key = _norm(query)
    hit = _cached(key)
    if hit is not None:
        return hit[:limit]

    data = await anilist.query(QUERY, {"s": query})
    if data is None:
        return []
    media = about(query, anilist.media(data))
    titles = _romaji_first(_latin_titles(media, skip=key), media)

    _cache[key] = (time.time(), titles)
    log.info("AniList: %r -> %s", query, titles[:limit])
    return titles[:limit]


def _cached(key: str) -> list[str] | None:
    hit = _cache.get(key)
    return hit[1] if hit and time.time() - hit[0] < CACHE_TTL else None


def _candidates(m: dict) -> tuple:
    """Romaji, inglés y los dos primeros sinónimos de una entrada (pueden faltar)."""
    t = m.get("title") or {}
    return t.get("romaji"), t.get("english"), *(m.get("synonyms") or [])[:2]


def _latin_titles(media: list[dict], skip: str) -> list[str]:
    """Los candidatos en alfabeto latino, sin repetir (ni el de `skip`, ya normalizado)."""
    titles: list[str] = []
    seen = {skip}
    for cand in (c for m in media for c in _candidates(m) if c and _LATIN_RE.match(c)):
        n = _norm(cand)
        if n and n not in seen:
            seen.add(n)
            titles.append(cand.replace("’", "'"))
    return titles


def _romaji_first(titles: list[str], media: list[dict]) -> list[str]:
    """El romaji de cada anime primero (es como lo nombra japanpaw casi siempre)."""
    romajis = [m["title"]["romaji"].replace("’", "'") for m in media if (m.get("title") or {}).get("romaji")]
    return sorted(titles, key=lambda x: 0 if x in romajis else 1)
