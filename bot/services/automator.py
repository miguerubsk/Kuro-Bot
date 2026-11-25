"""Cliente de Anime-Automator (/download, /check, /seasons, /watches, /torrent) y cómo contar sus respuestas."""

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
    # por torrent
    "nothing_found": "no hay torrents con subtítulos en español",
    "unsupported": "por torrent solo van series (no películas)",
    "not_found": "AniList no conoce ese anime",
    "anilist_down": "AniList no responde",
    "transmission_failed": "Transmission no acepta los torrents",
    "unauthorized": "Anime-Automator no acepta el CALLBACK_SECRET",
    "bad_request": "petición mal formada",
}


class AutomatorClient:
    def __init__(self, base_url: str, secret: str = ""):
        self.base = base_url.rstrip("/")
        self.secret = secret   # el mismo CALLBACK_SECRET que firma /events

    async def _post(self, path: str, body: dict, timeout: float, connect: float = 10, signed: bool = False) -> dict:
        """
        POST con JSON. Nunca lanza: si no responde, {"status": "unreachable"}; si
        responde algo que no es un JSON con "status", {"status": "http_error"}.
        """
        headers = {"X-Callback-Secret": self.secret} if signed else None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=connect)) as c:
                r = await c.post(f"{self.base}{path}", json=body, headers=headers)
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

    @staticmethod
    def _torrent_body(anilist_id: int, season: str | None, **extra) -> dict:
        body = {"anilist_id": int(anilist_id), **{k: v for k, v in extra.items() if v is not None}}
        if season:
            body["season"] = season
        return body

    async def torrent_check(self, anilist_id: int, season: str | None = None) -> dict:
        """
        Qué capítulos hay por torrent de esa entrada de AniList, sin descargar:
        "missing" (con "missing", "found", "season", "folder"...), "nothing_new",
        "in_progress", "nothing_found" o un error.
        """
        data = await self._post("/torrent/check", self._torrent_body(anilist_id, season), timeout=240, signed=True)
        log.info("Torrent para AniList %s: %s", anilist_id,
                 {k: data.get(k) for k in ("status", "name", "season", "found", "missing")})
        return data

    async def torrent_download(self, anilist_id: int, season: str | None = None, job_id: int | None = None) -> dict:
        """Lo mismo, y pone a descargar lo que falte (progreso por /events, como /download)."""
        body = self._torrent_body(anilist_id, season, job_id=None if job_id is None else str(job_id))
        data = await self._post("/torrent/download", body, timeout=300, signed=True)
        log.info("Descarga por torrent de AniList %s: %s", anilist_id, data)
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
    movie = _describe_movie(result, name, for_admin) if result.get("kind") == "movie" else None
    if movie:
        return movie
    folder = _folder_line(result) if for_admin else ""
    if st == "queued":
        return _describe_queued(result, name) + folder
    if st == "nothing_new":
        return (
            f"✅ <b>{name}</b> ya está completo ({result.get('have', '?')} de "
            f"{result.get('available', '?')} capítulos disponibles)." + folder
        )
    return _describe_error(result, name, for_admin)


def _folder_line(result: dict) -> str:
    return f"\nCarpeta: <code>{html.escape(result['folder'])}</code>" if result.get("folder") else ""


def _describe_movie(result: dict, name: str, for_admin: bool) -> str | None:
    """La respuesta de una película; None si no es de las que se cuentan aparte (los errores)."""
    st = result.get("status")
    where = html.escape(f"{result.get('folder', '')}/{result.get('file', '')}")
    dest = f"\nDestino: <code>{where}</code>" if for_admin else ""
    if st == "queued" and result.get("queued"):
        return f"🎬 Película <b>{name}</b> en cola.{dest}"
    if st == "queued":
        return f"🎬 La película <b>{name}</b> ya estaba en cola."
    if st == "nothing_new":
        return f"✅ La película <b>{name}</b> ya estaba en la colección.{dest}"
    return None


def _describe_queued(result: dict, name: str) -> str:
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
    return txt


def _describe_error(result: dict, name: str, for_admin: bool) -> str:
    st = result.get("status")
    reason = ERROR_TEXT.get(st, f"estado desconocido «{html.escape(str(st))}»")
    txt = f"❌ No se pudo encolar <b>{name}</b>: {reason}."
    if for_admin and result.get("error"):
        txt += f"\n<code>{html.escape(str(result['error']))[:500]}</code>"
    return txt


def describe_torrent(result: dict, fallback_name: str) -> str:
    """Lo mismo para el admin, en una petición por torrent (con temporada y grupos)."""
    st = result.get("status")
    name = html.escape(result.get("name") or fallback_name)
    if st == "in_progress":
        txt = f"⏳ <b>{name}</b>: lo que falta ya se está descargando."
    elif st == "missing":   # consulta: aún no se ha pedido nada
        txt = f"🧲 <b>{name}</b>: faltan {compress_ranges(result.get('missing') or [])}."
    else:
        txt = describe(result, fallback_name, for_admin=True)
    extra = _torrent_extra(result)
    if extra:
        txt += "\n🧲 Torrent · " + " · ".join(extra)
    if "Carpeta:" not in txt:
        txt += _folder_line(result)
    return txt


def _torrent_extra(result: dict) -> list[str]:
    """Temporada, grupos (de más a menos capítulos) y lo que Transmission no aceptó."""
    extra = []
    if result.get("season"):
        extra.append(f"T{html.escape(str(result['season']))}")
    groups = result.get("groups") or {}
    if groups:
        extra.append(", ".join(f"{html.escape(g)} ×{n}" for g, n in sorted(groups.items(), key=lambda x: -x[1])))
    if result.get("not_added"):
        extra.append(f"Transmission no aceptó {compress_ranges(result['not_added'])}")
    return extra
