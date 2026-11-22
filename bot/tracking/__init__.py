"""
Seguimiento semanal de lo que está en emisión (change-detection.io).

Cuando alguien pide un anime en emisión (suelto o dentro de «todas las
temporadas»), Kuro le ofrece vigilarlo. Si dice que sí:

- un cliente: el miauestro lo aprueba o lo rechaza (y hay un límite de
  seguimientos por cliente, TRACKING_LIMIT);
- el miauestro: se crea en el momento;
- si ese anime ya se vigila (por otro cliente o un watch hecho a mano), se
  apunta sin crear nada ni molestar al admin: no gasta recursos.

El watch mira solo la rejilla de enlaces de la página de pastes, y solo los
días y horas en que puede salir capítulo (horario de AniList; si no, el día
de la semana del estreno). change-detection avisa a Anime-Automator
(/webhook) y este baja lo que falte, como con los seguimientos de siempre.

Cada 12 h se repasan los activos: si la web ya no lo tiene en emisión (o
AniList lo da por terminado hace más de dos semanas), se borra el watch y se
avisa; si ha cambiado la hora de emisión, se reajusta la ventana.
"""

import asyncio
import logging
import os
import random
import time
from zoneinfo import ZoneInfo

from telegram.constants import ParseMode
from telegram.error import TelegramError

from ..core.models import TrackStatus
from ..core.text import e
from ..services.airing import AiringClient
from ..services.changedetection import ChangeDetectionClient, ChangeDetectionError
from ..ui.keyboards import yes_no
from .schedule import Schedule

log = logging.getLogger(__name__)

SITE_SUFFIX = " - Japan-Paw! Descarga Calidad"   # el <title> de la página de pastes
MAINTAIN_EVERY = 12 * 3600
FINISHED_GRACE = 14 * 24 * 3600     # AniList dice «terminado», pero puede faltar subir el último


class Tracker:
    # prefijos de callback_data (no cambiarlos: los botones viejos se quedan en los chats)
    YES, NO, APPROVE, REJECT, STOP = "tky", "tkn", "tka", "tkr", "tks"

    def __init__(self, kuro, cd: ChangeDetectionClient | None = None, airing: AiringClient | None = None):
        self.k = kuro
        cfg = kuro.cfg
        self.tz_name = _tz_name()
        self.tz = ZoneInfo(self.tz_name)
        self.cd = cd or ChangeDetectionClient(cfg.cd_url, cfg.cd_api_key, cfg.cd_tag, cfg.cd_fetch_backend,
                                              cfg.cd_notify_url, self.tz_name, cfg.tracking_check_minutes)
        self.airing = airing or AiringClient()
        self.window = cfg.tracking_window_hours
        self.limit = cfg.tracking_limit

    @property
    def enabled(self) -> bool:
        return self.cd.enabled

    def _say(self, key, to, **kw):
        return self.k.persona.say(key, to, **kw)

    def full(self, chat_id: int) -> bool:
        return not self.k.is_admin(chat_id) and self.k.db.track_counted(chat_id) >= self.limit

    # ------------------------------------------------------------ oferta
    async def offer(self, chat_id: int, user_name: str, post):
        """Tras pedir algo en emisión: «¿lo vigilo cada semana?» (nada si no procede)."""
        if not self.enabled or not post.airing or post.movie or not post.paste_url:
            return
        db = self.k.db
        if db.track_live_for(chat_id, post.paste_url):
            return
        if self.full(chat_id):
            await self.k.messenger.send(chat_id, self._say("track_offer_full", chat_id, title=post.title,
                                                           limit=self.limit))
            return
        tid = db.track_add(chat_id, user_name, post)
        kb = yes_no("📡 Sí, vigílalo", f"{self.YES}:{tid}", "No, gracias", f"{self.NO}:{tid}")
        await self.k.messenger.send(chat_id, self._say("track_offer", chat_id, title=post.title), reply_markup=kb)

    async def decline(self, t) -> str:
        self.k.db.track_transition(t.id, (TrackStatus.OFFERED,), TrackStatus.DECLINED)
        return self._say("track_declined", t.chat_id, title=t.title)

    async def accept(self, t) -> str:
        """El cliente (o el miauestro) dice que sí. Devuelve el texto para el mensaje de la oferta."""
        db, to = self.k.db, t.chat_id
        if self.full(to):
            db.track_transition(t.id, (TrackStatus.OFFERED,), TrackStatus.DECLINED)
            return self._say("track_offer_full", to, title=t.title, limit=self.limit)
        if not db.track_transition(t.id, (TrackStatus.OFFERED,), TrackStatus.PENDING):
            return self._say("track_already", to, title=t.title)

        schedule = await self.plan(t)
        t = db.track_get(t.id)
        when = schedule.describe()

        shared = db.track_active_for_url(t.paste_url)
        if shared:  # ya se vigila: se apunta sin crear nada
            db.track_update(t.id, watch_uuid=shared[0].watch_uuid, owned=shared[0].owned)
            db.track_transition(t.id, (TrackStatus.PENDING,), TrackStatus.ACTIVE)
            if not self.k.is_admin(to):
                await self.k.messenger.send(self.k.admin, self._say(
                    "track_admin_joined", self.k.admin, who=t.user_name, title=t.title))
            return self._say("track_joined", to, title=t.title, when=when)

        if self.k.is_admin(to):
            ok, detail = await self.activate(t)
            if not ok:
                return self._say("track_failed", to, title=t.title) + f"\n<code>{e(detail)}</code>"
            return self._say("track_active", to, title=t.title, when=when)

        try:
            msg = await self.k.messenger.bot.send_message(
                self.k.admin, self.admin_text(t), parse_mode=ParseMode.HTML, disable_web_page_preview=True,
                reply_markup=self.admin_keyboard(t))
        except TelegramError:
            log.exception("No se pudo enviar el seguimiento #%s al admin", t.id)
            db.track_transition(t.id, (TrackStatus.PENDING,), TrackStatus.OFFERED)
            return self._say("admin_unreachable", to)
        log.info("Seguimiento #%s (%s) pendiente del admin (mensaje %s)", t.id, t.title, msg.message_id)
        return self._say("track_sent", to, title=t.title, when=when)

    # ------------------------------------------------------------ horario
    async def plan(self, t) -> Schedule:
        """Ventana de comprobación: hora de emisión (AniList), si no el día del estreno, si no siempre."""
        info = await self.airing.lookup(t.title)
        if info and info.next_at:
            s = Schedule.from_airing(info.next_at, self.tz, self.window)
        else:
            s = None
            try:
                details = await self.k.site.details([t.post_id])
                d = details.get(t.post_id)
                s = Schedule.from_premiere(d.premiere, self.window) if d else None
            except Exception:
                log.warning("Sin ficha para el horario de %s", t.title, exc_info=True)
            s = s or Schedule.always()
        self.k.db.track_update(t.id, schedule=s.to_dict(), anilist_id=info.anilist_id if info else 0)
        log.info("Horario de %s: %s (%s)", t.title, s.describe(), s.source or "sin datos")
        return s

    # ------------------------------------------------------------ admin
    def admin_text(self, t) -> str:
        s = Schedule.from_dict(t.schedule)
        source = {"anilist": "hora de emisión de AniList", "estreno": "día del estreno; hora desconocida"}
        return (self._say("track_admin_request", self.k.admin, who=t.user_name, title=t.title)
                + f"\nVigilancia: {e(s.describe())} ({source.get(s.source, 'sin horario: cada 6 h')})"
                + f"\nCada {self.cd.check_minutes} min dentro de la ventana"
                + f"\n{e(t.post_url)}\n{e(t.paste_url)}")

    def admin_keyboard(self, t, retry: bool = False):
        return yes_no("🔁 Reintentar" if retry else "✅ Vigílalo", f"{self.APPROVE}:{t.id}",
                      "❌ Ni hablar", f"{self.REJECT}:{t.id}")

    async def activate(self, t) -> tuple[bool, str]:
        """Crea (o reutiliza) el watch y deja el seguimiento activo. (ok, detalle del error)."""
        db = self.k.db
        schedule = Schedule.from_dict(t.schedule)
        try:
            uuid, owned = await self.cd.find(t.paste_url), False
            if uuid:
                log.info("%s ya se vigilaba en change-detection (%s): no creo otro", t.paste_url, uuid)
            else:
                uuid, owned = await self.cd.create(t.paste_url, await self._watch_title(t), schedule), True
        except ChangeDetectionError as ex:
            log.error("No se pudo crear el seguimiento #%s: %s", t.id, ex)
            db.track_update(t.id, status=TrackStatus.FAILED)
            return False, str(ex)
        db.track_update(t.id, watch_uuid=uuid, owned=owned, status=TrackStatus.ACTIVE)
        return True, ""

    async def _watch_title(self, t) -> str:
        """
        El título del watch es el que recibe Anime-Automator en el webhook para
        decidir la carpeta: tiene que ser el mismo <title> que usó al descargar.
        """
        lib = await self.k.automator.check_library(t.paste_url, title=t.title)
        return (lib.get("title") or "").strip() or t.title + SITE_SUFFIX

    async def approve(self, t) -> tuple[bool, str]:
        """(ok, texto para el admin). Avisa al cliente."""
        if not self.k.db.track_transition(t.id, TrackStatus.OPEN, TrackStatus.PROCESSING):
            return True, self._say("already_decided", self.k.admin, status=self.k.db.track_get(t.id).status)
        if not t.schedule:
            await self.plan(t)
        t = self.k.db.track_get(t.id)
        ok, detail = await self.activate(t)
        when = Schedule.from_dict(t.schedule).describe()
        if not ok:
            return False, self._say("track_admin_failed", self.k.admin, title=t.title) + f"\n<code>{e(detail)}</code>"
        await self.k.messenger.send(t.chat_id, self._say("track_active", t.chat_id, title=t.title, when=when))
        return True, self._say("track_admin_approved", self.k.admin, title=t.title)

    async def reject(self, t) -> str:
        if not self.k.db.track_transition(t.id, TrackStatus.OPEN, TrackStatus.REJECTED):
            return self._say("already_decided", self.k.admin, status=self.k.db.track_get(t.id).status)
        await self.k.messenger.send(t.chat_id, self._say("track_rejected", t.chat_id, title=t.title))
        return self._say("track_admin_rejected", self.k.admin, title=t.title)

    # ------------------------------------------------------------ final
    async def stop(self, t, notify_key: str | None = None) -> bool:
        """Deja de vigilarlo para ese chat; si nadie más lo sigue y el watch es de Kuro, se borra."""
        db = self.k.db
        if not db.track_transition(t.id, (TrackStatus.ACTIVE, TrackStatus.PENDING, TrackStatus.FAILED),
                                   TrackStatus.ENDED):
            return False
        if t.watch_uuid and t.owned and not db.track_active_for_url(t.paste_url):
            try:
                await self.cd.delete(t.watch_uuid)
            except ChangeDetectionError as ex:
                log.error("No se pudo borrar el watch %s de %s: %s", t.watch_uuid, t.title, ex)
                await self.k.messenger.send(self.k.admin, self._say(
                    "track_admin_delete_failed", self.k.admin, title=t.title) + f"\n<code>{e(str(ex))}</code>")
        if notify_key:
            await self.k.messenger.send(t.chat_id, self._say(notify_key, t.chat_id, title=t.title))
        return True

    # ------------------------------------------------------ mantenimiento
    async def loop(self):
        await asyncio.sleep(300)
        while True:
            if self.enabled:
                try:
                    await self.maintain()
                except Exception:
                    log.exception("Fallo repasando los seguimientos")
            await asyncio.sleep(MAINTAIN_EVERY + random.uniform(-600, 600))

    async def maintain(self):
        groups: dict[str, list] = {}
        for t in self.k.db.track_list():
            groups.setdefault(t.paste_url, []).append(t)
        for url, ts in groups.items():
            await self._maintain_one(url, ts)
            await asyncio.sleep(3)   # AniList limita a ~30 consultas por minuto

    async def _maintain_one(self, url: str, ts: list):
        first, db = ts[0], self.k.db
        try:
            post = await self.k.site.get_post(first.post_url, first.post_id, first.title)
        except Exception as ex:
            log.warning("No pude releer %s para el seguimiento: %s", first.post_url, ex)
            return
        finished = not post.airing
        info = await self.airing.by_id(first.anilist_id) if first.anilist_id else None
        key = f"track_finished_since:{url}"
        if not finished and info and info.status == "FINISHED":
            since = db.kv_get(key) or time.time()
            db.kv_set(key, since)
            finished = time.time() - since > FINISHED_GRACE
        if finished:
            log.info("%s ya no está en emisión: fin del seguimiento", first.title)
            for t in ts:
                await self.stop(t, "track_ended")
            if not self.k.is_admin(first.chat_id) or len(ts) > 1:
                await self.k.messenger.send(self.k.admin, self._say("track_admin_ended", self.k.admin,
                                                                    title=first.title))
            return
        if info and info.next_at and first.owned:
            new = Schedule.from_airing(info.next_at, self.tz, self.window)
            if new != Schedule.from_dict(first.schedule):
                try:
                    await self.cd.reschedule(first.watch_uuid, new)
                except ChangeDetectionError as ex:
                    log.warning("No pude reajustar el horario de %s: %s", first.title, ex)
                    return
                log.info("Nuevo horario para %s: %s", first.title, new.describe())
                for t in ts:
                    db.track_update(t.id, schedule=new.to_dict())


def _tz_name() -> str:
    name = os.environ.get("TZ") or "Europe/Madrid"
    try:
        ZoneInfo(name)
        return name
    except Exception:
        return "Europe/Madrid"
