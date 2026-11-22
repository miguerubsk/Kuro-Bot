"""Buscar un anime y elegir entre los resultados (fichas con portada o lista)."""

import asyncio
import logging

from telegram.error import BadRequest

from ..ui.results import ResultsBuilder
from .base import Access, ButtonCommand, ChatCommand, TextCommand, register

log = logging.getLogger(__name__)


class SearchMixin:
    MIN_LEN, MAX_LEN = 2, 100

    async def search(self, ctx, query: str):
        k = self.k
        query = " ".join(query.split())
        if len(query) < self.MIN_LEN:
            return await ctx.reply_key("ask_name")
        query = query[:self.MAX_LEN]
        # sin cupo también se puede buscar: lo que ya está en la biblioteca, o
        # solo en peor calidad, no gasta cupo (el cupo se mira al elegir)
        status = await ctx.reply_key("searching", query=query)
        try:
            results, alias = await k.site.search_with_aliases(query)
        except Exception:
            log.exception("Fallo buscando %r", query)
            return await status.edit_text(ctx.say("search_error"), parse_mode="HTML")
        if not results:
            return await status.edit_text(ctx.say("not_found", query=query), parse_mode="HTML")

        found, details = await asyncio.gather(ResultsBuilder(k).build(ctx.session, results),
                                              k.site.details([r.post_id for r in results]))
        intro = (ctx.say("alias_hint", query=query, alias=alias) + "\n") if alias else ""
        outro = ctx.say("pick_seasons") if found.has_groups else ""
        if details:
            await status.edit_text(intro + ctx.say("pick_cards") + outro, parse_mode="HTML")
            try:
                return await k.cards.send(ctx.bot, ctx.chat_id, ctx.session, found.choices, details)
            except Exception:
                log.exception("No se pudieron enseñar las fichas; va la lista de siempre")
        await status.edit_text(intro + ctx.say("pick") + outro, parse_mode="HTML", reply_markup=found.keyboard())


@register
class Pedir(SearchMixin, ChatCommand):
    names = ("pedir",)

    async def execute(self, ctx):
        await self.search(ctx, " ".join(ctx.args))


@register
class FreeText(SearchMixin, TextCommand):
    async def execute(self, ctx):
        await self.search(ctx, ctx.message.text or "")


@register
class CardPage(ButtonCommand):
    pattern = r"^card:\d+:\d+$"
    access = Access.ANYONE
    auto_answer = False

    async def execute(self, ctx):
        cid, idx = map(int, ctx.parts)
        deck = ctx.session.decks.get(cid)
        if not deck or idx >= len(deck.items):
            return await ctx.alert(ctx.say("expired"))
        await ctx.query.answer()
        await self.k.cards.show(ctx.query, deck, cid, idx)


@register
class Noop(ButtonCommand):
    """El contador «2 / 5» de los paginadores."""
    pattern = r"^noop$"
    access = Access.ANYONE

    async def execute(self, ctx):
        pass


@register
class Cancel(ButtonCommand):
    pattern = r"^cancel$"
    access = Access.ANYONE

    async def execute(self, ctx):
        q = ctx.query
        if not q.message.photo:
            return await q.edit_message_text(ctx.say("cancelled"), parse_mode="HTML")
        try:
            await q.message.delete()
        except BadRequest:
            await q.edit_message_reply_markup(None)
        await ctx.bot.send_message(ctx.chat_id, ctx.say("cancelled"), parse_mode="HTML")
