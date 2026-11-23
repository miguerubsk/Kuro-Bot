"""
Lo que se encarga y el admin aprueba o rechaza: una petición suelta o un
lote («todas las temporadas»). Las dos clases se usan igual, así que la
misma orden de aprobar/rechazar sirve para ambas (Liskov).
"""

import re
from abc import ABC, abstractmethod

from telegram import InlineKeyboardMarkup

from ..core.models import Status
from ..core.text import e
from ..ui.keyboards import season_row, yes_no
from .dispatcher import Outcome

# corregir la temporada de un encargo por torrent sin decidir (no cambiarlo: botones viejos)
TORRENT_SEASON = "trs"


class Target(ABC):
    # prefijos de callback_data (no cambiarlos: los botones viejos de los chats los usan)
    approve_action: str
    reject_action: str
    approve_label: str
    retry_label: str
    reject_label = "❌ Ni hablar"
    rejected_answer: str     # texto corto del aviso al pulsar rechazar
    rejected_key: str        # frase para quien lo pidió
    missing_text: str        # si ya no existe

    def __init__(self, kuro, reqs: list):
        self.k = kuro
        self.reqs = reqs

    @classmethod
    @abstractmethod
    def load(cls, kuro, ident: int) -> "Target | None": ...

    @property
    @abstractmethod
    def ident(self) -> int: ...

    @property
    def chat_id(self) -> int:
        return self.reqs[0].chat_id

    @property
    @abstractmethod
    def name(self) -> str:
        """Cómo se llama lo pedido en los mensajes al cliente."""

    @abstractmethod
    def admin_text(self) -> str: ...

    def tag(self, req) -> str:
        """Prefijo de cada petición en los mensajes (la temporada en los lotes)."""
        return ""

    @abstractmethod
    def approved_report(self, results: list[tuple[object, Outcome]]) -> str:
        """Texto para el admin tras aprobar (debajo de admin_text)."""

    @abstractmethod
    def direct_report(self, results: list[tuple[object, Outcome]]) -> str:
        """Texto para el admin cuando el encargo es suyo y va directo."""

    def open_requests(self) -> list:
        return [r for r in self.reqs if r.status in Status.OPEN]

    def keyboard(self, retry: bool = False) -> InlineKeyboardMarkup:
        return yes_no(self.retry_label if retry else self.approve_label, f"{self.approve_action}:{self.ident}",
                      self.reject_label, f"{self.reject_action}:{self.ident}")

    def remember_admin_msg(self, msg_id: int):
        for r in self.reqs:
            self.k.db.set_admin_msg(r.id, msg_id)


class SingleTarget(Target):
    approve_action, reject_action = "ok", "no"
    approve_label, retry_label = "✅ Adelante, nya", "🔁 Reintentar"
    rejected_answer, rejected_key = "Rechazada", "rejected"
    missing_text = "Esa petición ya no existe."

    @classmethod
    def load(cls, kuro, ident):
        req = kuro.db.get(ident)
        return cls(kuro, [req]) if req else None

    @property
    def req(self):
        return self.reqs[0]

    @property
    def ident(self):
        return self.req.id

    @property
    def name(self):
        return self.req.title

    def admin_text(self):
        return self.k.texts.admin_request(self.req) + self.k.memo.notes.get(self.req.id, "")

    def keyboard(self, retry: bool = False) -> InlineKeyboardMarkup:
        kb = super().keyboard(retry)
        if not self.req.torrent:
            return kb
        return InlineKeyboardMarkup([*kb.inline_keyboard, season_row(TORRENT_SEASON, self.req.id, self.req.season)])

    def approved_report(self, results):
        (_, res), = results
        if res.ok:
            return self.k.persona.say("admin_approved", self.k.admin) + "\n" + res.admin_text
        return res.admin_text

    def direct_report(self, results):
        (_, res), = results
        return res.user_text + "\n\n" + res.admin_text


class BundleTarget(Target):
    approve_action, reject_action = "bok", "bno"
    approve_label, retry_label = "✅ Todas, nya", "🔁 Reintentar las fallidas"
    rejected_answer, rejected_key = "Rechazado", "bundle_rejected"
    missing_text = "Ese lote ya no existe."

    @classmethod
    def load(cls, kuro, ident):
        reqs = kuro.db.bundle(ident)
        return cls(kuro, reqs) if reqs else None

    @property
    def ident(self):
        return self.reqs[0].bundle_id

    @property
    def name(self):
        first = self.reqs[0].title
        return self.k.memo.bundle_names.get(self.ident) or re.sub(r":.*$", "", first).strip() or first

    def admin_text(self):
        return self.k.texts.admin_bundle(self.reqs, self.k.memo.notes, self.k.memo.seasons)

    def tag(self, req):
        t = self.k.memo.seasons.get(req.id)
        return f"<b>T{e(t)}</b> · " if t else ""

    def approved_report(self, results):
        return (self.k.persona.say("admin_approved", self.k.admin) + "\n"
                + "\n".join(self.tag(r) + res.admin_text for r, res in results))

    def direct_report(self, results):
        return "\n\n".join(f"{self.tag(r)}{res.user_text}\n{res.admin_text}" for r, res in results)
