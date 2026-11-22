"""
Decisiones del admin como órdenes (patrón orden / command).

Cada botón de aprobar/rechazar lleva en su callback_data una orden
serializada («ok:12», «bno:3»…). `decode` la convierte en un objeto
ApproveOrder/RejectOrder sobre el Target que toque, y `execute` la ejecuta.
Añadir una decisión nueva es añadir una clase y una entrada en ACTIONS.
"""

from abc import ABC, abstractmethod

from telegram.constants import ParseMode

from ..core.models import Status
from ..core.text import plain
from .targets import BundleTarget, SingleTarget, Target

HTML = ParseMode.HTML


class OrderCommand(ABC):
    def __init__(self, kuro, target: Target):
        self.k = kuro
        self.target = target

    @abstractmethod
    async def execute(self, query): ...

    # ---------------------------------------------------------- comunes
    def _say(self, key, **kw):
        return self.k.persona.say(key, self.k.admin, **kw)

    def _claim(self, to_state: str) -> list:
        """Las peticiones que siguen abiertas, ya pasadas a to_state (evita dobles decisiones)."""
        return [r for r in self.target.open_requests() if self.k.db.transition(r.id, Status.OPEN, to_state)]

    async def _already_decided(self, query):
        status = self.k.db.get(self.target.reqs[0].id).status
        await query.answer(plain(self._say("already_decided", status=status)), show_alert=True)

    async def _show(self, query, text: str, **kw):
        # la cabecera se sortea una vez: no cambia de frase entre «enviando» y el resultado
        if not hasattr(self, "_head"):
            self._head = self.target.admin_text()
        await query.edit_message_text(self._head + "\n\n" + text, parse_mode=HTML,
                                      disable_web_page_preview=True, **kw)


class RejectOrder(OrderCommand):
    async def execute(self, query):
        if not self._claim(Status.REJECTED):
            return await self._already_decided(query)
        await query.answer(self.target.rejected_answer)
        await self._show(query, self._say("admin_rejected"))
        to = self.target.chat_id
        await self.k.messenger.send(to, self.k.persona.say(self.target.rejected_key, to, title=self.target.name))


class ApproveOrder(OrderCommand):
    async def execute(self, query):
        t = self.target
        first_try = any(r.status == Status.PENDING for r in t.open_requests())
        claimed = self._claim(Status.PROCESSING)
        if not claimed:
            return await self._already_decided(query)
        await query.answer("Marchando…")
        await self._show(query, self._say("admin_sending"))

        results = [(r, await self.k.dispatcher.dispatch(self.k.db.get(r.id))) for r in claimed]
        failed = any(not res.ok for _, res in results)
        await self._show(query, t.approved_report(results), reply_markup=t.keyboard(retry=True) if failed else None)
        # en los reintentos no se repite el aviso de lo que vuelve a fallar
        user_parts = [t.tag(r) + res.user_text for r, res in results if res.ok or first_try]
        if user_parts:
            await self.k.messenger.send(t.chat_id, "\n\n".join(user_parts))


# prefijo de callback_data -> (qué se decide, qué se hace)
ACTIONS: dict[str, tuple[type[Target], type[OrderCommand]]] = {
    "ok": (SingleTarget, ApproveOrder),
    "no": (SingleTarget, RejectOrder),
    "bok": (BundleTarget, ApproveOrder),
    "bno": (BundleTarget, RejectOrder),
}
PATTERN = rf"^({'|'.join(ACTIONS)}):\d+$"


def decode(kuro, data: str) -> tuple[OrderCommand | None, str]:
    """(orden, texto si ya no existe) a partir de «ok:12»."""
    action, raw_id = data.split(":", 1)
    target_cls, command_cls = ACTIONS[action]
    target = target_cls.load(kuro, int(raw_id))
    return (command_cls(kuro, target) if target else None), target_cls.missing_text
