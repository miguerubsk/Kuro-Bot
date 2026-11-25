"""
Cliente de la API de change-detection.io (/api/v1, cabecera x-api-key).

Cada seguimiento es un «watch» de la página de pastes del anime. Solo se
mira el contenedor de los enlaces de descarga (FILTER), así que el aviso
salta cuando aparece un capítulo nuevo y no por anuncios u otros cambios
de la página. El aviso lo manda change-detection a Anime-Automator
(/webhook), como con los seguimientos de siempre.
"""

import json
import logging

import httpx

log = logging.getLogger(__name__)

# Cada pestaña de descarga (div.tab_content) tiene arriba créditos, enlaces VIP
# y de reportar, y debajo la rejilla con un enlace «Capítulo N» por capítulo:
# solo esa rejilla cambia cuando sale uno nuevo
FILTER = ".tab_content .ep-grid"
NOTIFY_BODY = json.dumps({"watch_url": "{{watch_url}}", "watch_title": "{{watch_title}}"})


class ChangeDetectionError(Exception):
    pass


class ChangeDetectionClient:
    def __init__(self, base_url: str, api_key: str, tag: str = "", fetch_backend: str = "",
                 notify_url: str = "", tz: str = "Europe/Madrid", check_minutes: int = 60):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.tag = tag
        self.fetch_backend = fetch_backend
        self.notify_url = notify_url
        self.tz = tz
        self.check_minutes = max(5, check_minutes)

    @property
    def enabled(self) -> bool:
        return bool(self.base and self.key)

    async def _call(self, method: str, path: str, body: dict | None = None):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as c:
                r = await c.request(method, f"{self.base}/api/v1{path}", json=body,
                                    headers={"x-api-key": self.key})
        except httpx.HTTPError as ex:
            raise ChangeDetectionError(f"change-detection no responde: {ex}") from ex
        if r.status_code >= 400:
            raise ChangeDetectionError(f"change-detection respondió HTTP {r.status_code}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError:
            return r.text

    # ------------------------------------------------------------- watches
    def _timing(self, schedule) -> dict:
        """Cada cuánto y qué días se mira: dentro del horario, cada check_minutes; sin horario, cada 6 h."""
        return {
            "time_between_check_use_default": False,
            "time_between_check": {"minutes": self.check_minutes} if schedule.limited else {"hours": 6},
            "time_schedule_limit": schedule.time_schedule_limit(self.tz),
        }

    def payload(self, url: str, title: str, schedule) -> dict:
        body = {"url": url, "title": title, "include_filters": [FILTER], **self._timing(schedule)}
        if self.tag:
            body["tag"] = self.tag
        if self.fetch_backend:
            body["fetch_backend"] = self.fetch_backend
        if self.notify_url:
            body.update(notification_urls=[self.notify_url], notification_body=NOTIFY_BODY,
                        notification_format="text")
        return body

    async def find(self, url: str) -> str | None:
        """uuid de un watch que ya vigile esa URL (creado a mano o por Kuro), o None."""
        data = await self._call("GET", "/watch")
        if isinstance(data, dict):
            for uuid, w in data.items():
                if isinstance(w, dict) and (w.get("url") or "").strip() == url:
                    return w.get("uuid") or uuid
        return None

    async def create(self, url: str, title: str, schedule) -> str:
        data = await self._call("POST", "/watch", self.payload(url, title, schedule))
        uuid = data.get("uuid") if isinstance(data, dict) else None
        uuid = uuid or await self.find(url)
        if not uuid:
            raise ChangeDetectionError("change-detection no ha devuelto el identificador del seguimiento")
        log.info("Seguimiento creado en change-detection: %s (%s) -> %s", title, url, uuid)
        return uuid

    async def reschedule(self, uuid: str, schedule):
        await self._call("PUT", f"/watch/{uuid}", self._timing(schedule))

    async def delete(self, uuid: str):
        await self._call("DELETE", f"/watch/{uuid}")
        log.info("Seguimiento %s borrado de change-detection", uuid)
