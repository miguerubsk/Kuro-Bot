"""
Animes que los clientes no pueden pedir (BLOCKED_ANIME; por defecto One Piece
y Naruto: son enormes). Se compara sin mayúsculas, espacios ni signos, y
basta con que el título lo contenga: «Naruto: Shippuuden», «One Piece Film:
Red» o «Boruto: Naruto Next Generations» también quedan fuera.
"""

import re
import unicodedata

DEFAULT = ("One Piece", "Naruto")


def _key(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return re.sub(r"[\W_]+", "", t)


class Blocklist:
    def __init__(self, names=DEFAULT):
        self.names = tuple(n.strip() for n in names if n and n.strip())
        self._keys = tuple(k for k in (_key(n) for n in self.names) if len(k) >= 3)

    def matches(self, *titles: str) -> bool:
        return any(k in _key(t) for t in titles if t for k in self._keys)


def parse(raw: str | None) -> tuple[str, ...]:
    """«One Piece, Naruto» -> ("One Piece", "Naruto"); sin definir, los de siempre; vacío, ninguno."""
    if raw is None:
        return DEFAULT
    return tuple(n.strip() for n in raw.split(",") if n.strip())
