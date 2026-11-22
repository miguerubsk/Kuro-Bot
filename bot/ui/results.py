"""
Resultados de búsqueda como opciones para elegir.

Las temporadas de un mismo anime se marcan (T1, T2…), se ordenan y llevan
detrás un botón para pedirlas todas como un solo encargo. Las películas
llevan 🎬.
"""

import asyncio
from dataclasses import dataclass, field

from telegram import InlineKeyboardMarkup

from ..core.text import season_sort, short
from ..services.japanpaw import clean_title
from .keyboards import button, cancel_row
from .session import ChatSession, Choice, SeasonGroup


@dataclass
class ResultSet:
    choices: list[Choice] = field(default_factory=list)
    groups: dict[int, SeasonGroup] = field(default_factory=dict)

    @property
    def has_groups(self) -> bool:
        return bool(self.groups)

    def keyboard(self) -> InlineKeyboardMarkup:
        """La lista de toda la vida (cuando no hay fichas): un botón por opción."""
        rows = []
        for i, ch in enumerate(self.choices):
            rows.append([button(ch.label, f"pick:{ch.pid}", 60)])
            # el botón de «todas» va detrás de la última temporada del grupo
            next_gid = self.choices[i + 1].gid if i + 1 < len(self.choices) else None
            if ch.gid and next_gid != ch.gid:
                rows.append([button(self.groups[ch.gid].label, f"all:{ch.gid}")])
        rows.append(cancel_row())
        return InlineKeyboardMarkup(rows)


@dataclass
class _Entry:
    result: object
    title: str
    movie: bool
    season: dict | None

    @property
    def key(self):
        return self.season.get("key") if self.season else None


class ResultsBuilder:
    def __init__(self, kuro):
        self.k = kuro

    async def build(self, session: ChatSession, results) -> ResultSet:
        titles = [clean_title(r.title) for r in results]
        kinds, seasons = await asyncio.gather(
            self.k.site.post_kinds([r.post_id for r in results]), self.k.automator.seasons(titles))
        if len(seasons) != len(results):
            seasons = [None] * len(results)

        entries = []
        for r, t, sinfo in zip(results, titles, seasons):
            session.results[r.post_id] = (r.title, r.url)
            entries.append(_Entry(r, t, "pelicula" in kinds.get(r.post_id, set()), sinfo))

        # temporadas del mismo anime (al menos dos temporadas distintas)
        by_key: dict[str, list[_Entry]] = {}
        for en in entries:
            if not en.movie and en.key:
                by_key.setdefault(en.key, []).append(en)
        multi = {k: v for k, v in by_key.items() if len({en.season["season"] for en in v}) >= 2}

        out, done = ResultSet(), set()
        for en in entries:
            if en.key not in multi:
                prefix = "🎬 " if en.movie else ""
                out.choices.append(Choice(en.result.post_id, prefix + en.result.title, None, en.movie))
                continue
            if en.key in done:
                continue
            done.add(en.key)
            gid = session.next_id("group")
            members = sorted(multi[en.key], key=lambda x: season_sort(x.season["season"]))
            out.choices += [Choice(m.result.post_id, f"T{m.season['season']} · {m.result.title}", gid)
                            for m in members]
            group = self._group(members)
            session.groups[gid] = out.groups[gid] = group
        return out

    @staticmethod
    def _group(members: list[_Entry]) -> SeasonGroup:
        # para «todas»: una versión por temporada (la primera que salga)
        per_season = {}
        for m in members:
            per_season.setdefault(m.season["season"], m)
        items = [(m.result.post_id, m.result.title, m.result.url, m.season["season"]) for m in per_season.values()]
        base = members[0].season.get("base") or members[0].title
        label = short(f"📦 Todas: {base} (T{items[0][3]}–T{items[-1][3]}) · 1 encargo")
        return SeasonGroup(base, items, label)
