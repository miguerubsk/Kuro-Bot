"""
Dónde ir contando cómo va un encargo (patrón estrategia):

- EditInPlace: en la propia lista de resultados (se edita el mensaje).
- ReplyBelowCard: si se eligió desde una ficha con portada, en un mensaje
  nuevo debajo (la ficha se queda sin botones, como recuerdo de lo pedido).

Las dos se usan igual: `await out.edit(texto, ...)`.
"""

from abc import ABC, abstractmethod

from telegram.constants import ParseMode
from telegram.error import BadRequest


class Progress(ABC):
    def __init__(self, query):
        self.q = query

    @classmethod
    def for_query(cls, query) -> "Progress":
        return ReplyBelowCard(query) if query.message.photo else EditInPlace(query)

    @abstractmethod
    async def _edit(self, text: str, **kw): ...

    async def edit(self, text: str, **kw):
        kw.setdefault("parse_mode", ParseMode.HTML)
        return await self._edit(text, **kw)


class EditInPlace(Progress):
    async def _edit(self, text, **kw):
        return await self.q.edit_message_text(text, **kw)


class ReplyBelowCard(Progress):
    def __init__(self, query):
        super().__init__(query)
        self.msg = None

    async def _edit(self, text, **kw):
        if self.msg is not None:
            return await self.msg.edit_text(text, **kw)
        try:
            await self.q.edit_message_reply_markup(None)
        except BadRequest:
            pass
        self.msg = await self.q.message.reply_text(text, **kw)
        return self.msg
