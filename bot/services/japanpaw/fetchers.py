"""
Cómo se descargan las páginas de la web (patrón estrategia).

- DirectFetcher: httpx con User-Agent de navegador (sin él la web bloquea).
- BrowserFetcher: el Chrome headless de Anime-Automator (sockpuppetbrowser)
  vía Playwright/CDP, para cuando hay bloqueo anti-bot.
- FallbackFetcher: prueba una tras otra hasta que alguna funcione.

Todas tienen la misma interfaz (fetch) y son intercambiables.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Callable

import httpx

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


class Blocked(Exception):
    """La web ha devuelto una página de bloqueo anti-bot."""


class FetchFailed(Exception):
    """Esta estrategia no ha podido traer la página (puede que otra sí)."""


def looks_blocked(status: int, text: str) -> bool:
    if status in (403, 429, 503):
        return True
    head = text[:5000]
    return "Just a moment" in head or "cf-chl" in head or "challenge-platform" in head


class Fetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str, want_json: bool = False):
        """Texto (o JSON ya decodificado) de la URL. Lanza FetchFailed si no puede."""


class DirectFetcher(Fetcher):
    ATTEMPTS = 2

    def __init__(self, client: Callable[[], httpx.AsyncClient]):
        self.client = client

    async def fetch(self, url: str, want_json: bool = False):
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                r = await self.client().get(url)
                if looks_blocked(r.status_code, r.text):
                    raise Blocked(f"HTTP {r.status_code}")
                r.raise_for_status()
                return r.json() if want_json else r.text
            except Blocked as ex:
                log.warning("La web bloquea la petición directa (%s), uso el navegador: %s", ex, url)
                raise FetchFailed(str(ex)) from ex
            except (httpx.HTTPError, ValueError) as ex:
                log.warning("Error consultando %s (intento %s): %s", url, attempt, ex)
                if attempt < self.ATTEMPTS:
                    await asyncio.sleep(2)
        log.info("Pruebo con el navegador tras fallar la petición directa")
        raise FetchFailed(url)


class BrowserFetcher(Fetcher):
    def __init__(self, cdp_url: str):
        self.cdp_url = cdp_url

    def _render(self, url: str) -> tuple[str, str]:
        """(html, texto_visible) renderizado por el navegador."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(self.cdp_url)
            try:
                page = browser.new_context().new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                # espera a que se resuelva un posible challenge de Cloudflare
                for _ in range(20):
                    if not looks_blocked(200, page.content()):
                        break
                    page.wait_for_timeout(1000)
                return page.content(), page.inner_text("body")
            finally:
                browser.close()

    async def fetch(self, url: str, want_json: bool = False):
        page_html, body_text = await asyncio.to_thread(self._render, url)
        if looks_blocked(200, page_html):
            raise FetchFailed("la web sigue bloqueando incluso desde el navegador")
        return json.loads(body_text) if want_json else page_html


class FallbackFetcher(Fetcher):
    def __init__(self, *chain: Fetcher):
        self.chain = chain

    async def fetch(self, url: str, want_json: bool = False):
        last: Exception | None = None
        for fetcher in self.chain:
            try:
                return await fetcher.fetch(url, want_json)
            except FetchFailed as ex:
                last = ex
        raise RuntimeError(str(last) if last else f"no se pudo descargar {url}")
