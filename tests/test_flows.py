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


class NoAiring:
    """AniList sin respuesta (las pruebas no salen a internet)."""
    async def exact(self, title):
        return None

    async def lookup(self, title):
        return None

    async def by_id(self, anilist_id):
        return None


class FakeSite:
    def __init__(self):
        self.results = [SearchResult(11, "Anime A", "https://japanpaw.com/a"),
                        SearchResult(12, "Anime A 2nd Season", "https://japanpaw.com/a2")]
        self.with_details = True

    async def search_with_aliases(self, query):
        return list(self.results), None

    async def post_kinds(self, ids):
        return {}

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
