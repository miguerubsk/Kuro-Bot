"""
Comandos, mensajes y botones de Telegram como órdenes (patrón orden / command).

Cada cosa que el bot atiende es una clase con `execute(ctx)`. La clase base
hace lo que antes se repetía en cada función: comprobar quién puede usarla
(Access), responder al botón y darle a `execute` un Ctx con atajos.

Para añadir un comando nuevo basta con escribir otra subclase con
@register; app.py los da de alta todos sin cambiar nada más (abierto-cerrado).
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import BaseHandler, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from ..core.text import plain
from ..ui.session import ChatSession

log = logging.getLogger(__name__)

HTML = ParseMode.HTML
REGISTRY: list[type["Command"]] = []


def register(cls):
    REGISTRY.append(cls)
    return cls


class Access(Enum):
    ANYONE = "anyone"
    MEMBER = "member"   # según la política de acceso (lista blanca, palabra clave…)
    ADMIN = "admin"


class Ctx:
    """Lo que necesita cada orden, con el destinatario ya puesto (say nunca se queda sin chat)."""

    def __init__(self, kuro, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.k = kuro
        self.update = update
        self.context = context
        self.query = update.callback_query
        self.message = update.effective_message
        self.chat_id = self.query.message.chat.id if self.query else update.effective_chat.id
        self.say = kuro.persona.to(self.chat_id)
        self.session = ChatSession(context.chat_data)

    @property
    def bot(self):
        return self.context.bot

    @property
    def args(self) -> list[str]:
        return self.context.args or []

    @property
    def is_admin(self) -> bool:
        return self.k.is_admin(self.chat_id)

    @property
    def user_name(self) -> str:
        """Nombre (@usuario) en «grupo», para que el admin sepa quién pide."""
        u, c = self.update.effective_user, self.update.effective_chat
        name = u.full_name if u else "?"
        if u and u.username:
            name += f" (@{u.username})"
        if c and c.type != ChatType.PRIVATE and c.title:
            name += f" en «{c.title}»"
        return name

    async def reply(self, text: str, **kw):
        kw.setdefault("parse_mode", HTML)
        return await self.message.reply_text(text, **kw)

    async def reply_key(self, key: str, **kw):
        return await self.reply(self.say(key, **kw))

    async def alert(self, text: str):
        await self.query.answer(plain(text), show_alert=True)


class Command(ABC):
    access = Access.MEMBER
    group = 0

    def __init__(self, kuro):
        self.k = kuro

    @abstractmethod
    def handler(self) -> BaseHandler: ...

    @abstractmethod
    async def execute(self, ctx: Ctx): ...

    def _allowed(self, ctx: Ctx) -> bool:
        if self.access is Access.ADMIN:
            return ctx.is_admin
        if self.access is Access.MEMBER:
            return self.k.access.allows(ctx.chat_id)
        return True

    async def deny(self, ctx: Ctx): ...

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        ctx = Ctx(self.k, update, context)
        if not self._allowed(ctx):
            return await self.deny(ctx)
        await self.execute(ctx)


class ChatCommand(Command):
    """/comando"""
    names: tuple[str, ...] = ()

    def handler(self):
        return CommandHandler(list(self.names), self)

    async def deny(self, ctx):
        if self.access is Access.ADMIN:
            await ctx.reply_key("not_admin")
        else:
            await ctx.reply_key(self.k.access.deny_key, chat_id=ctx.chat_id)


class TextCommand(ChatCommand):
    """Texto libre, solo en privado (en grupos haría saltar al bot con cualquier mensaje)."""

    def handler(self):
        return MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, self)


class ButtonCommand(Command):
    """Botón (callback_data que casa con `pattern`); `ctx.parts` trae los trozos separados por «:»."""
    pattern = ""
    denied_key = "not_authorized"
    auto_answer = True   # responder al botón antes de execute (quita el relojito)

    def handler(self):
        return CallbackQueryHandler(self, pattern=self.pattern)

    async def deny(self, ctx):
        await ctx.alert(ctx.say(self.denied_key))

    async def __call__(self, update, context):
        ctx = Ctx(self.k, update, context)
        ctx.parts = update.callback_query.data.split(":")[1:]
        if not self._allowed(ctx):
            return await self.deny(ctx)
        if self.auto_answer:
            await ctx.query.answer()
        await self.execute(ctx)
