"""Piezas de teclado que se repiten (paginadores, sí/no, cancelar)."""

from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..core.text import short

NOOP = "noop"
# encargos por torrent (no cambiarlos: los botones viejos de los chats los usan):
# ver qué hay de uno, de todas sus temporadas, pedirlo y pedirlas todas
TORRENT_OFFER, TORRENT_ALL, TORRENT_GO, TORRENT_GO_ALL = "trt", "tra", "trg", "trb"


def button(text: str, data: str, width: int | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(short(text, width) if width else text, callback_data=data)


def cancel_row() -> list[InlineKeyboardButton]:
    return [button("✖️ Cancelar", "cancel")]


def pager_row(data_for: Callable[[int], str], idx: int, n: int) -> list[InlineKeyboardButton]:
    """◀️ i / n ▶️ (da la vuelta en los extremos)."""
    return [button("◀️", data_for((idx - 1) % n)),
            button(f"{idx + 1} / {n}", NOOP),
            button("▶️", data_for((idx + 1) % n))]


def yes_no(yes_label: str, yes_data: str, no_label: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button(yes_label, yes_data), button(no_label, no_data)]])


def in_pairs(buttons: list) -> list[list]:
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def shift_season(season: str, delta: int) -> str:
    """La temporada de al lado ("2" + 1 -> "3"; "1.5" - 1 -> "1"), nunca menos de 1."""
    try:
        n = int(float(season or 1))
    except ValueError:
        n = 1
    return str(max(1, n + delta))


def season_row(prefix: str, ident: int, season: str) -> list[InlineKeyboardButton]:
    """◀️ T1 · T3 ▶️ para corregir la temporada (solo el admin): «prefijo:ident:temporada»."""
    lower, upper = shift_season(season, -1), shift_season(season, 1)
    row = [] if lower == season else [button(f"◀️ T{lower}", f"{prefix}:{ident}:{lower}")]
    return row + [button(f"T{upper} ▶️", f"{prefix}:{ident}:{upper}")]
