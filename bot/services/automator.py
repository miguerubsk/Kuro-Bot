"""Cliente de Anime-Automator (/download, /check, /seasons, /watches) y cómo contar sus respuestas."""

import html
import logging

import httpx

from ..core.text import compress_ranges

log = logging.getLogger(__name__)

ERROR_TEXT = {
    "nas_not_mounted": "la NAS no está montada en el servidor de descargas",
    "page_fetch_failed": "no se pudo descargar la página del anime",
    "no_title": "la página del anime no tiene título",
    "folder_resolution_failed": "no se pudo decidir la carpeta de destino",
    "no_tab_found": "no hay ninguna versión descargable en la página",
    "bad_url": "el enlace no es válido",
    "unreachable": "el servicio de descargas no responde",
    "http_error": "el servicio de descargas devolvió un error",
}


class AutomatorClient:
    def __init__(self, base_url: str, secret: str = ""):
        self.base = base_url.rstrip("/")
        self.secret = secret   # el mismo CALLBACK_SECRET que firma /events

    async def _post(self, path: str, body: dict, timeout: float, connect: float = 10) -> dict:
        """
        POST con JSON. Nunca lanza: si no responde, {"status": "unreachable"}; si
        responde algo que no es un JSON con "status", {"status": "http_error"}.
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=connect)) as c:
                r = await c.post(f"{self.base}{path}", json=body)
        except httpx.HTTPError as ex:
            log.warning("Anime-Automator no responde a %s: %s", path, ex)
            return {"status": "unreachable", "error": str(ex)}
        try:
            data = r.json()
        except ValueError:
            data = None
        if not isinstance(data, dict) or "status" not in data:
            return {"status": "http_error", "error": f"HTTP {r.status_code}", "_raw": data}
        return data

    @staticmethod
    def _body(paste_url: str, movie: bool, title: str | None, **extra) -> dict:
        body = {"url": paste_url, **{k: v for k, v in extra.items() if v is not None}}
        if movie:
            body["kind"] = "movie"
        if title:
            body["title"] = title
        return body

    async def request_download(self, paste_url: str, job_id: int | None = None, movie: bool = False,
                               title: str | None = None) -> dict:
        """
        Con job_id, Anime-Automator no avisa por su propio Telegram y envía el
        progreso capítulo a capítulo a nuestro endpoint /events.
        """
        body = self._body(paste_url, movie, title, job_id=None if job_id is None else str(job_id))
        data = await self._post("/download", body, timeout=180)
        log.info("Respuesta de Anime-Automator para %s: %s", paste_url, data)
        return data

    async def check_library(self, paste_url: str, movie: bool = False, title: str | None = None) -> dict:
        """
        Qué hay ya en la biblioteca, sin descargar nada. Estados: "nothing_new"
        (está todo), "in_progress" (lo que falta ya se está bajando), "missing"
        (falta algo: lista en "missing") o un error.
        """
        data = await self._post("/check", self._body(paste_url, movie, title), timeout=120)
        log.info("Biblioteca para %s: %s", paste_url,
                 {k: data.get(k) for k in ("status", "name", "have", "available", "missing")})
        return data

    async def sync_watches(self, watches: list[dict]) -> bool:
        """
        La lista completa de animes vigilados en el Drive (sustituye a la
        anterior): [{"watch_url", "title", "schedule", "timezone"}].
        """
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.put(f"{self.base}/watches", json={"watches": watches},
                                headers={"X-Callback-Secret": self.secret})
            r.raise_for_status()
            return True
        except httpx.HTTPError as ex:
            log.warning("No pude mandar los seguimientos a Anime-Automator: %s", ex)
            return False

    async def poll_watch(self, watch_url: str) -> dict:
        """Que mire ya ese anime en el Drive, aunque esté fuera de su ventana."""
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(f"{self.base}/watches/poll", json={"watch_url": watch_url},
                                 headers={"X-Callback-Secret": self.secret})
            return r.json()
        except (httpx.HTTPError, ValueError) as ex:
            log.warning("No pude pedir que se mire %s en el Drive: %s", watch_url, ex)
            return {"status": "unreachable", "error": str(ex)}

    async def seasons(self, titles: list[str], budget: float = 12) -> list[dict]:
        """
        Temporada de cada título según Anime-Automator (título + AniList):
        [{"title", "base", "key", "season": "2", "subtitle"}], en el mismo orden.
        Si falla, [] (los resultados se muestran sin marcar).
        """
        if not titles:
            return []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(budget + 10, connect=5)) as c:
                r = await c.post(f"{self.base}/seasons", json={"titles": titles, "budget": budget})
                return r.json().get("seasons") or []
        except (httpx.HTTPError, ValueError, AttributeError) as ex:
            log.warning("No se pudieron calcular las temporadas: %s", ex)
            return []


# ---------------------------------------------------------------------- #
# Respuestas de /download en texto (para el admin)
# ---------------------------------------------------------------------- #
def describe(result: dict, fallback_name: str, for_admin: bool = False) -> str:
    st = result.get("status")
    name = html.escape(result.get("name") or fallback_name)
    folder = f"\nCarpeta: <code>{html.escape(result.get('folder', ''))}</code>" if for_admin and result.get("folder") else ""
    if result.get("kind") == "movie":
        where = html.escape(f"{result.get('folder', '')}/{result.get('file', '')}")
        dest = f"\nDestino: <code>{where}</code>" if for_admin else ""
        if st == "queued" and result.get("queued"):
            return f"🎬 Película <b>{name}</b> en cola.{dest}"
        if st == "queued":
            return f"🎬 La película <b>{name}</b> ya estaba en cola."
        if st == "nothing_new":
            return f"✅ La película <b>{name}</b> ya estaba en la colección.{dest}"
    if st == "queued":
        queued = result.get("queued") or []
        txt = (
            f"📥 <b>{name}</b>: {len(queued)} capítulo(s) en cola "
            f"({compress_ranges(queued)}) de {result.get('available', '?')} disponibles"
        )
        if result.get("have"):
            txt += f"; ya había {result['have']}"
        txt += "."
        if result.get("already_in_progress"):
            txt += f"\nYa estaban en cola: {compress_ranges(result['already_in_progress'])}"
        return txt + folder
    if st == "nothing_new":
        return (
            f"✅ <b>{name}</b> ya está completo ({result.get('have', '?')} de "
            f"{result.get('available', '?')} capítulos disponibles)." + folder
        )
    reason = ERROR_TEXT.get(st, f"estado desconocido «{html.escape(str(st))}»")
    txt = f"❌ No se pudo encolar <b>{name}</b>: {reason}."
    if for_admin and result.get("error"):
        txt += f"\n<code>{html.escape(str(result['error']))[:500]}</code>"
    return txt
