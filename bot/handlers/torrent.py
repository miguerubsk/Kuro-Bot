"""Botones de los encargos por torrent: elegir el anime de AniList (o todas sus temporadas), pedirlo y corregir la temporada."""

from telegram.constants import ParseMode

from ..core.models import Status
from ..orders import torrent as T
from ..orders.placing import Submitter
from ..orders.targets import SingleTarget
from ..ui.progress import Progress
from .base import Access, ButtonCommand, register


class TorrentButton(ButtonCommand):
    async def deny_torrent(self, ctx) -> bool:
        if self.k.torrent_allowed(ctx.chat_id):
            return False
        await Progress.for_query(ctx.query).edit(ctx.say("expired"))
        return True


@register
class TorrentPick(TorrentButton):
    """trt:<anilist_id>[:<temporada>]: qué hay por torrent (con temporada, la que corrige el admin)."""
    pattern = rf"^{T.OFFER}:\d+(:[\d.]+)?$"

    async def execute(self, ctx):
        if await self.deny_torrent(ctx):
            return
        anilist_id = int(ctx.parts[0])
        season = ctx.parts[1] if len(ctx.parts) > 1 and ctx.is_admin else None
        out = Progress.for_query(ctx.query)
        await T.TorrentOffer(self.k, ctx.chat_id, ctx.session).show(out, anilist_id, season)


@register
class TorrentGo(TorrentButton):
    """trg:<anilist_id>:<temporada>: hacer el encargo."""
    pattern = rf"^{T.GO}:\d+:[\d.]+$"

    async def execute(self, ctx):
        if await self.deny_torrent(ctx):
            return
        anilist_id, season = int(ctx.parts[0]), ctx.parts[1]
        sub = Submitter.for_chat(self.k, ctx.chat_id, ctx.user_name)
        await T.TorrentPlacing(self.k, sub, Progress.for_query(ctx.query), anilist_id, season, ctx.session).run()


@register
class TorrentAll(TorrentButton):
    """tra:<anilist_id>: qué hay de todas las temporadas de ese anime."""
    pattern = rf"^{T.ALL}:\d+$"

    async def execute(self, ctx):
        if await self.deny_torrent(ctx):
            return
        out = Progress.for_query(ctx.query)
        await T.TorrentSeasons(self.k, ctx.chat_id, ctx.session).show(out, int(ctx.parts[0]))


@register
class TorrentGoAll(TorrentButton):
    """trb:<lote>: pedir todas las temporadas ofrecidas como un solo encargo."""
    pattern = rf"^{T.GO_ALL}:\d+$"

    async def execute(self, ctx):
        if await self.deny_torrent(ctx):
            return
        sub = Submitter.for_chat(self.k, ctx.chat_id, ctx.user_name)
        await T.TorrentBundlePlacing(self.k, sub, Progress.for_query(ctx.query), int(ctx.parts[0]),
                                     ctx.session).run()


@register
class TorrentSeason(ButtonCommand):
    """trs:<petición>:<temporada>: el admin corrige la temporada de un encargo por torrent sin decidir."""
    pattern = rf"^{T.SEASON}:\d+:[\d.]+$"
    access = Access.ADMIN

    async def execute(self, ctx):
        req_id, season = int(ctx.parts[0]), ctx.parts[1]
        req = self.k.db.get(req_id)
        if not req or not req.torrent or req.status not in Status.OPEN:
            return await ctx.alert(ctx.say("already_decided", status=req.status if req else "?"))
        self.k.db.set_season(req_id, season)
        target = SingleTarget.load(self.k, req_id)
        await ctx.query.edit_message_text(target.admin_text(), parse_mode=ParseMode.HTML,
                                          disable_web_page_preview=True,
                                          reply_markup=target.keyboard(retry=req.status == Status.FAILED))
