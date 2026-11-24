"""Pequeñas utilidades de texto que usa todo el bot."""

import html
import re
from datetime import datetime

e = html.escape


def compress_ranges(numbers) -> str:
    """[1,2,3,5,7,8] -> '1-3, 5, 7-8'"""
    nums = sorted(set(numbers))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"{nums[i]}" if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(out)


def short(text: str, n: int = 60) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def first_name(user_name: str) -> str:
    """«Ana (@ana) en «Grupo»» -> «Ana»."""
    return (user_name or "").split(" (")[0].strip() or user_name or "?"


def fmt_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m a las %H:%M")


def fmt_day(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%y")


def plain(html_text: str) -> str:
    """HTML de Telegram -> texto plano (para las alertas de los botones, que no admiten HTML)."""
    return html.unescape(re.sub(r"<[^>]+>", "", html_text))


def season_tag(season) -> str:
    """«T2» para una temporada; los extras del pack ya traen su nombre («OVA», «🎬 Película»)."""
    s = str(season or "").strip()
    return f"T{s}" if s[:1].isdigit() else s


def season_sort(season) -> float:
    try:
        return float(season)
    except (TypeError, ValueError):
        return 99.0
