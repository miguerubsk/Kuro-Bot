"""
Resultados de búsqueda como opciones para elegir.

Las temporadas de un mismo anime se marcan (T1, T2…), se ordenan y llevan
detrás un botón para pedirlas todas como un solo encargo. Sus OVAs,
especiales y películas («Monster Musume no Iru Nichijou OVA», «Gekijouban
Seitokai Yakuindomo») van en el mismo pack, detrás de las temporadas; si
el título no dice de qué serie son («Suzumiya Haruhi no Shoushitsu»), lo
dice AniList (el "series_key" de /seasons). Las películas llevan 🎬.
"""

import asyncio
import re
import unicodedata
from dataclasses import dataclass, field

from telegram import InlineKeyboardMarkup

from ..core.text import season_sort, season_tag, short
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


# palabras que marcan un extra (OVA, especial, película) y las que pueden ir delante del nombre
EXTRA_RE = re.compile(r"\b(?:OVAs?|OADs?|OAVs?|SP|Specials?|Especial(?:es)?|Movie|Film|Gekijou?ban|Pel[ií]cula)\b",
                      re.IGNORECASE)
_LEADING = {"gekijouban", "gekijoban", "eiga", "the"}
_MOVIE_NUMBER_RE = re.compile(r"\b(?:movie|film|gekijou?ban|pel[ií]cula)\s*0*(\d{1,2})\b", re.IGNORECASE)


def _words(text: str) -> list[str]:
    """Palabras comparables: sin tildes ni macrones, y «ou»/«uu» como vocal larga («Nichijou» = «Nichijō»)."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return [re.sub(r"u+", "u", re.sub(r"o[ou]", "o", w)) for w in re.findall(r"[^\W_]+", t)]


def extra_of(base: str, title: str, movie: bool) -> bool:
    """
    ¿Es `title` una OVA, especial o película de la serie `base`? El nombre
    de la serie tiene que ir al principio (como mucho tras «Gekijouban») y,
    detrás, «OVA», «Movie»… (a una película le basta con el nombre y un
    subtítulo aparte: «Kimetsu no Yaiba: Mugen Ressha-hen»). Así ni «Monster
    Musume OVA» ni «Gekijouban Monster Musume» son extras de «Monster».
    """
    bw = _words(base)
    tw = _without_leading(_words(title))
    if not bw or tw[:len(bw)] != bw:
        return False
    rest = tw[len(bw):]
    if rest and EXTRA_RE.match(rest[0]):
        return True
    return movie and _movie_of(bw, title, rest)


def _without_leading(words: list[str]) -> list[str]:
    """Sin lo que puede ir delante del nombre («Gekijouban», «The»…)."""
    i = 0
    while i < len(words) and words[i] in _LEADING:
        i += 1
    return words[i:]


def _movie_of(bw: list[str], title: str, rest: list[str]) -> bool:
    """
    Una película de la serie puede llevar solo el número («… 2»: la película 2)
    o un subtítulo, pero separado: «Kimetsu no Yaiba: Mugen Ressha-hen».
    """
    head = _without_leading(_words(re.split(r":| - | – ", title, maxsplit=1)[0]))
    return not rest or all(w.isdigit() for w in rest) or head == bw


def extra_tag(title: str, movie: bool) -> str:
    """Cómo sale un extra en el pack: «🎬 Película 2», «OVA», «Especial»."""
    if movie:
        m = _MOVIE_NUMBER_RE.search(title)
        return "🎬 Película" + (f" {int(m.group(1))}" if m else "")
    if re.search(r"\b(?:SP|Specials?|Especial(?:es)?)\b", title, re.IGNORECASE):
        return "Especial"
    return "OVA"


def _extra_number(tag: str) -> int:
    m = re.search(r"\d+", tag)
    return int(m.group()) if m else 0


@dataclass
class _Entry:
    result: object
    title: str
    movie: bool
    season: dict | None
    extra: str = ""          # «OVA», «🎬 Película»… si va en el pack de una serie

    @property
    def key(self):
        return self.season.get("key") if self.season else None

    @property
    def series_key(self):
        """La serie de la que es este extra según AniList (aunque el título no la diga)."""
        return self.season.get("series_key") if self.season else None

    @property
    def is_movie(self) -> bool:
        return self.movie or bool(self.season and self.season.get("format") == "MOVIE")

    @property
    def looks_extra(self) -> bool:
        return self.is_movie or bool(EXTRA_RE.search(self.title)) or bool(self.series_key)

    @property
    def tag(self) -> str:
        """Lo que se guarda como «temporada» en el lote: «2» (se ve «T2») o el nombre del extra."""
        return self.extra or self.season["season"]


class ResultsBuilder:
    def __init__(self, kuro):
        self.k = kuro

    async def build(self, session: ChatSession, results) -> ResultSet:
        entries = await self._entries(session, results)
        by_key = _seasons(entries)
        packs = _packs(by_key, _extras(entries, by_key))
        in_pack = {id(en): k for k, v in packs.items() for en in v}

        out, done = ResultSet(), set()
        for en in entries:
            key = in_pack.get(id(en))
            if key is None:
                prefix = "🎬 " if en.movie else ""
                out.choices.append(Choice(en.result.post_id, prefix + en.result.title, None, en.movie))
            elif key not in done:
                done.add(key)
                self._add_pack(session, out, packs[key])
        return out

    async def _entries(self, session: ChatSession, results) -> list[_Entry]:
        """Cada resultado con su tipo (película o no) y lo que sabe Anime-Automator de su temporada."""
        titles = [clean_title(r.title) for r in results]
        kinds, seasons = await asyncio.gather(
            self.k.site.post_kinds([r.post_id for r in results]), self.k.automator.seasons(titles))
        if len(seasons) != len(results):
            seasons = [None] * len(results)
        entries = []
        for r, t, sinfo in zip(results, titles, seasons):
            session.results[r.post_id] = (r.title, r.url)
            entries.append(_Entry(r, t, "pelicula" in kinds.get(r.post_id, set()), sinfo))
        return entries

    def _add_pack(self, session: ChatSession, out: ResultSet, pack: list[_Entry]):
        gid = session.next_id("group")
        # las temporadas en orden y, detrás, los extras (las películas por número)
        members = sorted(pack, key=lambda x: (bool(x.extra), season_sort(x.season["season"])
                                              if not x.extra else _extra_number(x.extra)))
        out.choices += [Choice(m.result.post_id, f"{season_tag(m.tag)} · {m.result.title}", gid, m.movie)
                        for m in members]
        session.groups[gid] = out.groups[gid] = self._group(members)

    @staticmethod
    def _group(members: list[_Entry]) -> SeasonGroup:
        # para «todas»: una versión por temporada (la primera que salga) y cada extra
        per_season = {}
        for m in members:
            per_season.setdefault(m.season["season"] if not m.extra else ("extra", m.result.post_id), m)
        items = [(m.result.post_id, m.result.title, m.result.url, m.tag) for m in per_season.values()]
        seasons = [it[3] for it in items if str(it[3])[:1].isdigit()]
        n_extra = len(items) - len(seasons)
        base = members[0].season.get("base") or members[0].title
        span = f"T{seasons[0]}–T{seasons[-1]}" if len(seasons) > 1 else f"T{seasons[0]}"
        if n_extra:
            span += f" + {n_extra} extra" + ("s" if n_extra > 1 else "")
        label = short(f"📦 Todo: {base} ({span}) · 1 encargo")
        return SeasonGroup(base, items, label)


def _seasons(entries: list[_Entry]) -> dict[str, list[_Entry]]:
    """Las temporadas de cada anime (por la clave de Anime-Automator)."""
    by_key: dict[str, list[_Entry]] = {}
    for en in entries:
        if not en.looks_extra and en.key:
            by_key.setdefault(en.key, []).append(en)
    return by_key


def _extras(entries: list[_Entry], by_key: dict[str, list[_Entry]]) -> dict[str, list[_Entry]]:
    """Las OVAs, especiales y películas de cada anime (cada una con la serie de nombre más largo que case)."""
    bases = sorted(((k, v[0].season.get("base") or v[0].title) for k, v in by_key.items()),
                   key=lambda kb: -len(kb[1]))
    extras: dict[str, list[_Entry]] = {}
    for en in entries:
        if not en.looks_extra or en.key in by_key:
            continue
        # AniList manda («Suzumiya Haruhi no Shoushitsu» es de «… no Yuuutsu»); si no, el título
        match = en.series_key if en.series_key in by_key else next(
            (k for k, base in bases if extra_of(base, en.title, en.is_movie)), None)
        if match:
            en.extra = extra_tag(en.title, en.is_movie)
            extras.setdefault(match, []).append(en)
    return extras


def _packs(by_key: dict[str, list[_Entry]], extras: dict[str, list[_Entry]]) -> dict[str, list[_Entry]]:
    """Un pack: al menos dos temporadas distintas, o una temporada y algún extra."""
    return {k: v + extras.get(k, []) for k, v in by_key.items()
            if len({en.season["season"] for en in v}) >= 2 or extras.get(k)}
