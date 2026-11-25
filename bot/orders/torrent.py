"""
Encargos por torrent: lo que no está en la web se busca por AniList y se
baja por torrent (Anime-Automator elige los releases: Erai-raws primero y
nunca sin subtítulos en español).

Los pasos para quien pide:
1. La búsqueda no encuentra nada: Kuro ofrece las opciones de AniList.
2. Elige una: Kuro pregunta a Anime-Automator qué hay (TorrentOffer) y lo
   cuenta. El admin puede cambiar la temporada antes de confirmar.
3. Confirma: TorrentPlacing hace el encargo como cualquier otro (carro,
   visto bueno del admin, avisos de progreso).

«Todo» (TorrentSeasons y TorrentBundlePlacing) sigue la cadena de precuelas
y secuelas de AniList (temporadas, OVAs, especiales y películas), mira cada
cosa y lo pide como un solo lote, igual que el «todas» de la web.
"""

from dataclasses import dataclass

from telegram import InlineKeyboardMarkup

from ..core.text import compress_ranges, e, season_tag
from ..ui.keyboards import TORRENT_ALL as ALL, TORRENT_GO as GO, TORRENT_GO_ALL as GO_ALL
from ..ui.keyboards import TORRENT_OFFER as OFFER, button, cancel_row, season_row
from ..ui.session import SeasonGroup
from .library import Assessment
from .placing import BundlePlacing, Item, Placing
from .targets import TORRENT_SEASON as SEASON, SingleTarget


@dataclass
class TorrentPost:
    """Lo que se guarda como petición (hace el papel del PostInfo de la web)."""
    anilist_id: int
    title: str
    season: str                 # la de Anime-Automator; "" en los extras (no se le corrige)
    airing: bool = False
    movie: bool = False
    tag: str = ""               # «OVA», «🎬 Película»… en los extras del pack
    source = "torrent"
    paste_url = ""

    @property
    def post_id(self) -> int:
        # negativo: nunca choca con los posts de la web (sirve para «ya lo tienes pedido»)
        return -self.anilist_id

    @property
    def url(self) -> str:
        return f"https://anilist.co/anime/{self.anilist_id}"

    @property
    def label(self) -> str:
        return self.tag or (f"T{self.season}" if self.season else "")


def admin_note(result: dict) -> str:
    """Lo que ve el admin al decidir (HTML)."""
    groups = result.get("groups") or {}
    txt = f"\n🧲 Por torrent: {compress_ranges(result.get('missing') or [])}"
    if groups:
        txt += " · " + ", ".join(f"{e(g)} ×{n}" for g, n in sorted(groups.items(), key=lambda x: -x[1]))
    if result.get("have"):
        txt += f"\n📚 En biblioteca: {result['have']} — <b>no gasta cupo</b>"
    if result.get("folder"):
        txt += f"\nCarpeta: <code>{e(result['folder'])}</code>"
    return txt


def _option_flags(option) -> tuple[str, bool, bool]:
    """(etiqueta de extra, ¿película?, ¿en emisión?) de la opción de AniList (sin opción, nada de eso)."""
    if not option:
        return "", False, False
    return option.tag, bool(option.movie), bool(option.releasing)


def offer_entry(anilist_id: int, result: dict, name: str, option) -> dict:
    """Lo que se recuerda de una oferta (en la sesión) hasta que se pide."""
    tag, movie, releasing = _option_flags(option)
    movie = movie or result.get("kind") == "movie"
    # a los extras no se les fija temporada: Anime-Automator los coloca como los de la web
    season = "" if tag or movie else str(result.get("season") or "1")
    return {"anilist_id": anilist_id, "name": name, "season": season, "tag": tag, "movie": movie,
            "missing": result.get("missing") or [], "airing": releasing and not movie,
            "have": result.get("have") or 0, "note": admin_note(result)}


def library_of(offer: dict) -> Assessment:
    """Si ya tenemos parte, completarlo no gasta cupo (como los encargos de la web)."""
    return Assessment(exempt=bool(offer.get("have")))


def post_of(offer: dict) -> TorrentPost:
    return TorrentPost(offer["anilist_id"], offer["name"], offer["season"], offer["airing"],
                       offer.get("movie", False), offer.get("tag", ""))


def is_best(result: dict) -> bool:
    found = result.get("found") or []
    return bool(found) and result.get("preferred", 0) >= len(found)


class _Step:
    """Un paso de la conversación de un chat (con su sesión)."""

    def __init__(self, kuro, chat_id: int, session):
        self.k = kuro
        self.chat_id = chat_id
        self.say = kuro.persona.to(chat_id)
        self.session = session


class TorrentOffer(_Step):
    """Paso 2: qué hay por torrent de un anime de AniList, y el botón para pedirlo."""

    @property
    def cache(self):
        return self.session.torrent

    async def show(self, out, anilist_id: int, season: str | None = None):
        option = await self.k.catalog.option(anilist_id)
        title = option.title if option else "…"
        await out.edit(self.say("torrent_searching", title=title))
        result = await self.k.automator.torrent_check(anilist_id, season)
        st = result.get("status")
        name = result.get("name") or title
        if st == "missing":
            text, kb = self._offer(anilist_id, result, name, option)
            return await out.edit(text, reply_markup=kb)
        if st == "nothing_new":
            return await out.edit(self.say("library_complete", title=name, have=result.get("have", "?")))
        if st == "in_progress":
            return await out.edit(self.say("library_busy", title=name))
        if st == "nothing_found":
            return await out.edit(self.say("torrent_none", title=name))
        if st == "unsupported":
            return await out.edit(self.say("torrent_movie"))
        await out.edit(self.say("torrent_error"))

    def _offer(self, anilist_id: int, result: dict, name: str, option):
        entry = offer_entry(anilist_id, result, name, option)
        season = str(result.get("season") or "1")
        self.cache[f"{anilist_id}:{season}"] = entry
        parts = self._offer_parts(entry, result, name, season)
        rows = [[button("🧲 Tráelo, nya", f"{GO}:{anilist_id}:{season}")]]
        # el miauestro puede corregir la temporada (los extras y las películas no llevan)
        if self.k.is_admin(self.chat_id) and not entry["tag"] and not entry["movie"]:
            parts.append(self.say("torrent_season_hint"))
            rows.append(season_row(OFFER, anilist_id, season))
        rows.append(cancel_row())
        return "\n\n".join(parts), InlineKeyboardMarkup(rows)

    def _offer_parts(self, entry: dict, result: dict, name: str, season: str) -> list[str]:
        """Qué hay (y qué tiene ya) y la calidad."""
        if entry["movie"]:
            parts = [self.say("torrent_offer_movie", title=name)]
        else:
            missing = entry["missing"]
            parts = [self.say("torrent_offer", title=name, tag=entry["tag"] or f"T{season}", count=len(missing),
                              ranges=compress_ranges(missing))]
            if result.get("have"):
                parts.append(self.say("torrent_have", have=result["have"]))
        parts.append(self.say("torrent_quality_best" if is_best(result) else "torrent_quality_mixed"))
        return parts


class TorrentPlacing(Placing):
    """Paso 3: el encargo (carro, visto bueno del admin…), como el de un post de la web."""

    def __init__(self, kuro, submitter, out, anilist_id: int, season: str, session):
        super().__init__(kuro, submitter, out)
        self.anilist_id = anilist_id
        self.season = season
        self.offer = session.torrent.get(f"{anilist_id}:{season}")
        self.post: TorrentPost | None = None

    @property
    def title(self):
        return self.post.title if self.post else ""

    async def collect(self):
        if not self.offer:
            await self.stop("expired")
        prev = self.sub.already_active(-self.anilist_id)
        if prev:
            await self.stop("already_pending", title=prev.title)
        # la temporada puede venir corregida por el admin (flechas)
        self.post = post_of({**self.offer, "season": self.season if self.offer["season"] else ""})
        return [Item(self.post, check=library_of(self.offer))]

    def store(self, items):
        rid = self._add(items[0])
        self.k.memo.notes[rid] = self.offer["note"]
        return SingleTarget(self.k, [self.k.db.get(rid)])

    def sending_label(self, target):
        return self.k.texts.post_label(self.post)

    def sent_text(self, target):
        return (self.say("sent_to_admin", title=self.post.title, label=self.k.texts.post_label(self.post),
                         **self._left())
                + "\n\n" + self.say("torrent_slow"))


class TorrentSeasons(_Step):
    """Paso 2 de «todo»: qué hay de cada temporada, OVA o película, y el botón para pedirlo como un encargo."""

    STATE = {"nothing_new": "✅ ya la tienes", "in_progress": "⏳ ya se está bajando",
             "nothing_found": "✖️ nada con subtítulos en español", "unsupported": "✖️ no se puede pedir así"}

    async def show(self, out, anilist_id: int):
        start = await self.k.catalog.option(anilist_id)
        title = start.title if start else "…"
        await out.edit(self.say("torrent_seasons_searching", title=title))
        chain = await self.k.catalog.pack(anilist_id)
        if len(chain) < 2:   # al final solo hay una cosa: como la de siempre
            return await TorrentOffer(self.k, self.chat_id, self.session).show(out, anilist_id)
        checks = [await self._check(opt) for opt in chain]
        # el nombre del pack: el de la primera temporada (los extras no cuentan)
        base = next((c.name for c in checks if c.name), "") or chain[0].title
        lines = "\n".join(c.line for c in checks)
        offers = [c.offer for c in checks if c.offer]
        if not offers:
            states = {c.status for c in checks}
            key = "bundle_all_have" if states <= {"nothing_new", "in_progress"} else "torrent_seasons_none"
            return await out.edit(self.say(key, title=base) + "\n\n" + lines)
        best = all(c.best for c in checks if c.offer)
        await self._offer_all(out, base, offers, lines, best)

    async def _check(self, opt) -> "_Check":
        """Qué hay de una temporada, OVA o película: su línea en la lista y, si falta algo, su oferta."""
        result = await self.k.automator.torrent_check(opt.anilist_id)
        st = result.get("status")
        name = result.get("name") or opt.title
        offer = None
        if st == "missing":
            # "show": cómo sale en el lote («2», que se ve «T2», u «OVA»…)
            offer = {**offer_entry(opt.anilist_id, result, name, opt),
                     "show": opt.tag or str(result.get("season") or "1")}
        tag = opt.tag or f"T{result.get('season') or '?'}"
        return _Check(st, f"<b>{e(tag)}</b> · {e(opt.title)}: {self._state(st, offer)}", offer, is_best(result),
                      "" if opt.tag else name)

    def _state(self, status: str, offer: dict | None) -> str:
        if offer is None:
            return self.STATE.get(status, "⚠️ no he podido mirarla")
        return "🧲 " + ("la película" if offer["movie"] else compress_ranges(offer["missing"]))

    async def _offer_all(self, out, base: str, offers: list[dict], lines: str, best: bool):
        bid = self.session.next_id("torrent_bundle")
        self.session.torrent[f"b{bid}"] = {"base": base, "offers": offers}
        parts = [self.say("torrent_seasons_offer", title=base, count=len(offers)), lines,
                 self.say("torrent_quality_best" if best else "torrent_quality_mixed")]
        label = "🧲 Tráelo, nya" if len(offers) == 1 else f"🧲 Tráelo todo ({len(offers)}) · 1 encargo"
        kb = InlineKeyboardMarkup([[button(label, f"{GO_ALL}:{bid}")], cancel_row()])
        await out.edit("\n\n".join(parts), reply_markup=kb)


@dataclass
class _Check:
    """Lo que hay por torrent de una cosa del pack."""
    status: str
    line: str                   # su línea en la lista (HTML)
    offer: dict | None          # su oferta, si falta algo
    best: bool                  # ¿todo en la mejor calidad?
    name: str                   # su nombre, si es una temporada ("" en los extras)


class TorrentBundlePlacing(BundlePlacing):
    """Paso 3 de «todo»: un lote de encargos por torrent (un carro, un visto bueno), como el de la web."""

    def __init__(self, kuro, submitter, out, bundle_key: int, session):
        self.bundle = session.torrent.get(f"b{bundle_key}")
        base = self.bundle["base"] if self.bundle else ""
        super().__init__(kuro, submitter, out, SeasonGroup(base, [], ""))

    async def collect(self):
        if not self.bundle:
            await self.stop("expired")
        items = []
        for offer in self.bundle["offers"]:
            if self.sub.already_active(-offer["anilist_id"]):
                self.skipped.append(season_tag(offer["show"]))
                continue
            items.append(Item(post_of(offer), offer["show"], library_of(offer)))
        if not items:
            await self.stop("bundle_all_have", title=self.group.base)
        return items

    def store(self, items):
        target = super().store(items)
        notes = {o["anilist_id"]: o["note"] for o in self.bundle["offers"]}
        for req in target.reqs:
            self.k.memo.notes[req.id] = notes.get(req.anilist_id, "")
        return target

    def sent_text(self, target):
        return super().sent_text(target) + "\n\n" + self.say("torrent_slow")
