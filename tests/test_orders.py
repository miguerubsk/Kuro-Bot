"""Encargos y comandos del miauestro: lo que pasa cuando algo no sale a la primera."""

from types import SimpleNamespace

from telegram.error import BadRequest

from bot.core.models import Status
from bot.handlers.admin import Alta, ResetCupo
from bot.handlers.orders import Pick, PickAll
from bot.handlers.search import FreeText
from bot.handlers.torrent import TorrentPick
from bot.handlers.tracking import Seguimientos
from bot.services.japanpaw import Details, PostInfo, SearchResult
from bot.ui.cards import CAPTION_MAX, caption
from bot.ui.results import extra_of
from bot.ui.session import Choice
from tests.test_flows import ADMIN, CLIENT, STRANGER, KuroTest, said


class TestAlta(KuroTest):
    def setUp(self):
        super().setUp()
        self.make(allowed_chat_ids=frozenset(), access_keyword="gato")

    async def add(self, chat):
        async def get_chat(chat_id):
            if chat is None:
                raise BadRequest("chat not found")
            return chat
        self.bot.get_chat = get_chat
        await self.type(Alta, ADMIN, args=[str(STRANGER)])
        return self.bot.to(ADMIN)[-1].text

    async def test_takes_the_telegram_name(self):
        text = await self.add(SimpleNamespace(full_name="Ana Pérez", title=None, username="ana"))
        self.assertTrue(said("admin_added", text))
        self.assertIn("Ana Pérez (@ana)", text)

    async def test_a_group_goes_by_its_title(self):
        text = await self.add(SimpleNamespace(full_name=None, title="Club del koto", username=None))
        self.assertIn("Club del koto", text)
        self.assertNotIn("(@", text)

    async def test_never_talked_to_kuro(self):
        text = await self.add(None)
        self.assertIn(str(STRANGER), text)
        self.assertTrue(self.k.access.allows(STRANGER))

    async def test_usage(self):
        await self.type(Alta, ADMIN, args=["pepe"])
        self.assertIn("Uso: /alta", self.bot.to(ADMIN)[-1].text)


class TestResetCupo(KuroTest):
    def spend(self, chat, n):
        for i in range(n):
            self.k.db.add(chat, "c", PostInfo(100 + i, f"T{i}", "u", "p", "1", False, ""), Status.COMPLETED)

    async def test_one_client_or_everyone(self):
        other = CLIENT + 1
        self.spend(CLIENT, 3)
        self.spend(other, 3)
        await self.type(ResetCupo, ADMIN, args=[str(CLIENT)])
        self.assertTrue(said("admin_reset", self.bot.to(ADMIN)[-1].text))
        self.assertEqual((self.k.quota.remaining(CLIENT), self.k.quota.remaining(other)), (3, 0))
        await self.type(ResetCupo, ADMIN)
        self.assertEqual(self.k.quota.remaining(other), 3)

    async def test_usage(self):
        await self.type(ResetCupo, ADMIN, args=["todos"])
        self.assertEqual(self.bot.to(ADMIN)[-1].text, "Uso: /resetcupo [id_chat]")

    async def test_clients_cannot(self):
        self.spend(CLIENT, 3)
        await self.type(ResetCupo, CLIENT)
        self.assertEqual(self.k.quota.remaining(CLIENT), 0)


class TestSearchFallbacks(KuroTest):
    async def test_site_down(self):
        async def broken(query):
            raise RuntimeError("web caída")
        self.site.search_with_aliases = broken
        await self.type(FreeText, CLIENT, "anime a")
        self.assertTrue(said("search_error", self.bot.to(CLIENT)[-1].text))

    async def test_cards_fail_so_the_list_goes(self):
        async def broken(*a, **kw):
            raise RuntimeError("Telegram no quiere fotos")
        self.k.cards.send = broken
        await self.type(FreeText, CLIENT, "anime a")
        status = self.bot.to(CLIENT)[-1]
        self.assertTrue(said("pick", status.text))
        self.assertEqual(self.buttons(status), ["pick:11", "pick:12", "cancel"])

    async def test_anilist_options_as_a_list_if_cards_fail(self):
        async def broken(options):
            raise RuntimeError("sin portadas")
        self.k.catalog.details = broken
        self.site.results = []
        await self.type(FreeText, ADMIN, "kono oto tomare")
        status = self.bot.to(ADMIN)[-1]
        self.assertTrue(said("not_found", status.text))
        self.assertIn("trt:108891", self.buttons(status))
        self.assertIn("trt:209463", self.buttons(status))
        self.assertIn("tra:108891", self.buttons(status))      # tiene precuela: «todo»
        self.assertEqual(self.buttons(status)[-1], "cancel")

    async def test_clients_get_no_anilist_options_by_default(self):
        self.site.results = []
        await self.type(FreeText, CLIENT, "kono oto tomare")
        status = self.bot.to(CLIENT)[-1]
        self.assertTrue(said("not_found", status.text))
        self.assertEqual(self.buttons(status), [])


class TestPlacingProblems(KuroTest):
    async def test_post_gone_from_the_site(self):
        self.chat_data[CLIENT].clear()                        # sin búsqueda previa
        self.site.results = []
        q = await self.press(Pick, CLIENT, "pick:11")
        self.assertTrue(said("expired", q.message.text))

    async def test_post_cannot_be_read(self):
        async def broken(url, post_id, title=""):
            raise RuntimeError("web caída")
        self.site.get_post = broken
        q = await self.press(Pick, CLIENT, "pick:11")
        self.assertTrue(said("post_error", q.message.text))
        self.assertIsNone(self.k.db.get(1))

    async def test_post_without_link(self):
        get_post = self.site.get_post

        async def no_link(url, post_id, title=""):
            p = await get_post(url, post_id, title)
            p.paste_url = ""
            return p
        self.site.get_post = no_link
        q = await self.press(Pick, CLIENT, "pick:11")
        self.assertTrue(said("no_link", q.message.text))

    async def test_movie_already_in_the_library(self):
        self.automator.library = {"status": "nothing_new", "have": 1, "kind": "movie"}
        q = await self.press(Pick, CLIENT, "pick:11")
        self.assertTrue(said("library_movie", q.message.text))

    async def test_already_downloading(self):
        self.automator.library = {"status": "in_progress"}
        q = await self.press(Pick, CLIENT, "pick:11")
        self.assertTrue(said("library_busy", q.message.text))

    async def test_library_unknown_still_asks_the_admin(self):
        self.automator.library = {"status": "error", "error": "timeout"}
        with self.assertLogs("bot.orders.library", "WARNING"):
            await self.press(Pick, CLIENT, "pick:11")
        self.assertEqual(self.k.db.get(1).status, Status.PENDING)

    async def test_admin_sees_what_is_in_the_library(self):
        self.automator.library = {"status": "missing", "missing": [3, 4], "upgrade": [3, 4], "have": 2,
                                  "available": 4, "folder": "Anime/A", "new_folder": True}
        await self.press(Pick, CLIENT, "pick:11")
        admin = self.admin_request_msg().text
        for part in ("2 de 4", "(faltan 3-4)", "Mejora de calidad", "no gasta cupo", "<code>Anime/A</code>",
                     "— nueva"):
            self.assertIn(part, admin)
        self.assertTrue(self.k.db.get(1).quota_exempt)

    async def test_bundle_skips_seasons_it_cannot_read(self):
        self.site.with_details = False
        self.site.results.append(SearchResult(13, "Anime A 3rd Season", "https://japanpaw.com/a3"))
        self.automator.season_info = [{"key": "a", "season": str(n), "base": "Anime A"} for n in (1, 2, 3)]
        get_post = self.site.get_post

        async def flaky(url, post_id, title=""):
            if post_id == 12:
                raise RuntimeError("web caída")
            p = await get_post(url, post_id, title)
            if post_id == 13:
                p.paste_url = ""
            return p
        self.site.get_post = flaky
        await self.type(FreeText, CLIENT, "anime a")
        await self.press(PickAll, CLIENT, "all:1")
        self.assertEqual([r.post_id for r in self.k.db.pending()], [11])


class TestDispatchOutcomes(KuroTest):
    async def test_each_answer_of_anime_automator(self):
        cases = (({"status": "queued", "queued": [1, 2], "tracked": False}, Status.COMPLETED),
                 ({"status": "in_progress"}, Status.NOTHING_NEW),
                 ({"status": "nothing_new"}, Status.NOTHING_NEW),
                 ({"status": "nothing_found"}, Status.FAILED),
                 ({"status": "error", "error": "boom"}, Status.FAILED))
        for n, (result, status) in enumerate(cases, 1):
            with self.subTest(result=result):
                self.automator.download_result = result
                await self.press(Pick, ADMIN, "pick:11")
                self.assertEqual(self.k.db.get(n).status, status)


class TestTorrentOfferStates(KuroTest):
    async def test_already_have_or_downloading(self):
        for status, key in (("nothing_new", "library_complete"), ("in_progress", "library_busy"),
                            ("rate_limited", "torrent_error")):
            with self.subTest(status=status):
                self.automator.torrent_result = {"status": status, "name": "Kono Oto Tomare!", "have": 13}
                q = await self.press(TorrentPick, ADMIN, "trt:108891")
                self.assertTrue(said(key, q.message.text), q.message.text)

    async def test_movie_offer(self):
        self.automator.torrent_result = {"status": "missing", "name": "Peli", "kind": "movie", "missing": [1],
                                         "found": [1], "preferred": 0, "have": 0}
        q = await self.press(TorrentPick, ADMIN, "trt:302")
        self.assertTrue(said("torrent_offer_movie", q.message.text.split("\n\n")[0]))
        self.assertTrue(said("torrent_quality_mixed", q.message.text.split("\n\n")[1]))
        self.assertEqual(self.buttons(q.message), ["trg:302:1", "cancel"])   # sin flechas de temporada


class TestTrackingList(KuroTest):
    async def test_disabled(self):
        await self.type(Seguimientos, CLIENT)
        self.assertTrue(said("track_disabled", self.bot.to(CLIENT)[-1].text))

    async def test_nothing_tracked(self):
        self.make(tracking_sources=frozenset({"drive"}))
        await self.type(Seguimientos, CLIENT)
        self.assertTrue(said("track_none", self.bot.to(CLIENT)[-1].text))

    async def test_states(self):
        from bot.core.models import TrackStatus
        self.make(tracking_sources=frozenset({"drive"}))
        post = PostInfo(11, "Anime A", "u", "https://paste/11", "1", True, "")
        for status in (TrackStatus.PENDING, TrackStatus.FAILED):
            tid = self.k.db.track_add(CLIENT, "Ana", post)
            self.k.db.track_update(tid, status=status)
        await self.type(Seguimientos, CLIENT)
        text = self.bot.to(CLIENT)[-1].text
        self.assertIn("⏳ pendiente del miauestro", text)
        self.assertIn("⚠️ falló al crearse", text)


class TestPureHelpers(KuroTest):
    def test_caption(self):
        d = Details(episodes="En emisión", season="Otoño 2025", video="BD 1080p", genres="Drama",
                    synopsis="palabra " * 400)
        text = caption(Choice(1, "Anime <A>", None), d)
        self.assertTrue(text.startswith("<b>Anime &lt;A&gt;</b>\n<i>📡 en emisión · Otoño 2025 · BD 1080p</i>"
                                         "\n<i>Drama</i>\n\n"))
        self.assertTrue(text.endswith("palabra…"))
        self.assertLessEqual(len(text.replace("<b>", "").replace("</b>", "").replace("<i>", "")
                                 .replace("</i>", "").replace("&lt;", "<").replace("&gt;", ">")), CAPTION_MAX)
        movie = caption(Choice(1, "Peli", None, True), Details(episodes="1", premiere="2017-08-01"))
        self.assertIn("<i>2017</i>", movie)
        self.assertNotIn("caps.", movie)
        self.assertIn("Sin sinopsis", movie)
        self.assertIn("12 caps.", caption(Choice(1, "Serie", None), Details(episodes="12")))

    def test_extra_of(self):
        self.assertTrue(extra_of("Monster Musume no Iru Nichijou", "Monster Musume no Iru Nichijou OVA", False))
        self.assertTrue(extra_of("Seitokai Yakuindomo", "Gekijouban Seitokai Yakuindomo", True))
        self.assertTrue(extra_of("Seitokai Yakuindomo", "Gekijouban Seitokai Yakuindomo 2", True))
        self.assertTrue(extra_of("Kimetsu no Yaiba", "Kimetsu no Yaiba: Mugen Ressha-hen", True))
        self.assertFalse(extra_of("Kimetsu no Yaiba", "Kimetsu no Yaiba: Mugen Ressha-hen", False))
        self.assertFalse(extra_of("Monster", "Monster Musume no Iru Nichijou OVA", False))
        self.assertFalse(extra_of("Monster", "Gekijouban Monster Musume", True))
        self.assertFalse(extra_of("", "Monster OVA", False))
