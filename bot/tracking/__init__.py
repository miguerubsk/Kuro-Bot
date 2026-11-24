"""
Seguimiento semanal de lo que está en emisión (change-detection.io y el Drive).

Cuando alguien pide un anime en emisión (suelto o dentro de «todas las
temporadas»), Kuro le ofrece vigilarlo. Si dice que sí:

- un cliente: el miauestro lo aprueba o lo rechaza (y hay un límite de
  seguimientos por cliente, TRACKING_LIMIT);
- el miauestro: se crea en el momento;
- si ese anime ya se vigila (por otro cliente o un watch hecho a mano), se
  apunta sin crear nada ni molestar al admin: no gasta recursos.

Hay dos vigilantes (TRACKING_SOURCES), y los dos miran solo en la ventana
de emisión (como mucho 24 h desde la hora de AniList; si no, el día del
estreno en Japón):

- changedetection: un watch de la página de pastes que mira solo la rejilla
  de enlaces; avisa a Anime-Automator (/webhook).
- drive: Kuro le manda a Anime-Automator la lista completa de animes
  vigilados (PUT /watches: URL, título de la ficha y ventana), y este mira
  la carpeta de cada uno en la unidad de Drive de emisión cada 10 min.

Los dos acaban en el mismo encolado, que nunca baja dos veces lo mismo. La
lista del Drive se manda cada vez que cambia algo, al arrancar y tras cada
repaso (si falla, se reintenta cada 10 min). Si se quita «changedetection»
de TRACKING_SOURCES, el repaso borra los watches que creó Kuro allí.

Cada 12 h se repasan los activos: si la web ya no lo tiene en emisión (o
AniList lo da por terminado hace más de dos semanas), se termina y se avisa;
si ha cambiado la hora de emisión, se reajusta la ventana.
"""

import asyncio
import dataclasses
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
from ..services.japanpaw import clean_title
from ..ui.keyboards import yes_no
from .schedule import Schedule

log = logging.getLogger(__name__)

SITE_SUFFIX = " - Japan-Paw! Descarga Calidad"   # el <title> de la página de pastes
MAINTAIN_EVERY = 12 * 3600
RESYNC_EVERY = 10 * 60              # reintento de la lista del Drive si no llegó
K_DRIVE_SYNCED = "drive_watches_synced"
K_CD_MINUTES = "cd_check_minutes"   # intervalo con el que están los watches de change-detection
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
        self.sources = cfg.tracking_sources
        self._sync_lock = asyncio.Lock()
        self._sync_pending = False

    @property
    def use_cd(self) -> bool:
        return "changedetection" in self.sources and self.cd.enabled

    @property
    def use_drive(self) -> bool:
        return "drive" in self.sources

    @property
    def enabled(self) -> bool:
        return self.use_cd or self.use_drive

    def sources_text(self) -> str:
        parts = []
        if self.use_cd:
            parts.append(f"change-detection cada {self.cd.check_minutes} min")
        if self.use_drive:
            parts.append("el Drive (Anime-Automator) cada 10 min")
        return " y ".join(parts) or "nadie"

    def _say(self, key, to, **kw):
        return self.k.persona.say(key, to, **kw)

    def full(self, chat_id: int, paste_url: str = "") -> bool:
        """¿No le queda cupo? Lo que ya sigue otro no gasta cupo, así que para eso siempre hay."""
        if self.k.is_admin(chat_id):
            return False
        if paste_url and self.k.db.track_followed_by_others(chat_id, paste_url):
            return False
        return self.k.db.track_counted(chat_id) >= self.limit

    # ---------------------------------------------------------- emisión
    async def confirm_airing(self, post):
        """
        La web no siempre marca lo que está en emisión: si dice que no, se
        pregunta a AniList por ese mismo título (exacto: otra temporada no
        vale). Devuelve el post, con airing=True si AniList lo da por emitiéndose.
        """
        if post.airing or post.movie:
            return post
        try:
            info = await self.airing.exact(clean_title(post.title))
        except Exception:
            log.warning("AniList no ha podido confirmar la emisión de %s", post.title, exc_info=True)
            return post
        if info and info.status == "RELEASING":
            log.info("%s: la web no lo marca en emisión, pero AniList sí (%s)", post.title, info.anilist_id)
            return dataclasses.replace(post, airing=True)
        return post

    # ------------------------------------------------------------ oferta
    async def offer(self, chat_id: int, user_name: str, post):
        """Tras pedir algo en emisión: «¿lo vigilo cada semana?» (nada si no procede)."""
        if not self.enabled or not post.airing or post.movie or not post.paste_url:
            return
        db = self.k.db
        if db.track_live_for(chat_id, post.paste_url):
            return
        if self.full(chat_id, post.paste_url):
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
        shared_now = db.track_followed_by_others(to, t.paste_url)
        if not shared_now and self.full(to):
            db.track_transition(t.id, (TrackStatus.OFFERED,), TrackStatus.DECLINED)
            return self._say("track_offer_full", to, title=t.title, limit=self.limit)
        if not db.track_transition(t.id, (TrackStatus.OFFERED,), TrackStatus.PENDING):
            return self._say("track_already", to, title=t.title)
        if shared_now:
            db.track_update(t.id, shared=True)

        schedule = await self.plan(t)
        t = db.track_get(t.id)
        when = schedule.describe()

        shared = db.track_active_for_url(t.paste_url)
        if shared:  # ya se vigila: se apunta sin crear nada
            db.track_update(t.id, watch_uuid=shared[0].watch_uuid, owned=shared[0].owned,
                            watch_title=shared[0].watch_title)
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
                s = Schedule.from_premiere(d.premiere, self.tz) if d else None
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
                + f"\nDentro de la ventana mira {e(self.sources_text())}"
                + f"\n{e(t.post_url)}\n{e(t.paste_url)}")

    def admin_keyboard(self, t, retry: bool = False):
        return yes_no("🔁 Reintentar" if retry else "✅ Vigílalo", f"{self.APPROVE}:{t.id}",
                      "❌ Ni hablar", f"{self.REJECT}:{t.id}")

    async def activate(self, t) -> tuple[bool, str]:
        """
        Crea (o reutiliza) el watch de change-detection, si se usa, deja el
        seguimiento activo y manda la lista al Drive. (ok, detalle del error)
        """
        db = self.k.db
        schedule = Schedule.from_dict(t.schedule)
        title = t.watch_title or await self._watch_title(t)
        uuid, owned = "", False
        if self.use_cd:
            try:
                uuid = await self.cd.find(t.paste_url)
                if uuid:
                    log.info("%s ya se vigilaba en change-detection (%s): no creo otro", t.paste_url, uuid)
                else:
                    uuid, owned = await self.cd.create(t.paste_url, title, schedule), True
            except ChangeDetectionError as ex:
                log.error("No se pudo crear el seguimiento #%s: %s", t.id, ex)
                db.track_update(t.id, status=TrackStatus.FAILED, watch_title=title)
                return False, str(ex)
        db.track_update(t.id, watch_uuid=uuid, owned=owned, watch_title=title, status=TrackStatus.ACTIVE)
        await self.sync_automator()
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
        await self.sync_automator()
        return True

    # ------------------------------------------------------------ Drive
    async def sync_automator(self) -> bool:
        """
        Manda a Anime-Automator la lista completa de lo que se vigila en el
        Drive: un watch por URL, con el título de la ficha y la misma ventana
        que change-detection. Sin «drive» en TRACKING_SOURCES, la vacía (una vez).
        """
        db = self.k.db
        async with self._sync_lock:
            if not self.use_drive and not db.kv_get(K_DRIVE_SYNCED):
                return True
            out: dict[str, dict] = {}
            for t in db.track_list() if self.use_drive else []:   # los activos
                if t.paste_url in out:
                    continue
                title = t.watch_title
                if not title:   # seguimientos de antes: se calcula una vez
                    title = await self._watch_title(t)
                    for same in db.track_active_for_url(t.paste_url):
                        db.track_update(same.id, watch_title=title)
                out[t.paste_url] = {"watch_url": t.paste_url, "title": title,
                                    "schedule": Schedule.from_dict(t.schedule).to_dict() if t.schedule else {},
                                    "timezone": self.tz_name}
            ok = await self.k.automator.sync_watches(list(out.values()))
            self._sync_pending = not ok
            if ok:
                db.kv_set(K_DRIVE_SYNCED, 1 if self.use_drive else 0)
                log.info("Lista del Drive enviada a Anime-Automator: %s anime(s)", len(out))
            return ok

    async def poll_now(self, t) -> dict:
        """Que Anime-Automator mire ya ese anime en el Drive (aunque esté fuera de la ventana)."""
        return await self.k.automator.poll_watch(t.paste_url)

    async def retire_cd(self):
        """Sin «changedetection» en TRACKING_SOURCES: borra los watches que creó Kuro allí."""
        if "changedetection" in self.sources or not self.cd.enabled:
            return
        db, done = self.k.db, 0
        for t in db.track_list():
            if not (t.owned and t.watch_uuid):
                continue
            try:
                await self.cd.delete(t.watch_uuid)
            except ChangeDetectionError as ex:
                log.warning("No pude retirar el watch %s (%s) de change-detection: %s", t.watch_uuid, t.title, ex)
                continue
            for same in db.track_active_for_url(t.paste_url):
                db.track_update(same.id, watch_uuid="", owned=False)
            done += 1
        if done:
            log.info("Retirados %s watches de change-detection: ya vigila solo el Drive", done)
            await self.k.messenger.send(self.k.admin, self._say("track_admin_cd_retired", self.k.admin, n=done))

    # ------------------------------------------------------ mantenimiento
    async def loop(self):
        await self._safe(self.sync_automator, "mandando la lista del Drive")
        await asyncio.sleep(300)
        while True:
            if self.enabled:
                await self._safe(self.maintain, "repasando los seguimientos")
            # hasta el próximo repaso, reintenta la lista del Drive si no llegó
            until = time.time() + MAINTAIN_EVERY + random.uniform(-600, 600)
            while time.time() < until:
                await asyncio.sleep(min(RESYNC_EVERY, max(1, until - time.time())))
                if self._sync_pending:
                    await self._safe(self.sync_automator, "reintentando la lista del Drive")

    @staticmethod
    async def _safe(fn, what: str):
        try:
            await fn()
        except Exception:
            log.exception("Fallo %s", what)

    async def maintain(self):
        groups: dict[str, list] = {}
        for t in self.k.db.track_list():
            groups.setdefault(t.paste_url, []).append(t)
        for url, ts in groups.items():
            await self._maintain_one(url, ts)
            await asyncio.sleep(3)   # AniList limita a ~30 consultas por minuto
        await self.retire_cd()
        await self.refresh_cd_interval()
        await self.sync_automator()

    async def refresh_cd_interval(self):
        """Si ha cambiado TRACKING_CHECK_MINUTES, se aplica también a los watches que ya existen."""
        db = self.k.db
        if not self.use_cd:
            return
        prev = db.kv_get(K_CD_MINUTES)
        if prev is None or int(prev) == self.cd.check_minutes:
            db.kv_set(K_CD_MINUTES, self.cd.check_minutes)
            return
        done: set[str] = set()
        for t in db.track_list():
            if t.owned and t.watch_uuid and t.watch_uuid not in done:
                try:
                    await self.cd.reschedule(t.watch_uuid, Schedule.from_dict(t.schedule))
                except ChangeDetectionError as ex:
                    log.warning("No pude cambiar el intervalo de %s: %s", t.title, ex)
                    return   # se reintenta en el próximo repaso
                done.add(t.watch_uuid)
        log.info("Intervalo de change-detection: de %s a %s min en %s watch(es)", prev, self.cd.check_minutes, len(done))
        db.kv_set(K_CD_MINUTES, self.cd.check_minutes)

    async def _maintain_one(self, url: str, ts: list):
        first, db = ts[0], self.k.db
        try:
            post = await self.k.site.get_post(first.post_url, first.post_id, first.title)
        except Exception as ex:
            log.warning("No pude releer %s para el seguimiento: %s", first.post_url, ex)
            return
        info = await self.airing.by_id(first.anilist_id) if first.anilist_id else None
        # la web puede no marcarlo: si AniList dice que se sigue emitiendo, no se acaba
        finished = not post.airing and not (info and info.status == "RELEASING")
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
        new = await self._fresh_schedule(first, info)
        if new is None or new.to_dict() == (first.schedule or {}):
            return
        if self.use_cd and first.owned and first.watch_uuid:
            try:
                await self.cd.reschedule(first.watch_uuid, new)
            except ChangeDetectionError as ex:
                log.warning("No pude reajustar el horario de %s: %s", first.title, ex)
                return
        log.info("Nuevo horario para %s: %s", first.title, new.describe())
        for t in ts:
            db.track_update(t.id, schedule=new.to_dict())

    async def _fresh_schedule(self, t, info) -> Schedule | None:
        """
        La ventana que toca ahora: la hora de AniList si la hay; si no, se
        recalcula la del estreno (cambio de hora) y las antiguas de más de un día.
        """
        if info and info.next_at:
            return Schedule.from_airing(info.next_at, self.tz, self.window)
        old = t.schedule or {}
        if old.get("source") != "estreno" and int(old.get("hours") or 0) <= Schedule.from_dict(old).hours:
            return None
        try:
            d = (await self.k.site.details([t.post_id])).get(t.post_id)
        except Exception:
            log.warning("Sin ficha para recalcular el horario de %s", t.title, exc_info=True)
            d = None
        return (Schedule.from_premiere(d.premiere, self.tz) if d else None) or Schedule.from_dict(old)


def _tz_name() -> str:
    name = os.environ.get("TZ") or "Europe/Madrid"
    try:
        ZoneInfo(name)
        return name
    except Exception:
        return "Europe/Madrid"
