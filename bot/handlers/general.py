"""Comandos para todos: /start, /ayuda, /id, /carros (o /cupo)."""

import logging

from .base import Access, ChatCommand, register

log = logging.getLogger(__name__)


@register
class Start(ChatCommand):
    names = ("start",)
    access = Access.ANYONE   # gestiona él mismo el alta con palabra clave

    async def execute(self, ctx):
        policy = self.k.access
        if policy.allows(ctx.chat_id):
            txt = self.k.texts.help(ctx.chat_id)
            if not ctx.is_admin and policy.open:
                txt = ctx.say("open_warning") + "\n\n" + txt
            return await ctx.reply(txt)

        if policy.blocked(ctx.chat_id):
            return  # demasiados intentos: se ignora en silencio
        name = ctx.user_name
        if policy.try_register(ctx.chat_id, " ".join(ctx.args), name):
            log.info("Chat %s dado de alta: %s", ctx.chat_id, name)
            await ctx.reply(ctx.say("welcome_new") + "\n\n" + self.k.texts.help(ctx.chat_id))
            await self.k.messenger.send(self.k.admin, self.k.persona.say(
                "admin_new_member", self.k.admin, who=name, chat_id=ctx.chat_id))
        else:
            await self.deny(ctx)


@register
class Help(ChatCommand):
    names = ("ayuda", "help")

    async def execute(self, ctx):
        await ctx.reply(self.k.texts.help(ctx.chat_id))


@register
class ChatId(ChatCommand):
    names = ("id",)
    access = Access.ANYONE   # para poder pedir acceso hay que saber el número

    async def execute(self, ctx):
        await ctx.reply_key("chat_id", chat_id=ctx.chat_id)


@register
class Cupo(ChatCommand):
    names = ("carros", "cupo")   # los cupos de la semana son «carros»

    async def execute(self, ctx):
        q = self.k.quota
        if ctx.is_admin:
            await ctx.reply_key("quota_admin")
        elif q.exhausted(ctx.chat_id):
            await ctx.reply(self.k.texts.no_quota(ctx.chat_id))
        else:
            await ctx.reply_key("quota_left", left=q.remaining(ctx.chat_id), limit=q.limit)
