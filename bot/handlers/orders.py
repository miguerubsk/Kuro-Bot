"""Botones de encargo: pedir uno, pedir todas las temporadas, y la decisión del admin."""

from ..orders import commands as decisions
from ..orders.placing import BundlePlacing, SinglePlacing, Submitter
from ..ui.progress import Progress
from .base import Access, ButtonCommand, register


class PlaceButton(ButtonCommand):
    async def place(self, ctx, placing_cls, *args):
        sub = Submitter.for_chat(self.k, ctx.chat_id, ctx.user_name)
        await placing_cls(self.k, sub, Progress.for_query(ctx.query), *args).run()


@register
class Pick(PlaceButton):
    pattern = r"^pick:\d+$"

    async def execute(self, ctx):
        post_id = int(ctx.parts[0])
        await self.place(ctx, SinglePlacing, post_id, ctx.session.results.get(post_id))


@register
class PickAll(PlaceButton):
    pattern = r"^all:\d+$"

    async def execute(self, ctx):
        group = ctx.session.groups.get(int(ctx.parts[0]))
        if not group:
            return await Progress.for_query(ctx.query).edit(ctx.say("expired"))
        await self.place(ctx, BundlePlacing, group)


@register
class Decision(ButtonCommand):
    """ok/no (una petición) y bok/bno (un lote): la orden va en el propio botón."""
    pattern = decisions.PATTERN
    access = Access.ADMIN
    auto_answer = False   # la propia orden responde («Marchando…», «Rechazada»)

    async def execute(self, ctx):
        command, missing = decisions.decode(self.k, ctx.query.data)
        if command is None:
            return await ctx.alert(missing)
        await command.execute(ctx.query)
