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
"""

from dataclasses import dataclass

from telegram import InlineKeyboardMarkup

from ..core.text import compress_ranges, e
from ..ui.keyboards import button, cancel_row, season_row
from .placing import Item, Placing
from .targets import TORRENT_SEASON as SEASON, SingleTarget

# prefijos de callback_data (no cambiarlos: los botones viejos de los chats los usan)
OFFER, GO = "trt", "trg"


@dataclass
class TorrentPost:
    """Lo que se guarda como petición (hace el papel del PostInfo de la web)."""
    anilist_id: int
    title: str
    season: str
    airing: bool = False
    source = "torrent"
    paste_url = ""
    movie = False

    @property
    def post_id(self) -> int:
        # negativo: nunca choca con los posts de la web (sirve para «ya lo tienes pedido»)
        return -self.anilist_id

    @property
    def url(self) -> str:
        return f"https://anilist.co/anime/{self.anilist_id}"

    @property
    def label(self) -> str:
        return f"T{self.season}" if self.season else ""


class TorrentOffer:
    """Paso 2: qué hay por torrent de un anime de AniList, y el botón para pedirlo."""

    def __init__(self, kuro, chat_id: int, session):
        self.k = kuro
        self.chat_id = chat_id
        self.say = kuro.persona.to(chat_id)
        self.cache = session.torrent

    async def show(self, out, anilist_id: int, season: str | None = None):
        option = await self.k.tracker.airing.option(anilist_id)
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
        season = str(result.get("season") or "1")
        missing = result.get("missing") or []
        found = result.get("found") or []
        self.cache[f"{anilist_id}:{season}"] = {
            "name": name, "season": season, "missing": missing,
            "airing": bool(option and option.releasing),
            "note": self._admin_note(result),
        }
        parts = [self.say("torrent_offer", title=name, season=season, count=len(missing),
                          ranges=compress_ranges(missing))]
        if result.get("have"):
            parts.append(self.say("torrent_have", have=result["have"]))
        best = found and result.get("preferred", 0) >= len(found)
        parts.append(self.say("torrent_quality_best" if best else "torrent_quality_mixed"))
        rows = [[button("🧲 Tráelo, nya", f"{GO}:{anilist_id}:{season}")]]
        if self.k.is_admin(self.chat_id):
            parts.append(self.say("torrent_season_hint"))
            rows.append(season_row(OFFER, anilist_id, season))
        rows.append(cancel_row())
        return "\n\n".join(parts), InlineKeyboardMarkup(rows)

    @staticmethod
    def _admin_note(result: dict) -> str:
        """Lo que ve el admin al decidir (HTML)."""
        groups = result.get("groups") or {}
        txt = f"\n🧲 Por torrent: {compress_ranges(result.get('missing') or [])}"
        if groups:
            txt += " · " + ", ".join(f"{e(g)} ×{n}" for g, n in sorted(groups.items(), key=lambda x: -x[1]))
        if result.get("folder"):
            txt += f"\nCarpeta: <code>{e(result['folder'])}</code>"
        return txt


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
        self.post = TorrentPost(self.anilist_id, self.offer["name"], self.season, self.offer["airing"])
        return [Item(self.post)]

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
