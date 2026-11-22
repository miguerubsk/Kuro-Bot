"""Comandos del miauestro: /pendientes, /resetcupo, /descargados, /alta (y sus botones)."""

import logging

from telegram.error import BadRequest

from ..core.models import Status
from ..core.text import fmt_date
from ..orders.targets import SingleTarget
from .base import Access, ButtonCommand, ChatCommand, register

log = logging.getLogger(__name__)


@register
class Pendientes(ChatCommand):
    names = ("pendientes",)
    access = Access.ADMIN

    async def execute(self, ctx):
        reqs = self.k.db.pending()
        if not reqs:
            return await ctx.reply_key("admin_no_pending")
        for r in reqs:
            failed = r.status == Status.FAILED
            state = "⚠️ falló al enviarse" if failed else "pendiente"
            target = SingleTarget(self.k, [r])
            await ctx.reply(self.k.texts.admin_request(r) + f"\nEstado: {state} ({fmt_date(r.created_at)})",
                            disable_web_page_preview=True, reply_markup=target.keyboard(retry=failed))


@register
class ResetCupo(ChatCommand):
    names = ("resetcupo",)
    access = Access.ADMIN

    async def execute(self, ctx):
        target = None
        if ctx.args:
            try:
                target = int(ctx.args[0])
            except ValueError:
                return await ctx.message.reply_text("Uso: /resetcupo [id_chat]")
        n = self.k.db.reset_quota(target)
        log.info("Cupos reiniciados (%s): %s peticiones", target or "todos", n)
        await ctx.reply_key("admin_reset", n=n)


@register
class Alta(ChatCommand):
    """/alta código [nombre]: dejar pasar a alguien que le ha dado su código al miauestro."""
    names = ("alta",)
    access = Access.ADMIN

    async def execute(self, ctx):
        policy = self.k.access
        if not policy.can_add:
            return await ctx.reply_key("admin_add_open")
        try:
            target = int(ctx.args[0])
        except (IndexError, ValueError):
            return await ctx.message.reply_text("Uso: /alta código [nombre]")
        if policy.allows(target):
            return await ctx.reply_key("admin_add_already", chat_id=target)
        name = " ".join(ctx.args[1:]).strip() or await self._name(ctx, target)
        policy.add(target, name)
        log.info("Chat %s dado de alta por el admin: %s", target, name)
        await self.k.messenger.send(target, self.k.persona.say("welcome_added", target)
                                    + "\n\n" + self.k.texts.help(target))
        await ctx.reply_key("admin_added", who=name, chat_id=target)

    @staticmethod
    async def _name(ctx, chat_id: int) -> str:
        """El nombre que tenga en Telegram (si ya ha hablado con Kuro), o el propio código."""
        try:
            chat = await ctx.bot.get_chat(chat_id)
        except Exception:
            return str(chat_id)
        name = chat.full_name or chat.title or str(chat_id)
        return name + (f" (@{chat.username})" if chat.username else "")


@register
class Descargados(ChatCommand):
    names = ("descargados", "historial")
    access = Access.ADMIN

    async def execute(self, ctx):
        text, kb = self.k.history.render(self.k.admin)
        await ctx.reply(text, reply_markup=kb)


@register
class HistoryPage(ButtonCommand):
    pattern = r"^hist:-?\d+:\d+$"
    access = Access.ADMIN
    denied_key = "not_admin"

    async def execute(self, ctx):
        target, page = map(int, ctx.parts)
        text, kb = self.k.history.render(target, page)
        try:
            await ctx.query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        except BadRequest as ex:
            if "not modified" not in str(ex).lower():
                raise
