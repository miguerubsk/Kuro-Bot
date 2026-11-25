"""
Personalidad del bot: Kuro (ficha del personaje y frases en lines.py).

Persona es un singleton: guarda estado de todo el proceso (quién es el
miauestro y las últimas variantes usadas de cada frase, para no repetirlas),
así que tiene que haber una sola.

Para que no suene siempre igual, cada sorteo evita las variantes que han
salido hace poco: la mitad de las de esa clave (como mucho MEMORY). Con
cuatro variantes, no se repite ninguna hasta pasadas dos; con diez, cinco.

    persona.say("searching", chat_id, query="frieren")

Las plantillas son HTML de Telegram; los valores se escapan solos salvo los
que acaban en "_html". {voc}/{Voc} es cómo llama Kuro a quien lee, {site} un
nombre al azar para la web donde se busca (nunca el de verdad) y {example}
un anime al azar para los ejemplos.

Historias: con set_rapport(trust, titles) Kuro sabe cuánta confianza tiene
con cada cliente (0 = ninguna … len(TRUST_STEPS)) y qué se ha bajado, y al
final de algunas frases (STORY_KEYS) cuenta de vez en cuando algo de su vida
o, con el miauestro, una batallita.
"""

import html
import os
import random
import re
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

from . import lines as L

# «de el puerto» -> «del puerto», «a el bazar» -> «al bazar» (los nombres de la web
# y los ejemplos se meten en medio de la frase y pueden empezar por «el»)
_CONTRACTIONS = re.compile(r"\b([Dd]e|[Aa]) el\b")

def _contract(m: re.Match) -> str:
    return m.group(1)[0] + ("el" if m.group(1).lower() == "de" else "l")


try:
    TZ = ZoneInfo(os.environ.get("TZ") or "Europe/Madrid")
except Exception:
    TZ = None


class Persona:
    MEMORY = 6   # cuántas variantes recientes de cada clave se evitan, como mucho
    _instance: "Persona | None" = None

    @classmethod
    def instance(cls) -> "Persona":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, rng: random.Random | None = None):
        self.boss: int | None = None
        self._rng = rng or random.Random()
        self._recent: dict[str, deque] = {}
        self._trust = None    # chat_id -> nivel de confianza
        self._titles = None   # () -> títulos bajados (para las batallitas)

    # ---------------------------------------------------------------- piezas
    def set_boss(self, chat_id: int):
        self.boss = chat_id

    def set_rapport(self, trust, titles):
        self._trust, self._titles = trust, titles

    def site(self) -> str:
        return self._rng.choice(L.SITE_NAMES)

    def example(self) -> str:
        """Un anime de ejemplo, sin repetir los que han salido hace poco."""
        return self._fresh("__example__", L.EXAMPLE_TITLES)

    def vocative(self, to: int | None) -> str:
        return self._rng.choice(L.BOSS_TITLES if to is not None and to == self.boss else L.CLIENT_TITLES)

    @staticmethod
    def is_night() -> bool:
        return datetime.now(TZ).hour in L.NIGHT_HOURS

    def _fresh(self, key: str, options: list[str]) -> str:
        """Una variante al azar entre las que no han salido hace poco."""
        recent = self._recent.setdefault(key, deque(maxlen=self.MEMORY))
        avoid = list(recent)[-min(len(options) // 2, self.MEMORY):] if len(options) > 1 else []
        choice = self._rng.choice([o for o in options if o not in avoid] or options)
        recent.append(choice)
        return choice

    def _pick(self, key: str, night: bool) -> str:
        return self._fresh(key, L.LINES[key] + (L.NIGHT_LINES.get(key, []) if night else []))

    def _aside(self, night: bool) -> str:
        return self._fresh("__aside__", L.ASIDES + (L.NIGHT_ASIDES if night else []))

    def _story(self, to: int, voc: str) -> str:
        """Un trozo de su vida (a un cliente, según la confianza) o una batallita (al miauestro), o nada."""
        if self._trust is None:
            return ""
        values = {"voc": voc, "Voc": voc[:1].upper() + voc[1:], "site": self.site()}
        picked = self._battle(values) if to == self.boss else self._lore(to)
        if picked is None:
            return ""
        text, icon = picked
        return f"\n\n{icon} <i>{_CONTRACTIONS.sub(_contract, text.format(**values))}</i>"

    def _battle(self, values: dict) -> tuple[str, str] | None:
        """Una batallita para el miauestro (a veces con un anime de verdad de los bajados), o nada."""
        if self._rng.random() >= L.BATTLE_CHANCE:
            return None
        titles = self._titles() if self._titles else []
        pool = [b for b in L.BATTLES if titles or "{title}" not in b]
        values["title"] = html.escape(self._rng.choice(titles)) if titles else ""
        return self._fresh("__battle__", pool), "🍖"

    def _lore(self, to: int) -> tuple[str, str] | None:
        """Un trozo de su vida, según la confianza con ese cliente, o nada."""
        level = min(self._trust(to), len(L.LORE))
        if level <= 0 or self._rng.random() >= L.LORE_CHANCE[level - 1]:
            return None
        # cada cliente tiene su memoria: no se le repite lo que le contó hace poco
        return self._fresh(f"__lore__:{to}", [x for lv in L.LORE[:level] for x in lv]), "🐾"

    # ---------------------------------------------------------------- API
    def say(self, key: str, to: int | None = None, **kw) -> str:
        """Texto de la clave `key` dirigido al chat `to` (para saber si es el admin o no)."""
        values = {k: (html.escape(v) if isinstance(v, str) and not k.endswith("_html") else v)
                  for k, v in kw.items()}
        night = self.is_night()
        template = self._pick(key, night)
        voc = self.vocative(to)
        values.setdefault("voc", voc)
        values.setdefault("Voc", voc[:1].upper() + voc[1:])
        values.setdefault("site", self.site())
        if "{example}" in template:
            values.setdefault("example", html.escape(self.example()))
        text = _CONTRACTIONS.sub(_contract, template.format(**values))
        if key in L.ASIDE_KEYS and self._rng.random() < L.ASIDE_CHANCE:
            text += f" <i>*{self._aside(night)}*</i>"
        if to is not None and key in L.STORY_KEYS:
            text += self._story(to, voc)
        return text

    def to(self, chat_id: int):
        """say() ya dirigido a un chat (así nunca se olvida el destinatario)."""
        return lambda key, **kw: self.say(key, chat_id, **kw)


def say(key: str, to: int | None = None, **kw) -> str:
    return Persona.instance().say(key, to, **kw)


def set_boss(chat_id: int):
    Persona.instance().set_boss(chat_id)
