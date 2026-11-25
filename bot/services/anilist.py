"""La API de AniList (GraphQL): una consulta, las entradas de una búsqueda y los nombres de una entrada."""

import logging

import httpx

log = logging.getLogger(__name__)

ANILIST_URL = "https://graphql.anilist.co"


async def query(text: str, variables: dict, timeout: float = 10) -> dict | None:
    """El "data" de la respuesta, o None si AniList falla (nunca lanza)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(ANILIST_URL, json={"query": text, "variables": variables})
            r.raise_for_status()
            return r.json().get("data") or {}
    except Exception as ex:
        log.warning("AniList no ha respondido (%s): %s", variables, ex)
        return None


def media(data: dict | None) -> list[dict]:
    """Las entradas de una búsqueda (Page.media); [] si no hay ninguna o AniList ha fallado."""
    return ((data or {}).get("Page") or {}).get("media") or []


def names(m: dict) -> list[str]:
    """Romaji, inglés y sinónimos de una entrada (los que tenga)."""
    t = m.get("title") or {}
    return [x for x in (t.get("romaji"), t.get("english"), *(m.get("synonyms") or [])) if x]
