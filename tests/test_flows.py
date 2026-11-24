"""
Pruebas de los flujos de Kuro con dobles: Telegram, Anime-Automator y la web
son falsos, así que no se descarga ni se envía nada de verdad.

    docker run --rm -v "$PWD:/src" -w /src requester-bot-requester-bot python -m unittest -v
"""

import asyncio
import tempfile
import unittest
from types import SimpleNamespace

from telegram.error import BadRequest, NetworkError

from bot.config import Settings
from bot.core.models import Status
from bot.handlers.admin import Alta, Descargados, HistoryPage, Pendientes
from bot.handlers.general import Cupo, Help, Start
from bot.handlers.orders import Decision, Pick, PickAll
from bot.handlers.search import CardPage, Cancel, FreeText
from bot.handlers.torrent import TorrentAll, TorrentGo, TorrentGoAll, TorrentPick, TorrentSeason
from bot.kuro import Kuro
from bot.services.japanpaw import Details, PostInfo, SearchResult

ADMIN, CLIENT, STRANGER = 1000, 2000, 3000


# ---------------------------------------------------------------- dobles
class Msg:
    _ids = iter(range(1, 10**6))

    def __init__(self, chat_id, text="", photo=None, reply_markup=None, bot=None):
        self.message_id = next(self._ids)
        self.chat = SimpleNamespace(id=chat_id)
        self.text = text
        self.photo = [SimpleNamespace(file_id=f"file{self.message_id}")] if photo is not None else None
        self.reply_markup = reply_markup
        self.bot = bot
        self.edits = []

    async def reply_text(self, text, **kw):
        return self.bot._record(self.chat.id, text, kw)

    async def edit_text(self, text, **kw):
        self.edits.append((text, kw))
        self.text, self.reply_markup = text, kw.get("reply_markup")
        return self

    async def delete(self):
        self.bot.deleted.append(self.message_id)


class FakeBot:
    def __init__(self):
        self.sent: list[Msg] = []
        self.deleted = []
        self.fail_next: Exception | None = None

    def _record(self, chat_id, text, kw, photo=None):
        m = Msg(chat_id, text, photo, kw.get("reply_markup"), self)
        self.sent.append(m)
        return m

    async def send_message(self, chat_id, text, **kw):
        if self.fail_next:
            ex, self.fail_next = self.fail_next, None
            raise ex
        return self._record(chat_id, text, kw)

    async def send_photo(self, chat_id, photo, caption="", **kw):
        return self._record(chat_id, caption, kw, photo=photo)

    def to(self, chat_id):
        return [m for m in self.sent if m.chat.id == chat_id]


class Query:
    def __init__(self, message: Msg, data: str):
        self.message = message
        self.data = data
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, **kw):
        return await self.message.edit_text(text, **kw)

    async def edit_message_reply_markup(self, markup):
        self.message.reply_markup = markup

    async def edit_message_media(self, media, reply_markup=None):
        self.message.text, self.message.reply_markup = media.caption, reply_markup
        return self.message


class FakeAutomator:
    def __init__(self):
        self.downloads = []
        self.library = {"status": "missing", "missing": [1, 2], "have": 0, "available": 2, "folder": "X"}
        self.download_result = {"status": "queued", "queued": [1, 2], "tracked": True, "available": 2}
        self.season_info: list = []
        self.synced: list[list[dict]] = []   # cada lista mandada a /watches
        self.sync_ok = True

    async def request_download(self, paste_url, job_id=None, movie=False, title=None):
        self.downloads.append((paste_url, job_id))
        return dict(self.download_result)

    async def check_library(self, paste_url, movie=False, title=None):
        return dict(self.library)

    async def seasons(self, titles, budget=12):
        return self.season_info

    async def sync_watches(self, watches):
        self.synced.append(list(watches))
        return self.sync_ok

    async def poll_watch(self, watch_url):
        return {"status": "ok"}

    torrent_result = {"status": "missing", "name": "Kono Oto Tomare!", "season": "2", "missing": [1, 2, 3],
                      "found": [1, 2, 3], "have": 0, "preferred": 3, "groups": {"Erai-raws": 3},
                      "folder": "Anime/Kono Oto Tomare!/Temporada 2"}
    torrent_download_result = {"status": "queued", "name": "Kono Oto Tomare!", "queued": [1, 2, 3],
                               "tracked": True, "available": 3, "have": 0, "season": "2"}

    async def torrent_check(self, anilist_id, season=None):
        self.torrent_checks = getattr(self, "torrent_checks", []) + [(anilist_id, season)]
        return dict(self.torrent_result, **({"season": season} if season else {}))

    async def torrent_download(self, anilist_id, season=None, job_id=None):
        self.torrent_downloads = getattr(self, "torrent_downloads", []) + [(anilist_id, season, job_id)]
        return dict(self.torrent_download_result)


class NoAiring:
    """AniList sin respuesta (las pruebas no salen a internet)."""
    async def exact(self, title):
        return None

    async def lookup(self, title):
        return None

    async def by_id(self, anilist_id):
        return None


class FakeCatalog:
    """AniList para lo que se pide por torrent: Kono Oto Tomare (T1 -> T2) y Kanata Kara (suelta)."""
    def __init__(self):
        from bot.services.catalog import Option
        self.all = {
            103302: Option(103302, "Kono Oto Tomare!", "Koto", "TV", 13, 2019, "FINISHED",
                           description="Chika joins the koto club.", neighbours=[("SEQUEL", 108891, "TV")]),
            108891: Option(108891, "Kono Oto Tomare! 2", "Koto 2", "TV", 13, 2019, "FINISHED",
                           description="The koto club goes on.", genres=["Music", "Drama"],
                           neighbours=[("PREQUEL", 103302, "TV")]),
            209463: Option(209463, "Kanata Kara", "", "TV", None, 2026, "RELEASING"),
            # una serie con su película (para el pack con extras)
            301: Option(301, "Seitokai Yakuindomo", "", "TV", 13, 2010, "FINISHED",
                        neighbours=[("SIDE_STORY", 302, "MOVIE")]),
            302: Option(302, "Seitokai Yakuindomo Movie", "", "MOVIE", 1, 2017, "FINISHED",
                        neighbours=[("PARENT", 301, "TV")]),
        }

    async def options(self, query, limit=6):
        return [self.all[108891], self.all[209463]]

    async def option(self, anilist_id):
        return self.all.get(anilist_id)

    async def details(self, options):
        return {o.anilist_id: o.details() for o in options}

    async def pack(self, anilist_id):
        if anilist_id in (301, 302):
            return [self.all[301], self.all[302]]
        return [self.all[103302], self.all[108891]] if anilist_id in (103302, 108891) else [self.all[anilist_id]]


class FakeSite:
    def __init__(self):
        self.results = [SearchResult(11, "Anime A", "https://japanpaw.com/a"),
                        SearchResult(12, "Anime A 2nd Season", "https://japanpaw.com/a2")]
        self.with_details = True

    async def search_with_aliases(self, query):
        return list(self.results), None

    kinds: dict = {}

    async def post_kinds(self, ids):
        return self.kinds

    async def details(self, ids):
        return {i: Details(synopsis="Sinopsis " * 5, episodes="12") for i in ids} if self.with_details else {}

    async def get_post(self, url, post_id, title=""):
        return PostInfo(post_id, title or f"Post {post_id}", url, f"https://paste.japan-paw.net/?v={post_id}",
                        str(post_id), False, "BD 1080p")

    async def post_by_id(self, post_id):
        return next((r for r in self.results if r.post_id == post_id), None)

    async def cover_bytes(self, url):
        return None

    async def close(self):
        pass


def settings(data_dir, **kw) -> Settings:
    base = dict(token="x", admin_chat_id=ADMIN, allowed_chat_ids=frozenset({CLIENT}), access_keyword="",
                weekly_limit=3, automator_url="http://a", sockpuppet_url="ws://b", japanpaw_base="https://c",
                force_browser=False, data_dir=data_dir, callback_secret="s", events_port=0,
                tracking_sources=frozenset({"changedetection"}))   # sin URL de change-detection: apagado
    base.update(kw)
    return Settings(**base)


class KuroTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.make()

    def make(self, **cfg):
        self.automator, self.site, self.bot = FakeAutomator(), FakeSite(), FakeBot()
        self.k = Kuro(settings(self.tmp.name, **cfg), automator=self.automator, site=self.site)
        self.k.messenger.attach(self.bot)
        self.k.tracker.airing = NoAiring()
        self.k.catalog = FakeCatalog()
        self.chat_data = {ADMIN: {}, CLIENT: {}, STRANGER: {}}

    def tearDown(self):
        self.tmp.cleanup()

    # -------------------------------------------------------- utilidades
    def ctx(self, chat_id, args=None):
        return SimpleNamespace(bot=self.bot, chat_data=self.chat_data[chat_id], args=args or [])

    def update(self, chat_id, text="", query=None):
        msg = query.message if query else Msg(chat_id, text, bot=self.bot)
        return SimpleNamespace(callback_query=query, effective_message=msg,
                               effective_chat=SimpleNamespace(id=chat_id, type="private", title=None),
                               effective_user=SimpleNamespace(full_name=f"User{chat_id}", username=None))

    async def press(self, command_cls, chat_id, data, message=None):
        q = Query(message or Msg(chat_id, bot=self.bot), data)
        await command_cls(self.k)(self.update(chat_id, query=q), self.ctx(chat_id))
        return q

    async def type(self, command_cls, chat_id, text="", args=None):
        await command_cls(self.k)(self.update(chat_id, text), self.ctx(chat_id, args))

    @staticmethod
    def buttons(msg) -> list[str]:
        kb = msg.reply_markup
        return [b.callback_data for row in (kb.inline_keyboard if kb else []) for b in row]

    def admin_request_msg(self):
        return next(m for m in reversed(self.bot.to(ADMIN)) if any(
            d.startswith(("ok:", "bok:")) for d in self.buttons(m)))


# ---------------------------------------------------------------- pruebas
class TestSearch(KuroTest):
    async def test_cards_with_navigation(self):
        await self.type(FreeText, CLIENT, "anime a")
        card = self.bot.to(CLIENT)[-1]
        self.assertIsNotNone(card.photo)
        self.assertIn("card:1:1", self.buttons(card))
        self.assertIn("pick:11", self.buttons(card))
        q = await self.press(CardPage, CLIENT, "card:1:1", message=card)
        self.assertIn("pick:12", self.buttons(q.message))

    async def test_plain_list_without_details_and_season_group(self):
        self.site.with_details = False
        self.automator.season_info = [{"key": "a", "season": "1", "base": "Anime A"},
                                      {"key": "a", "season": "2", "base": "Anime A"}]
        await self.type(FreeText, CLIENT, "anime a")
        status = self.bot.to(CLIENT)[-1]
        self.assertEqual(self.buttons(status), ["pick:11", "pick:12", "all:1", "cancel"])

    async def test_cancel_card_deletes_it(self):
        await self.type(FreeText, CLIENT, "anime a")
        card = self.bot.to(CLIENT)[-1]
        await self.press(Cancel, CLIENT, "cancel", message=card)
        self.assertIn(card.message_id, self.bot.deleted)

    async def test_blocked_anime(self):
        self.site.results = [SearchResult(21, "One Piece", "https://japanpaw.com/op"),
                             SearchResult(22, "One Piece Film: Red", "https://japanpaw.com/opr")]
        await self.type(FreeText, CLIENT, "one piece")
        self.assertIn("one piece", self.bot.to(CLIENT)[-1].text.lower())
        self.assertNotIn("pick:21", self.buttons(self.bot.to(CLIENT)[-1]))
        self.assertFalse(any("pick:" in d for m in self.bot.to(CLIENT) for d in self.buttons(m)))
        # aunque se busque por otro nombre, lo que salga de Naruto no se puede elegir
        self.site.with_details = False
        self.site.results = [SearchResult(23, "Naruto: Shippuuden", "https://japanpaw.com/n"),
                             SearchResult(24, "Boku no Hero", "https://japanpaw.com/b")]
        await self.type(FreeText, CLIENT, "shippuden")
        self.assertEqual(self.buttons(self.bot.to(CLIENT)[-1]), ["pick:24", "cancel"])
        # el miauestro sí puede
        await self.type(FreeText, ADMIN, "naruto")
        self.assertIn("pick:23", self.buttons(self.bot.to(ADMIN)[-1]))

    def test_blocklist(self):
        from bot.core.blocklist import Blocklist, parse
        b = Blocklist(parse(None))
        self.assertTrue(b.matches("ONE PIECE Film: Red"))
        self.assertTrue(b.matches("Boruto: Naruto Next Generations"))
        self.assertFalse(b.matches("Monster", "One Punch Man"))
        self.assertFalse(Blocklist(parse("")).matches("Naruto"))

    async def test_movies_and_ovas_join_the_pack(self):
        self.site.with_details = False
        self.site.results = [SearchResult(31, "Monster Musume no Iru Nichijou", "https://japanpaw.com/mm"),
                             SearchResult(32, "Monster", "https://japanpaw.com/m"),
                             SearchResult(33, "Monster Musume no Iru Nichijou OVA", "https://japanpaw.com/mmo"),
                             SearchResult(34, "Gekijouban Monster Musume", "https://japanpaw.com/mmp")]
        self.site.kinds = {34: {"pelicula"}}
        self.automator.season_info = [
            {"key": "mm", "season": "1", "base": "Monster Musume no Iru Nichijō"},
            {"key": "monster", "season": "1", "base": "Monster"},
            {"key": "mmova", "season": "1", "base": "Monster Musume no Iru Nichijō OVA"},
            {"key": "gmm", "season": "1", "base": "Gekijōban Monster Musume"}]
        await self.type(FreeText, CLIENT, "monster musume")
        status = self.bot.to(CLIENT)[-1]
        # la OVA va con su serie (no con «Monster»); la película no es de esta serie ni de «Monster»
        self.assertEqual(self.buttons(status), ["pick:31", "pick:33", "all:1", "pick:32", "pick:34", "cancel"])
        texts = [b.text for row in status.reply_markup.inline_keyboard for b in row]
        self.assertIn("OVA · Monster Musume no Iru Nichijou OVA", texts)
        self.assertTrue(any("T1 + 1 extra" in t for t in texts), texts)
        from bot.ui.results import extra_of
        self.assertTrue(extra_of("Kimetsu no Yaiba", "Kimetsu no Yaiba: Mugen Ressha-hen", True))
        self.assertTrue(extra_of("Seitokai Yakuindomo", "Gekijouban Seitokai Yakuindomo 2", True))
        self.assertFalse(extra_of("Kimetsu no Yaiba", "Kimetsu no Yaiba: Yuukaku-hen", False))

    async def test_movie_with_another_name_joins_its_series(self):
        """«Suzumiya Haruhi no Shoushitsu» no empieza por el nombre de la serie: lo dice AniList."""
        self.site.with_details = False
        self.site.results = [SearchResult(41, "Suzumiya Haruhi no Yuuutsu", "https://japanpaw.com/h"),
                             SearchResult(42, "Suzumiya Haruhi no Shoushitsu", "https://japanpaw.com/hs"),
                             SearchResult(43, "Nagato Yuki-chan no Shoushitsu", "https://japanpaw.com/n")]
        self.site.kinds = {42: {"pelicula"}}
        self.automator.season_info = [
            {"key": "haruhi", "season": "1", "base": "Suzumiya Haruhi no Yūutsu"},
            {"key": "shoshitsu", "season": "1", "base": "Suzumiya Haruhi no Shōshitsu",
             "series": "Suzumiya Haruhi no Yuuutsu", "series_key": "haruhi", "format": "MOVIE"},
            {"key": "nagato", "season": "1", "base": "Nagato Yuki-chan no Shōshitsu"}]
        await self.type(FreeText, CLIENT, "suzumiya haruhi")
        status = self.bot.to(CLIENT)[-1]
        self.assertEqual(self.buttons(status), ["pick:41", "pick:42", "all:1", "pick:43", "cancel"])
        texts = [b.text for row in status.reply_markup.inline_keyboard for b in row]
        self.assertIn("🎬 Película · Suzumiya Haruhi no Shoushitsu", texts)
        self.assertTrue(any("T1 + 1 extra" in t for t in texts), texts)

    async def test_stranger_is_denied(self):
        await self.type(FreeText, STRANGER, "anime a")
        self.assertEqual(len(self.bot.to(STRANGER)), 1)
        self.assertNotIn("Anime A", self.bot.to(STRANGER)[0].text)


class TestClientOrder(KuroTest):
    async def pick(self):
        return await self.press(Pick, CLIENT, "pick:11")

    async def test_pick_then_approve(self):
        await self.pick()
        req = self.k.db.get(1)
        self.assertEqual(req.status, Status.PENDING)
        admin_msg = self.admin_request_msg()
        self.assertEqual(self.buttons(admin_msg), ["ok:1", "no:1"])
        self.assertIn("En biblioteca", admin_msg.text)   # nota de biblioteca para el admin

        q = await self.press(Decision, ADMIN, "ok:1", message=admin_msg)
        self.assertEqual(q.answers[0][0], "Marchando…")
        self.assertEqual(self.automator.downloads, [("https://paste.japan-paw.net/?v=11", 1)])
        self.assertEqual(self.k.db.get(1).status, Status.APPROVED)
        self.assertIsNone(admin_msg.reply_markup)
        self.assertTrue(self.bot.to(CLIENT))              # aviso al cliente

        q = await self.press(Decision, ADMIN, "ok:1", message=admin_msg)   # doble clic
        self.assertTrue(q.answers[0][1])                  # alerta «ya decidido»
        self.assertEqual(len(self.automator.downloads), 1)

    async def test_failed_dispatch_offers_retry(self):
        await self.pick()
        self.automator.download_result = {"status": "unreachable"}
        admin_msg = self.admin_request_msg()
        await self.press(Decision, ADMIN, "ok:1", message=admin_msg)
        self.assertEqual(self.k.db.get(1).status, Status.FAILED)
        self.assertIn("ok:1", self.buttons(admin_msg))
        self.assertIn("🔁 Reintentar", [b.text for row in admin_msg.reply_markup.inline_keyboard for b in row])

    async def test_reject(self):
        await self.pick()
        n_client = len(self.bot.to(CLIENT))
        await self.press(Decision, ADMIN, "no:1", message=self.admin_request_msg())
        self.assertEqual(self.k.db.get(1).status, Status.REJECTED)
        self.assertEqual(len(self.bot.to(CLIENT)), n_client + 1)

    async def test_already_in_library_costs_nothing(self):
        self.automator.library = {"status": "nothing_new", "have": 12}
        await self.pick()
        self.assertIsNone(self.k.db.get(1))
        self.assertFalse(self.bot.to(ADMIN))

    async def test_quota_exhausted(self):
        self.make(weekly_limit=1)
        await self.pick()
        q = await self.press(Pick, CLIENT, "pick:12")
        self.assertIsNone(self.k.db.get(2))
        self.assertEqual(len(q.message.edits), 3)  # leyendo, biblioteca, sin cupo

    async def test_quality_upgrade_is_exempt(self):
        self.make(weekly_limit=1)
        self.automator.library = {"status": "missing", "missing": [1], "upgrade": [1], "have": 0}
        await self.pick()
        await self.press(Pick, CLIENT, "pick:12")
        self.assertTrue(self.k.db.get(1).quota_exempt)
        self.assertIsNotNone(self.k.db.get(2))

    async def test_admin_unreachable_marks_failed(self):
        self.bot.fail_next = BadRequest("chat not found")
        await self.pick()
        self.assertEqual(self.k.db.get(1).status, Status.FAILED)

    async def test_pending_list_has_buttons(self):
        await self.pick()
        await self.type(Pendientes, ADMIN)
        self.assertEqual(self.buttons(self.bot.to(ADMIN)[-1]), ["ok:1", "no:1"])


class TestBundle(KuroTest):
    async def asyncSetUp(self):
        self.site.with_details = False
        self.automator.season_info = [{"key": "a", "season": "1", "base": "Anime A"},
                                      {"key": "a", "season": "2", "base": "Anime A"}]

    async def test_client_bundle_counts_once(self):
        await self.type(FreeText, CLIENT, "anime a")
        await self.press(PickAll, CLIENT, "all:1")
        self.assertEqual([r.bundle_id for r in self.k.db.bundle(1)], [1, 1])
        self.assertEqual(self.k.db.used_this_week(CLIENT), 1)
        admin_msg = self.admin_request_msg()
        self.assertEqual(self.buttons(admin_msg), ["bok:1", "bno:1"])
        self.assertIn("T1 · ", admin_msg.text)

        await self.press(Decision, ADMIN, "bok:1", message=admin_msg)
        self.assertEqual([j for _, j in self.automator.downloads], [1, 2])
        self.assertIn("T2", self.bot.to(CLIENT)[-1].text)

    async def test_admin_bundle_goes_direct(self):
        await self.type(FreeText, ADMIN, "anime a")
        q = await self.press(PickAll, ADMIN, "all:1")
        self.assertEqual(len(self.automator.downloads), 2)
        self.assertIn("<b>T1</b> · ", q.message.text)

    async def test_expired_group(self):
        q = await self.press(PickAll, CLIENT, "all:99")
        self.assertTrue(q.message.edits)


class TestAdminDirect(KuroTest):
    async def test_admin_pick_dispatches_at_once(self):
        q = await self.press(Pick, ADMIN, "pick:11")
        self.assertEqual(self.automator.downloads, [("https://paste.japan-paw.net/?v=11", 1)])
        self.assertIn("en cola", q.message.text)   # incluye el detalle técnico


class TestEvents(KuroTest):
    async def test_progress_and_completion(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(Decision, ADMIN, "ok:1", message=self.admin_request_msg())
        before_client, before_admin = len(self.bot.to(CLIENT)), len(self.bot.to(ADMIN))
        await self.k.events.route({"job_id": "1", "event": "episode_done", "episode": 1, "done": 1, "total": 2})
        await self.k.events.route({"job_id": "1", "event": "job_complete", "done": [1], "failed": [2]})
        self.assertEqual(self.k.db.get(1).status, Status.COMPLETED)
        self.assertEqual(self.k.db.get(1).eps_failed, 1)
        self.assertEqual(len(self.bot.to(CLIENT)), before_client + 2)
        self.assertEqual(len(self.bot.to(ADMIN)), before_admin + 1)   # resumen para el admin

    async def test_unknown_job_is_ignored(self):
        await self.k.events.route({"job_id": "999", "event": "episode_done"})
        self.assertFalse(self.bot.sent)


class TestHistoryAndCommands(KuroTest):
    async def test_history_by_client(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(Decision, ADMIN, "ok:1", message=self.admin_request_msg())
        await self.k.events.route({"job_id": "1", "event": "job_complete", "done": [1, 2], "failed": []})
        await self.type(Descargados, ADMIN)
        mine = self.bot.to(ADMIN)[-1]
        self.assertIn(f"hist:{CLIENT}:0", self.buttons(mine))
        q = await self.press(HistoryPage, ADMIN, f"hist:{CLIENT}:0", message=mine)
        self.assertIn("Anime A", q.message.text)

    async def test_history_is_admin_only(self):
        q = await self.press(HistoryPage, CLIENT, f"hist:{ADMIN}:0")
        self.assertTrue(q.answers[0][1])

    async def test_cupo(self):
        await self.type(Cupo, CLIENT)
        self.assertIn("carros", self.bot.to(CLIENT)[-1].text)
        self.assertIn("carros", Cupo.names)

    async def test_keyword_registration(self):
        self.make(allowed_chat_ids=frozenset(), access_keyword="gato")
        await self.type(Start, STRANGER, args=["perro"])
        self.assertFalse(self.k.access.allows(STRANGER))
        await self.type(Start, STRANGER, args=["gato"])
        self.assertTrue(self.k.access.allows(STRANGER))
        self.assertTrue(self.bot.to(ADMIN))   # aviso de alta

    async def test_stranger_is_told_password_or_code(self):
        self.make(allowed_chat_ids=frozenset(), access_keyword="gato")
        await self.type(Start, STRANGER)
        text = self.bot.to(STRANGER)[-1].text
        self.assertIn("/start contraseña", text)
        self.assertIn(str(STRANGER), text)

    async def test_admin_lets_in_by_code(self):
        for n, cfg in enumerate((dict(allowed_chat_ids=frozenset(), access_keyword="gato"), {})):
            with self.subTest(cfg=cfg):
                self.make(**cfg)
                who = STRANGER + 10 * n   # misma BD en las dos vueltas
                self.chat_data.setdefault(who, {})
                self.assertFalse(self.k.access.allows(who))
                await self.type(Alta, ADMIN, args=[str(who), "Pepe"])
                self.assertTrue(self.k.access.allows(who))
                self.assertIn("/pedir", self.bot.to(who)[-1].text)   # bienvenida con la ayuda
                self.assertIn("Pepe", self.bot.to(ADMIN)[-1].text)
                await self.type(Alta, STRANGER, args=[str(who + 1)])
                self.assertFalse(self.k.access.allows(who + 1))      # solo el admin

    async def test_help_explains_everything(self):
        await self.type(Help, CLIENT)
        text = self.bot.to(CLIENT)[-1].text
        for part in ("Cómo se pide", "El trato", "/carros", "/pedir", "/id"):
            self.assertIn(part, text)
        self.assertNotIn("/seguimientos", text)   # sin change-detection no se ofrece
        await self.type(Help, ADMIN)
        text = self.bot.to(ADMIN)[-1].text
        for part in ("/pendientes", "/descargados", "/resetcupo", "/alta"):
            self.assertIn(part, text)

    def test_trust_grows_with_served_animes(self):
        levels = [self.k.trust(CLIENT)]
        for i in range(7):
            post = PostInfo(100 + i, f"T{i}", "u", "p", "1", False, "")
            self.k.db.add(CLIENT, "c", post, Status.COMPLETED)
            self.k.db.add(CLIENT, "c", post, Status.COMPLETED)   # el mismo anime otra vez no suma
            levels.append(self.k.trust(CLIENT))
        self.assertEqual(levels, [0, 1, 1, 2, 2, 2, 2, 3])


class TestMessenger(KuroTest):
    async def test_network_error_goes_to_outbox_in_order(self):
        self.bot.fail_next = NetworkError("sin red")
        await self.k.messenger.send(CLIENT, "uno")
        await self.k.messenger.send(CLIENT, "dos")
        self.assertEqual([t for _, _, t, _ in self.k.db.outbox_items()], ["uno", "dos"])
        await self.k.messenger.flush_outbox()
        self.assertEqual([m.text for m in self.bot.to(CLIENT)], ["uno", "dos"])
        self.assertFalse(self.k.db.outbox_items())

    async def test_bad_request_is_not_retried(self):
        self.bot.fail_next = BadRequest("chat not found")   # hereda de NetworkError
        await self.k.messenger.send(CLIENT, "uno")
        self.assertFalse(self.k.db.outbox_items())


if __name__ == "__main__":
    asyncio.run(unittest.main())


class TestTorrent(KuroTest):
    async def not_found(self, chat_id):
        self.site.results = []
        await self.type(FreeText, chat_id, "kono oto tomare 2")
        return self.bot.to(chat_id)[-1]

    async def test_only_the_boss_gets_cards_by_default(self):
        card = await self.not_found(ADMIN)
        self.assertIsNotNone(card.photo)                       # ficha con portada (la de repuesto)
        self.assertIn("The koto club goes on.", card.text)      # sinopsis de AniList
        self.assertIn("inglés", card.text)
        self.assertIn("Música", card.text)
        self.assertEqual(self.buttons(card), ["card:1:1", "noop", "card:1:1", "trt:108891", "tra:108891", "cancel"])
        self.assertNotIn("nyaa", card.text.lower())
        q = await self.press(CardPage, ADMIN, "card:1:1", message=card)
        self.assertIn("trt:209463", self.buttons(q.message))
        self.assertNotIn("tra:209463", self.buttons(q.message))   # sin más temporadas
        msg = await self.not_found(CLIENT)
        self.assertIsNone(msg.photo)
        self.assertEqual(self.buttons(msg), [])

    async def test_disabled(self):
        self.make(torrent_access="off")
        self.assertEqual(self.buttons(await self.not_found(ADMIN)), [])

    async def test_boss_checks_corrects_season_and_orders(self):
        q = await self.press(TorrentPick, ADMIN, "trt:108891")
        self.assertIn("trg:108891:2", self.buttons(q.message))
        self.assertIn("trt:108891:1", self.buttons(q.message))      # corregir la temporada
        self.assertIn("trt:108891:3", self.buttons(q.message))
        self.assertIn("1-3", q.message.text)
        q = await self.press(TorrentPick, ADMIN, "trt:108891:3", message=q.message)
        self.assertEqual(self.automator.torrent_checks[-1], (108891, "3"))
        self.assertIn("trg:108891:3", self.buttons(q.message))

        await self.press(TorrentGo, ADMIN, "trg:108891:3", message=q.message)
        req = self.k.db.get(1)
        self.assertEqual((req.source, req.anilist_id, req.season, req.post_id), ("torrent", 108891, "3", -108891))
        self.assertEqual(self.automator.torrent_downloads, [(108891, "3", 1)])
        self.assertEqual(self.automator.downloads, [])
        self.assertEqual(req.status, Status.APPROVED)

    async def test_client_order_admin_fixes_season_then_approves(self):
        self.make(torrent_access="all")
        q = await self.press(TorrentPick, CLIENT, "trt:108891")
        self.assertNotIn("trt:108891:3", self.buttons(q.message))   # la temporada solo la toca el admin
        await self.press(TorrentGo, CLIENT, "trg:108891:2", message=q.message)
        self.assertEqual(self.k.db.get(1).status, Status.PENDING)
        self.assertEqual(self.k.quota.remaining(CLIENT), 2)
        admin_msg = self.admin_request_msg()
        self.assertEqual(self.buttons(admin_msg), ["ok:1", "no:1", "trs:1:1", "trs:1:3"])
        self.assertIn("Erai-raws", admin_msg.text)
        self.assertIn("anilist.co/anime/108891", admin_msg.text)

        q = await self.press(TorrentSeason, ADMIN, "trs:1:3", message=admin_msg)
        self.assertEqual(self.k.db.get(1).season, "3")
        self.assertIn("T3", q.message.text)
        await self.press(Decision, ADMIN, "ok:1", message=q.message)
        self.assertEqual(self.automator.torrent_downloads, [(108891, "3", 1)])
        self.assertIn("torrent", self.bot.to(CLIENT)[-1].text)

    async def test_nothing_with_spanish_subs_gives_the_cart_back(self):
        self.make(torrent_access="all")
        q = await self.press(TorrentPick, CLIENT, "trt:108891")
        await self.press(TorrentGo, CLIENT, "trg:108891:2", message=q.message)
        self.automator.torrent_download_result = {"status": "nothing_found", "name": "Kono Oto Tomare!"}
        await self.press(Decision, ADMIN, "ok:1", message=self.admin_request_msg())
        self.assertEqual(self.k.db.get(1).status, Status.FAILED)
        self.assertEqual(self.k.quota.remaining(CLIENT), 3)

    async def test_offer_states(self):
        for status, expect in (("nothing_found", "español"), ("unsupported", "series")):
            with self.subTest(status=status):
                self.automator.torrent_result = {"status": status, "name": "X"}
                q = await self.press(TorrentPick, ADMIN, "trt:5")
                self.assertIn(expect, q.message.text)
                self.assertEqual(self.buttons(q.message), [])

    async def test_order_button_needs_the_offer(self):
        q = await self.press(TorrentGo, ADMIN, "trg:108891:2")
        self.assertEqual(self.k.db.get(1), None)
        self.assertTrue(q.message.text)

    async def test_client_cannot_press_old_buttons_when_admin_only(self):
        await self.press(TorrentPick, CLIENT, "trt:108891")
        await self.press(TorrentAll, CLIENT, "tra:108891")
        self.assertFalse(getattr(self.automator, "torrent_checks", []))


class TestTorrentSeasons(KuroTest):
    def checks(self, by_id):
        async def check(anilist_id, season=None):
            self.automator.torrent_checks = getattr(self.automator, "torrent_checks", []) + [(anilist_id, season)]
            return by_id[anilist_id]
        self.automator.torrent_check = check

    def two_missing(self):
        base = {"status": "missing", "name": "Kono Oto Tomare!", "preferred": 13, "found": list(range(1, 14)),
                "groups": {"Erai-raws": 13}}
        self.checks({103302: dict(base, season="1", missing=list(range(1, 14))),
                     108891: dict(base, season="2", missing=[1, 2])})

    async def test_client_orders_all_seasons_as_one_bundle(self):
        self.make(torrent_access="all")
        self.two_missing()
        q = await self.press(TorrentAll, CLIENT, "tra:108891")
        self.assertEqual([i for i, _ in self.automator.torrent_checks], [103302, 108891])   # de la T1 en adelante
        self.assertIn("<b>T1</b>", q.message.text)
        self.assertIn("1-13", q.message.text)
        self.assertEqual(self.buttons(q.message), ["trb:1", "cancel"])

        await self.press(TorrentGoAll, CLIENT, "trb:1", message=q.message)
        reqs = self.k.db.bundle(1)
        self.assertEqual([(r.anilist_id, r.season, r.source) for r in reqs],
                         [(103302, "1", "torrent"), (108891, "2", "torrent")])
        self.assertEqual(self.k.quota.remaining(CLIENT), 2)              # un solo carro
        admin_msg = self.admin_request_msg()
        self.assertEqual(self.buttons(admin_msg), ["bok:1", "bno:1"])
        self.assertIn("Por torrent", admin_msg.text)
        await self.press(Decision, ADMIN, "bok:1", message=admin_msg)
        self.assertEqual(self.automator.torrent_downloads, [(103302, "1", 1), (108891, "2", 2)])

    async def test_only_what_is_missing(self):
        self.checks({103302: {"status": "nothing_new", "name": "Kono Oto Tomare!", "season": "1", "have": 13},
                     108891: {"status": "missing", "name": "Kono Oto Tomare!", "season": "2", "missing": [1],
                              "found": [1], "preferred": 0, "groups": {"ToonsHub": 1}}})
        q = await self.press(TorrentAll, ADMIN, "tra:103302")
        self.assertIn("ya la tienes", q.message.text)
        await self.press(TorrentGoAll, ADMIN, "trb:1", message=q.message)
        self.assertEqual(self.automator.torrent_downloads, [(108891, "2", 1)])

    async def test_nothing_anywhere(self):
        self.checks({103302: {"status": "nothing_new", "name": "K", "season": "1"},
                     108891: {"status": "nothing_found", "name": "K", "season": "2"}})
        q = await self.press(TorrentAll, ADMIN, "tra:103302")
        self.assertIn("subtítulos en español", q.message.text)
        self.assertEqual(self.buttons(q.message), [])

    async def test_pack_with_a_movie(self):
        self.make(torrent_access="all")
        self.checks({301: {"status": "nothing_new", "name": "Seitokai Yakuindomo", "season": "1", "have": 13},
                     302: {"status": "missing", "kind": "movie", "name": "Seitokai Yakuindomo Movie", "season": "",
                           "missing": [1], "found": [1], "preferred": 1, "groups": {"Erai-raws": 1}}})
        q = await self.press(TorrentAll, CLIENT, "tra:301")
        self.assertIn("<b>🎬 Película</b> · Seitokai Yakuindomo Movie: 🧲 la película", q.message.text)
        self.assertIn("<b>T1</b> · Seitokai Yakuindomo: ✅ ya la tienes", q.message.text)
        await self.press(TorrentGoAll, CLIENT, "trb:1", message=q.message)
        req = self.k.db.bundle(1)[0]
        self.assertEqual((req.anilist_id, req.season, req.movie), (302, "", True))
        admin_msg = self.admin_request_msg()
        self.assertIn("🎬 Película · Seitokai Yakuindomo Movie", admin_msg.text)
        await self.press(Decision, ADMIN, "bok:1", message=admin_msg)
        self.assertEqual(self.automator.torrent_downloads, [(302, None, 1)])    # sin temporada que forzar

    async def test_single_season_falls_back_to_one(self):
        q = await self.press(TorrentAll, ADMIN, "tra:209463")
        self.assertIn("trg:209463:2", self.buttons(q.message))


class TestCatalog(unittest.IsolatedAsyncioTestCase):
    async def test_chain_goes_through_specials(self):
        from bot.services.catalog import AniListCatalog, Option
        opts = {1: Option(1, "S1", "", "TV", 24, 2019, "FINISHED", neighbours=[("SEQUEL", 2, "TV")]),
                2: Option(2, "S2", "", "TV", 11, 2021, "FINISHED",
                          neighbours=[("PREQUEL", 1, "TV"), ("SEQUEL", 3, "SPECIAL")]),
                3: Option(3, "Especial", "", "SPECIAL", 1, 2022, "FINISHED",
                          neighbours=[("PREQUEL", 2, "TV"), ("SEQUEL", 4, "TV")]),
                4: Option(4, "S3", "", "TV", 11, 2023, "FINISHED",
                          neighbours=[("PREQUEL", 3, "SPECIAL"), ("SEQUEL", 5, "TV")]),
                5: Option(5, "S4", "", "TV", 12, 2027, "NOT_YET_RELEASED", neighbours=[("PREQUEL", 4, "TV")])}
        cat = AniListCatalog()

        async def option(i):
            return opts.get(i)
        cat.option = option
        # el especial del camino va en el pack, en su sitio; la T4 aún no se ha estrenado
        self.assertEqual([o.title for o in await cat.pack(4)], ["S1", "S2", "Especial", "S3"])

    async def test_pack_with_side_stories_and_movie_sequels(self):
        """Seitokai Yakuindomo: T1 -> OVA -> T2 -> OVA, y de esa OVA cuelgan la película y su secuela."""
        from bot.services.catalog import AniListCatalog, Option
        opts = {1: Option(1, "SY", "", "TV", 13, 2010, "FINISHED", neighbours=[("SEQUEL", 2, "OVA")]),
                2: Option(2, "SY OVA", "", "OVA", 8, 2011, "FINISHED",
                          neighbours=[("PREQUEL", 1, "TV"), ("SEQUEL", 3, "TV")]),
                3: Option(3, "SY*", "", "TV", 13, 2014, "FINISHED",
                          neighbours=[("PREQUEL", 2, "OVA"), ("SEQUEL", 4, "OVA")]),
                4: Option(4, "SY* OVA", "", "OVA", 10, 2014, "FINISHED",
                          neighbours=[("PREQUEL", 3, "TV"), ("SIDE_STORY", 5, "MOVIE")]),
                5: Option(5, "SY Movie", "", "MOVIE", 1, 2017, "FINISHED",
                          neighbours=[("PARENT", 4, "OVA"), ("SEQUEL", 6, "MOVIE")]),
                6: Option(6, "SY Movie 2", "", "MOVIE", 1, 2021, "FINISHED", neighbours=[("PREQUEL", 5, "MOVIE")]),
                7: Option(7, "MM", "", "TV", 12, 2015, "FINISHED",
                          neighbours=[("SIDE_STORY", 8, "OVA"), ("SIDE_STORY", 9, "ONA")]),
                8: Option(8, "MM SP", "", "OVA", 2, 2016, "FINISHED", neighbours=[("PARENT", 7, "TV")]),
                9: Option(9, "MM shorts", "", "ONA", 60, 2015, "FINISHED", neighbours=[("PARENT", 7, "TV")])}
        cat = AniListCatalog()

        async def option(i):
            return opts.get(i)
        cat.option = option
        full = ["SY", "SY OVA", "SY*", "SY* OVA", "SY Movie", "SY Movie 2"]
        self.assertEqual([o.title for o in await cat.pack(3)], full)
        self.assertEqual([o.title for o in await cat.pack(6)], full)      # desde la película 2 también
        # Monster Musume: la OVA cuelga aparte (historia paralela); los cortos ONA no van
        self.assertEqual([o.title for o in await cat.pack(8)], ["MM", "MM SP"])
        self.assertTrue(opts[7].has_pack)
        self.assertEqual([o.tag for o in await cat.pack(3)], ["", "OVA", "", "OVA", "🎬 Película", "🎬 Película"])


    def test_media_to_card(self):
        from bot.services.catalog import Option
        o = Option.from_media({
            "id": 7, "status": "FINISHED", "episodes": 12, "format": "TV", "season": "FALL", "seasonYear": 2019,
            "genres": ["Slice of Life", "Music"], "title": {"romaji": "Hibike", "english": "Sound!"},
            "description": "Kumiko joins<br><br>the <i>band</i> &amp; more.\n\n(Source: Crunchyroll)",
            "startDate": {"year": 2019}, "coverImage": {"large": "https://s4.anilist.co/x.jpg"},
            "relations": {"edges": [{"relationType": "SEQUEL", "node": {"id": 8, "format": "TV", "type": "ANIME"}},
                                    {"relationType": "SEQUEL", "node": {"id": 9, "format": "MOVIE", "type": "ANIME"}},
                                    {"relationType": "SIDE_STORY", "node": {"id": 10, "format": "TV", "type": "ANIME"}}]}})
        self.assertEqual(o.neighbours, [("SEQUEL", 8, "TV"), ("SEQUEL", 9, "MOVIE"), ("SIDE_STORY", 10, "TV")])
        d = o.details()
        self.assertEqual(d.synopsis, "Kumiko joins\nthe band & more.")
        self.assertEqual((d.season, d.genres, d.episodes), ("Otoño 2019", "Recuentos de la vida, Música", "12"))
        self.assertEqual(d.cover_url, "https://s4.anilist.co/x.jpg")
        self.assertIn("inglés", d.note)
        self.assertEqual(o.details("Kumiko entra en la banda.").note, "")
