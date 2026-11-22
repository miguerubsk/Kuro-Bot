"""
Búsqueda en la web de anime (WordPress) y extracción del enlace de
paste de la página de cada anime.

El nombre real de la web no debe salir nunca en lo que ve la gente: los
textos usan {site} (ver persona).
"""

import html as htmlmod
import logging
import urllib.parse

import httpx

from .. import aliases
from ..netblock import NetBypass
from .fetchers import HEADERS, BrowserFetcher, DirectFetcher, FallbackFetcher, Fetcher
from .models import Details, PostInfo, SearchResult
from .parsing import clean_title, is_allowed_url, is_cover_url, parse_details, parse_post_html
from .ranking import rank

__all__ = ["JapanpawClient", "Details", "PostInfo", "SearchResult", "clean_title"]

log = logging.getLogger(__name__)


class JapanpawClient:
    MAX_RESULTS = 8
    FETCH_RESULTS = 100      # se piden muchos (lo máximo de WordPress) y se ordenan antes de recortar
    MIN_DIRECT_RESULTS = 3   # con menos, se prueba también con otros nombres (AniList)

    def __init__(self, base_url: str, browser_url: str, force_browser: bool = False,
                 fetcher: Fetcher | None = None, proxy: str = ""):
        self.base = base_url.rstrip("/")
        self._http: httpx.AsyncClient | None = None
        self.bypass = NetBypass(proxy, HEADERS)
        browser = BrowserFetcher(browser_url)
        self.fetcher = fetcher or (browser if force_browser
                                   else FallbackFetcher(DirectFetcher(lambda: self.http, self.bypass), browser))

    @property
    def http(self) -> httpx.AsyncClient:
        """Un solo cliente HTTP para todo (reutiliza conexiones); se crea ya dentro del bucle de asyncio."""
        if self._http is None:
            self._http = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30)
        return self._http

    async def close(self):
        if self._http is not None:
            await self._http.aclose()
        await self.bypass.close()

    async def _json(self, path: str):
        return await self.fetcher.fetch(f"{self.base}{path}", want_json=True)

    async def _posts(self, post_ids: list[int], fields: str) -> list[dict]:
        """Varios posts en una sola consulta a la API de WordPress."""
        ids = ",".join(str(i) for i in post_ids)
        return await self._json(f"/wp-json/wp/v2/posts?include={ids}&per_page={len(post_ids)}&_fields={fields}") or []

    # ----------------------------------------------------------- búsqueda
    async def search(self, query: str) -> list[SearchResult]:
        params = urllib.parse.urlencode({"search": query, "per_page": self.FETCH_RESULTS,
                                         "type": "post", "subtype": "post"})
        data = await self._json(f"/wp-json/wp/v2/search?{params}")
        found = [SearchResult(post_id=int(item["id"]), url=item["url"],
                              title=htmlmod.unescape(item.get("title") or "").strip() or f"Post {item['id']}")
                 for item in data or []
                 if item.get("subtype") == "post" and is_allowed_url(item.get("url", ""))]
        results = rank(query, found)[:self.MAX_RESULTS]
        seen_titles: dict[str, int] = {}
        for r in results:
            seen_titles[r.title] = seen_titles.get(r.title, 0) + 1
        # títulos repetidos (distintas versiones): se distinguen por id
        for r in results:
            if seen_titles[r.title] > 1:
                r.title = f"{r.title} (#{r.post_id})"
        return results

    async def search_with_aliases(self, query: str) -> tuple[list[SearchResult], str | None]:
        """
        Busca tal cual y, si salen pocos resultados, pregunta a AniList por los
        otros nombres del anime y busca también con ellos. Devuelve
        (resultados, alias_que_ha_funcionado | None). Los resultados directos van
        primero; los de alias, detrás y sin duplicados.
        """
        direct = await self.search(query)
        if len(direct) >= self.MIN_DIRECT_RESULTS:
            return direct, None

        results = list(direct)
        seen = {r.post_id for r in results}
        used = None
        for alt in await aliases.alternative_titles(query):
            try:
                found = await self.search(alt)
            except Exception:
                log.warning("Fallo buscando el alias %r", alt, exc_info=True)
                continue
            # la búsqueda mira también el texto de las fichas y con nombres
            # cortos trae de todo: solo se quedan los que se parecen
            new = [r for r in found if r.post_id not in seen
                   and (aliases.related(alt, r.title) or aliases.related(query, r.title))]
            if new and used is None:
                used = alt
            for r in new:
                seen.add(r.post_id)
                results.append(r)
            if len(results) >= self.MAX_RESULTS:
                break
        # el alias solo merece mención si sin él no habría salido nada
        return results[:self.MAX_RESULTS], (used if not direct else None)

    # -------------------------------------------------------------- posts
    async def post_kinds(self, post_ids: list[int]) -> dict[int, set[str]]:
        """{post_id: {"pelicula", "en-emision", "serie"...}} (categorías de cada post)."""
        if not post_ids:
            return {}
        try:
            data = await self._posts(post_ids, "id,class_list")
        except Exception:
            log.warning("No se pudieron leer las categorías de %s", post_ids, exc_info=True)
            return {}
        return {int(item["id"]): {c[len("category-"):] for c in item.get("class_list") or []
                                  if c.startswith("category-")} for item in data}

    async def details(self, post_ids: list[int]) -> dict[int, Details]:
        """{post_id: Details} de varios posts en una sola consulta (vacío si falla)."""
        if not post_ids:
            return {}
        try:
            data = await self._posts(post_ids, "id,content")
        except Exception:
            log.warning("No se pudieron leer las fichas de %s", post_ids, exc_info=True)
            return {}
        out = {}
        for item in data:
            try:
                out[int(item["id"])] = parse_details((item.get("content") or {}).get("rendered", ""))
            except Exception:
                log.warning("Ficha ilegible: post %s", item.get("id"), exc_info=True)
        return out

    async def post_by_id(self, post_id: int) -> SearchResult | None:
        """Recupera título y URL de un post (por si la caché de búsqueda se ha perdido)."""
        try:
            data = await self._json(f"/wp-json/wp/v2/posts/{post_id}?_fields=id,link,title")
        except Exception:
            log.exception("No se pudo recuperar el post %s", post_id)
            return None
        url = data.get("link", "")
        if not is_allowed_url(url):
            return None
        title = htmlmod.unescape((data.get("title") or {}).get("rendered", "")).strip()
        return SearchResult(post_id=post_id, title=title or f"Post {post_id}", url=url)

    async def get_post(self, url: str, post_id: int, title: str = "") -> PostInfo:
        if not is_allowed_url(url):
            raise ValueError(f"URL fuera de la web: {url}")
        return parse_post_html(await self.fetcher.fetch(url), post_id, url, title)

    async def cover_bytes(self, url: str) -> bytes | None:
        """Descarga la portada (Telegram no siempre puede bajarla él solo por la protección de la web)."""
        if not url or not is_cover_url(url):
            return None
        try:
            r = await self.http.get(url)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") \
                    and 0 < len(r.content) < 9_000_000:
                return r.content
            log.info("Portada no disponible (%s): %s", r.status_code, url)
        except httpx.HTTPError as ex:
            log.info("Portada no disponible (%s): %s", ex, url)
        return None
