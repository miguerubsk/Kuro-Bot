"""Lo que se recuerda de cada chat entre botón y botón (en memoria: se pierde al reiniciar)."""

from dataclasses import dataclass, field


@dataclass
class Choice:
    """Una opción de los resultados de búsqueda."""
    pid: int
    label: str
    gid: int | None = None   # grupo de temporadas al que pertenece
    movie: bool = False


@dataclass
class SeasonGroup:
    """Temporadas de un mismo anime, para pedirlas todas como un solo encargo."""
    base: str
    items: list[tuple[int, str, str, str]]   # (post_id, título, url, temporada)
    label: str


@dataclass
class Deck:
    """Fichas con portada de una búsqueda."""
    items: list[Choice]
    details: dict
    groups: dict[int, SeasonGroup] = field(default_factory=dict)


class ChatSession:
    KEEP_DECKS = 5   # solo las últimas búsquedas

    def __init__(self, chat_data: dict):
        self._d = chat_data

    def _bucket(self, name: str) -> dict:
        return self._d.setdefault(name, {})

    def next_id(self, name: str) -> int:
        key = f"next_{name}"
        n = self._d.get(key, 1)
        self._d[key] = n + 1
        return n

    @property
    def results(self) -> dict[int, tuple[str, str]]:
        """post_id -> (título, url)"""
        return self._bucket("results")

    @property
    def groups(self) -> dict[int, SeasonGroup]:
        return self._bucket("groups")

    @property
    def decks(self) -> dict[int, Deck]:
        return self._bucket("cards")

    def add_deck(self, deck: Deck) -> int:
        cid = self.next_id("card")
        for old in [k for k in self.decks if k <= cid - self.KEEP_DECKS]:
            self.decks.pop(old, None)
        self.decks[cid] = deck
        return cid
