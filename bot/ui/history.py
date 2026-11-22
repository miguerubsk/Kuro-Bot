"""/descargados: lo que ha pedido cada uno (solo el admin)."""

from telegram import InlineKeyboardMarkup

from ..core.models import Status
from ..core.text import e, first_name, fmt_day
from ..services.japanpaw import clean_title
from .keyboards import button, in_pairs, pager_row

PAGE = 30


def _tier(n: int) -> str:
    """Cómo de buen cliente es (cada nivel tiene sus frases)."""
    return "waiting" if n == 0 else "one" if n == 1 else "few" if n <= 5 else "many"


def _line(r) -> str:
    partial = f" <i>(⚠️ {r.eps_failed} cap. sin bajar)</i>" if r.eps_failed else ""
    movie = " 🎬" if r.movie else ""
    return f"• {e(clean_title(r.title))}{movie} <i>— {fmt_day(r.created_at)}</i>{partial}"


class HistoryView:
    def __init__(self, kuro):
        self.k = kuro

    def _head(self, target: int, hist, done, name: str) -> str:
        say = self.k.persona.to(self.k.admin)
        if target == self.k.admin:
            return say("history_mine", count=len(done)) if hist else say("history_empty_mine")
        if not hist:
            return say("history_empty_client", who=name)
        return say(f"history_client_{_tier(len(done))}", who=name, count=len(done))

    def render(self, target: int, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
        admin = self.k.admin
        hist = self.k.db.history(target)
        done = [r for r in hist if r.status == Status.COMPLETED]
        going = [r for r in hist if r.status != Status.COMPLETED]
        names = dict(self.k.db.requesters())
        head = self._head(target, hist, done, first_name(names.get(target, "")) if target != admin else "")

        lines = [_line(r) for r in done]
        if going:
            lines += ["", self.k.persona.say("history_in_progress", admin)] + [_line(r) for r in going]
        pages = max(1, -(-len(lines) // PAGE))
        page = min(max(page, 0), pages - 1)
        body = "\n".join(lines[page * PAGE:(page + 1) * PAGE]).strip("\n")
        text = head + ("\n\n" + body if body else "")

        rows = [pager_row(lambda p: f"hist:{target}:{p}", page, pages)] if pages > 1 else []
        people = [(admin, "🐾 Los míos")] + [(cid, first_name(n)) for cid, n in names.items() if cid != admin]
        rows += in_pairs([button(f"· {label} ·" if cid == target else label, f"hist:{cid}:0", 30)
                          for cid, label in people])
        return text, InlineKeyboardMarkup(rows)
