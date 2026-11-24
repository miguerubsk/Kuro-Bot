"""
Hacer un encargo desde los resultados de búsqueda.

Dos ejes que se combinan:

- Qué se pide (método plantilla): SinglePlacing (un post) o BundlePlacing
  (todas las temporadas, un solo encargo). Placing.run() fija los pasos
  comunes: reunir lo pedido, mirar el cupo, guardarlo y entregarlo.
- Quién lo pide (patrón estrategia): DirectSubmitter para el miauestro (va
  directo, sin consultas ni cupo) y ApprovalSubmitter para los clientes
  (biblioteca, cupo y visto bueno del admin).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from telegram.constants import ParseMode
from telegram.error import TelegramError

from ..core.models import Status
from ..core.text import e, season_tag
from ..services.japanpaw import PostInfo
from ..ui.session import SeasonGroup
from .library import Assessment
from .targets import BundleTarget, SingleTarget, Target

log = logging.getLogger(__name__)


@dataclass
class Item:
    post: PostInfo
    season: str | None = None
    check: Assessment | None = None


class Stop(Exception):
    """Se corta el encargo; el motivo ya se le ha contado a quien pide."""


# ---------------------------------------------------------------------- #
# Quién pide
# ---------------------------------------------------------------------- #
class Submitter(ABC):
    status: str             # estado inicial de las peticiones
    checks_library: bool

    def __init__(self, kuro, chat_id: int, user_name: str):
        self.k = kuro
        self.chat_id = chat_id
        self.user_name = user_name

    @staticmethod
    def for_chat(kuro, chat_id: int, user_name: str) -> "Submitter":
        cls = DirectSubmitter if kuro.is_admin(chat_id) else ApprovalSubmitter
        return cls(kuro, chat_id, user_name)

    def already_active(self, post_id: int):
        return None

    async def check(self, post) -> Assessment | None:
        return None

    def blocked_by_quota(self, exempt: bool) -> bool:
        return False

    @abstractmethod
    async def submit(self, placing: "Placing", target: Target): ...


class DirectSubmitter(Submitter):
    """El miauestro: su encargo va directo (Anime-Automator ya dice «nada nuevo» sin bajar nada)."""
    status = Status.PROCESSING
    checks_library = False

    async def submit(self, placing, target):
        await placing.out.edit(placing.say("sending", title=placing.title, label=placing.sending_label(target)))
        results = [(r, await self.k.dispatcher.dispatch(r)) for r in target.reqs]
        await placing.out.edit(target.direct_report(results))


class ApprovalSubmitter(Submitter):
    """Un cliente: se mira la biblioteca y el cupo, y el admin tiene que dar el visto bueno."""
    status = Status.PENDING
    checks_library = True

    def already_active(self, post_id):
        return self.k.db.active_for_post(self.chat_id, post_id)

    async def check(self, post):
        return await self.k.library.assess(post, self.chat_id)

    def blocked_by_quota(self, exempt):
        return not exempt and self.k.quota.exhausted(self.chat_id)

    async def submit(self, placing, target):
        try:
            msg = await self.k.messenger.bot.send_message(
                self.k.admin, target.admin_text(), parse_mode=ParseMode.HTML,
                disable_web_page_preview=True, reply_markup=target.keyboard())
            target.remember_admin_msg(msg.message_id)
        except TelegramError:
            log.exception("No se pudo enviar el encargo %s al admin", [r.id for r in target.reqs])
            for r in target.reqs:
                self.k.db.transition(r.id, (Status.PENDING,), Status.FAILED)
            await placing.out.edit(placing.say("admin_unreachable"))
            return
        await placing.out.edit(placing.sent_text(target))


# ---------------------------------------------------------------------- #
# Qué se pide
# ---------------------------------------------------------------------- #
class Placing(ABC):
    def __init__(self, kuro, submitter: Submitter, out):
        self.k = kuro
        self.sub = submitter
        self.out = out
        self.chat_id = submitter.chat_id
        self.say = kuro.persona.to(self.chat_id)
        self.exempt = False
        self.airing: list[PostInfo] = []   # lo leído que está en emisión: se ofrece vigilarlo

    async def run(self):
        try:
            items = await self.collect()
        except Stop:
            # aunque no haga falta bajar nada (ya está todo), lo que salga después sí
            return await self.offer_tracking()
        self.exempt = all(i.check is not None and i.check.exempt for i in items)
        if self.sub.blocked_by_quota(self.exempt):
            await self.out.edit(self.k.texts.no_quota(self.chat_id))
            return
        await self.sub.submit(self, self.store(items))
        await self.offer_tracking()

    def saw(self, post: PostInfo):
        if post.airing and not post.movie and post.paste_url:
            self.airing.append(post)

    async def offer_tracking(self):
        for post in self.airing:
            try:
                await self.k.tracker.offer(self.chat_id, self.sub.user_name, post)
            except Exception:
                log.exception("Fallo ofreciendo el seguimiento de %s", post.title)

    async def stop(self, key: str, **kw):
        await self.out.edit(self.say(key, **kw))
        raise Stop

    def _add(self, item: Item, bundle_id: int = 0) -> int:
        rid = self.k.db.add(self.chat_id, self.sub.user_name, item.post, self.sub.status,
                            bundle_id=bundle_id, quota_exempt=self.exempt)
        if item.check and item.check.admin_note:
            self.k.memo.notes[rid] = item.check.admin_note
        return rid

    def _left(self) -> dict:
        return {"left": self.k.quota.remaining(self.chat_id), "limit": self.k.quota.limit}

    @property
    @abstractmethod
    def title(self) -> str: ...

    @abstractmethod
    async def collect(self) -> list[Item]:
        """Lo que hay que pedir (lanza Stop, tras avisar, si no hay nada)."""

    @abstractmethod
    def store(self, items: list[Item]) -> Target: ...

    @abstractmethod
    def sending_label(self, target: Target) -> str:
        """Texto plano (se escapa al formatear) que va tras el título en «enviando…»."""

    @abstractmethod
    def sent_text(self, target: Target) -> str: ...


class SinglePlacing(Placing):
    def __init__(self, kuro, submitter, out, post_id: int, cached: tuple[str, str] | None):
        super().__init__(kuro, submitter, out)
        self.post_id = post_id
        self.cached = cached
        self.item: Item | None = None

    @property
    def title(self):
        return self.item.post.title

    async def collect(self):
        if self.cached:
            title, url = self.cached
        else:
            found = await self.k.site.post_by_id(self.post_id)
            if not found:
                await self.stop("expired")
            title, url = found.title, found.url

        prev = self.sub.already_active(self.post_id)
        if prev:
            await self.stop("already_pending", title=prev.title)

        await self.out.edit(self.say("reading_post", title=title))
        try:
            post = await self.k.site.get_post(url, self.post_id, title)
        except Exception:
            log.exception("Fallo leyendo el post %s (%s)", self.post_id, url)
            await self.stop("post_error")
        if not post.paste_url:
            await self.stop("no_link", title=post.title)
        post = await self.k.tracker.confirm_airing(post)
        self.saw(post)

        check = None
        if self.sub.checks_library:
            # antes de gastar cupo o molestar al admin: ¿ya está en la biblioteca?
            await self.out.edit(self.say("checking_library", title=post.title))
            check = await self.sub.check(post)
            if check.state == Assessment.COMPLETE:
                movie = post.movie or check.lib.get("kind") == "movie"
                await self.stop("library_movie" if movie else "library_complete", title=post.title,
                                have=check.lib.get("have", "?"))
            if check.state == Assessment.BUSY:
                await self.stop("library_busy", title=post.title)
        self.item = Item(post, None, check)
        return [self.item]

    def store(self, items):
        rid = self._add(items[0])
        return SingleTarget(self.k, [self.k.db.get(rid)])

    def sending_label(self, target):
        return self.k.texts.post_label(self.item.post)

    def sent_text(self, target):
        post = self.item.post
        return (self.say("sent_to_admin", title=post.title, label=self.k.texts.post_label(post), **self._left())
                + self.item.check.user_note
                + ("" if post.movie else self.k.texts.airing_note(self.chat_id, post.airing, post.label)))


class BundlePlacing(Placing):
    def __init__(self, kuro, submitter, out, group: SeasonGroup):
        super().__init__(kuro, submitter, out)
        self.group = group
        self.skipped: list[str] = []

    @property
    def title(self):
        return self.group.base

    async def collect(self):
        await self.out.edit(self.say("bundle_reading", title=self.group.base))
        items = []
        for post_id, title, url, season in self.group.items:
            if self.sub.already_active(post_id):
                self.skipped.append(season_tag(season))
                continue
            try:
                post = await self.k.site.get_post(url, post_id, title)
            except Exception:
                log.exception("Fallo leyendo el post %s (%s)", post_id, url)
                continue
            if not post.paste_url:
                continue
            post = await self.k.tracker.confirm_airing(post)
            self.saw(post)
            check = await self.sub.check(post)
            if check is not None and not check.available:
                self.skipped.append(season_tag(season))
                continue
            items.append(Item(post, season, check))
        if not items:
            await self.stop("bundle_all_have", title=self.group.base)
        return items

    def store(self, items):
        bundle_id = self.k.db.new_bundle_id()
        self.k.memo.bundle_names[bundle_id] = self.group.base
        reqs = []
        for item in items:
            rid = self._add(item, bundle_id)
            self.k.memo.seasons[rid] = item.season
            reqs.append(self.k.db.get(rid))
        return BundleTarget(self.k, reqs)

    def _items_html(self, target) -> str:
        return ", ".join(e(season_tag(self.k.memo.seasons[r.id])) for r in target.reqs)

    def sending_label(self, target):
        return " (" + ", ".join(season_tag(self.k.memo.seasons[r.id]) for r in target.reqs) + ")"

    def sent_text(self, target):
        skipped = self.say("bundle_skipped", items_html=", ".join(self.skipped)) if self.skipped else ""
        upgrade = self.say("library_upgrade") if self.exempt else ""
        return (self.say("bundle_sent", title=self.group.base, items_html=self._items_html(target), **self._left())
                + upgrade + skipped)
