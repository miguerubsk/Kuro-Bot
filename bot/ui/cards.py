"""Fichas para elegir: portada + sinopsis, una a una (◀️ ▶️)."""

import struct
import zlib

from telegram import InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import BadRequest

from ..core.text import e
from ..services.japanpaw import Details
from .keyboards import button, cancel_row, pager_row
from .session import ChatSession, Choice, Deck

CAPTION_MAX = 1000  # Telegram corta en 1024
PLACEHOLDER = "placeholder"


def _placeholder_png() -> bytes:
    """Portada de repuesto (gris oscuro) para las fichas que no traen."""
    w, h = 230, 340
    raw = b"".join(b"\x00" + b"\x2b\x2b\x33" * w for _ in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


class CoverCache:
    """
    Portadas ya subidas a Telegram (url -> file_id), para no volver a
    descargarlas ni subirlas al pasar de ficha.
    """
    MAX = 2000

    def __init__(self, site):
        self.site = site
        self.file_ids: dict[str, str] = {}

    async def photo(self, d: Details | None) -> tuple[str, object]:
        """(clave, file_id o bytes) de la portada; si no hay, la de repuesto."""
        url = (d.cover_url if d else "") or PLACEHOLDER
        if url in self.file_ids:
            return url, self.file_ids[url]
        data = await self.site.cover_bytes(url) if url != PLACEHOLDER else None
        if data is None:
            url = PLACEHOLDER
            data = self.file_ids.get(url) or _placeholder_png()
        return url, data

    def remember(self, url: str, msg):
        if msg is not None and getattr(msg, "photo", None):
            if len(self.file_ids) > self.MAX:
                self.file_ids.clear()
            self.file_ids[url] = msg.photo[-1].file_id


def caption(choice: Choice, d: Details) -> str:
    facts = []
    eps = (d.episodes or "").strip()
    if "emisi" in eps.lower():
        facts.append("📡 en emisión")
    elif eps.isdigit() and not (choice.movie and eps == "1"):
        facts.append(f"{eps} caps.")
    facts += [x for x in (d.season or d.premiere[:4], d.video) if x]

    head, plain_len = f"<b>{e(choice.label)}</b>", len(choice.label)
    for extra in (" · ".join(facts), d.genres):
        if extra:
            head += f"\n<i>{e(extra)}</i>"
            plain_len += 1 + len(extra)
    syn = d.synopsis or "(Sin sinopsis, nya. Habrá que fiarse del título.)"
    room = CAPTION_MAX - plain_len - 2
    if len(syn) > room:
        syn = syn[: max(room - 1, 0)].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return f"{head}\n\n{e(syn)}"


def keyboard(cid: int, idx: int, deck: Deck) -> InlineKeyboardMarkup:
    n = len(deck.items)
    ch = deck.items[idx]
    rows = []
    if n > 1:
        rows.append(pager_row(lambda i: f"card:{cid}:{i}", idx, n))
    if n > 3:
        rows.append([button(f"·{i + 1}·" if i == idx else str(i + 1), f"card:{cid}:{i}") for i in range(n)])
    rows.append([button("✅ Pedir este", f"pick:{ch.pid}")])
    group = deck.groups.get(ch.gid) if ch.gid else None
    if group:
        rows.append([button(group.label, f"all:{ch.gid}")])
    rows.append(cancel_row())
    return InlineKeyboardMarkup(rows)


class CardDeck:
    def __init__(self, covers: CoverCache):
        self.covers = covers

    async def _render(self, deck: Deck, cid: int, idx: int):
        ch = deck.items[idx]
        d = deck.details.get(ch.pid) or Details()
        url, photo = await self.covers.photo(d)
        return url, photo, caption(ch, d), keyboard(cid, idx, deck)

    async def send(self, bot, chat_id: int, session: ChatSession, choices: list[Choice], details: dict):
        deck = Deck(choices, details, session.groups)
        cid = session.add_deck(deck)
        url, photo, text, kb = await self._render(deck, cid, 0)
        msg = await bot.send_photo(chat_id, photo, caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        self.covers.remember(url, msg)

    async def show(self, query, deck: Deck, cid: int, idx: int):
        url, photo, text, kb = await self._render(deck, cid, idx)
        try:
            msg = await query.edit_message_media(InputMediaPhoto(photo, caption=text, parse_mode=ParseMode.HTML),
                                                 reply_markup=kb)
            self.covers.remember(url, msg if hasattr(msg, "photo") else None)
        except BadRequest as ex:
            if "not modified" not in str(ex).lower():
                raise
