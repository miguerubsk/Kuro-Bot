"""Piezas de teclado que se repiten (paginadores, sí/no, cancelar)."""

from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..core.text import short

NOOP = "noop"


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
