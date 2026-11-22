"""
Personalidad del bot: Kuro (ficha del personaje y frases en lines.py).

Persona es un singleton: guarda estado de todo el proceso (quién es el
miauestro y la última variante usada de cada frase, para no repetirla dos
veces seguidas), así que tiene que haber una sola.

    persona.say("searching", chat_id, query="frieren")

Las plantillas son HTML de Telegram; los valores se escapan solos salvo los
que acaban en "_html". {voc}/{Voc} es cómo llama Kuro a quien lee y {site} un
nombre al azar para la web donde se busca (nunca el de verdad).
"""

import html
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from . import lines as L

try:
    TZ = ZoneInfo(os.environ.get("TZ") or "Europe/Madrid")
except Exception:
    TZ = None


class Persona:
    _instance: "Persona | None" = None

    @classmethod
    def instance(cls) -> "Persona":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, rng: random.Random | None = None):
        self.boss: int | None = None
        self._rng = rng or random.Random()
        self._last_pick: dict[str, str] = {}

    # ---------------------------------------------------------------- piezas
    def set_boss(self, chat_id: int):
        self.boss = chat_id

    def site(self) -> str:
        return self._rng.choice(L.SITE_NAMES)

    def vocative(self, to: int | None) -> str:
        return self._rng.choice(L.BOSS_TITLES if to is not None and to == self.boss else L.CLIENT_TITLES)

    @staticmethod
    def is_night() -> bool:
        return datetime.now(TZ).hour in L.NIGHT_HOURS

    def _pick(self, key: str, night: bool) -> str:
        options = L.LINES[key] + (L.NIGHT_LINES.get(key, []) if night else [])
        if len(options) > 1:
            options = [o for o in options if o != self._last_pick.get(key)]
        choice = self._rng.choice(options)
        self._last_pick[key] = choice
        return choice

    def _aside(self, night: bool) -> str:
        return self._rng.choice(L.ASIDES + (L.NIGHT_ASIDES if night else []))

    # ---------------------------------------------------------------- API
    def say(self, key: str, to: int | None = None, **kw) -> str:
        """Texto de la clave `key` dirigido al chat `to` (para saber si es el admin o no)."""
        values = {k: (html.escape(v) if isinstance(v, str) and not k.endswith("_html") else v)
                  for k, v in kw.items()}
        voc = self.vocative(to)
        values.setdefault("voc", voc)
        values.setdefault("Voc", voc[:1].upper() + voc[1:])
        values.setdefault("site", self.site())
        night = self.is_night()
        text = self._pick(key, night).format(**values)
        if key in L.ASIDE_KEYS and self._rng.random() < L.ASIDE_CHANCE:
            text += f" <i>*{self._aside(night)}*</i>"
        return text

    def to(self, chat_id: int):
        """say() ya dirigido a un chat (así nunca se olvida el destinatario)."""
        return lambda key, **kw: self.say(key, chat_id, **kw)


def say(key: str, to: int | None = None, **kw) -> str:
    return Persona.instance().say(key, to, **kw)


def set_boss(chat_id: int):
    Persona.instance().set_boss(chat_id)
