"""Seguimiento semanal: horario, oferta, aprobación, límite, lotes y fin de la emisión (con dobles)."""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from bot.core.models import TrackStatus
from bot.handlers.orders import Decision, Pick, PickAll
from bot.handlers.search import FreeText
from bot.handlers.tracking import Seguimientos, TrackDecision, TrackNo, TrackStop, TrackYes
from bot.services.airing import Airing
from bot.services.changedetection import FILTER, ChangeDetectionClient, ChangeDetectionError
from bot.services.japanpaw import PostInfo
from bot.tracking.schedule import Schedule
from tests.test_flows import ADMIN, CLIENT, FakeSite, KuroTest

MADRID = ZoneInfo("Europe/Madrid")


class TestSchedule(unittest.TestCase):
    def test_window_is_one_day_at_most(self):
        # jueves 17:30 en Madrid: de jueves 17:00 a viernes 17:00, aunque se pidan 48 h
        ts = datetime(2026, 11, 26, 17, 30, tzinfo=MADRID).timestamp()
        s = Schedule.from_airing(ts, MADRID, 48)
        self.assertEqual(s.windows(), {3: (17 * 60, 7 * 60), 4: (0, 17 * 60)})
        lim = s.time_schedule_limit("Europe/Madrid")
        self.assertTrue(lim["enabled"])
        self.assertEqual(lim["thursday"], {"enabled": True, "start_time": "17:00",
                                           "duration": {"hours": "7", "minutes": "00"}})
        self.assertFalse(lim["monday"]["enabled"])
        self.assertEqual(s.describe(), "los jueves desde las 17:00, durante 24 h")
        self.assertEqual(Schedule.from_airing(ts, MADRID, 6).hours, 6)

    def test_wraps_the_week(self):
        ts = datetime(2026, 11, 29, 20, 0, tzinfo=MADRID).timestamp()   # domingo
        self.assertEqual(Schedule.from_airing(ts, MADRID, 24).windows(), {6: (20 * 60, 4 * 60), 0: (0, 20 * 60)})

    def test_premiere_is_the_japanese_day(self):
        # estreno en viernes (día de Japón): de jueves 16:00 a viernes 16:00 en Madrid en invierno…
        winter = datetime(2026, 11, 23, tzinfo=MADRID)
        s = Schedule.from_premiere("2025-07-04", MADRID, now=winter)
        self.assertEqual((s.weekday, s.start_min, s.hours), (3, 16 * 60, 24))
        self.assertIn("medianoche en Japón", s.describe())
        # …y desde las 17:00 en verano
        summer = Schedule.from_premiere("2025-07-04", MADRID, now=datetime(2026, 7, 1, tzinfo=MADRID))
        self.assertEqual((summer.weekday, summer.start_min), (3, 17 * 60))
        self.assertIsNone(Schedule.from_premiere("?", MADRID))

    def test_old_long_windows_are_capped(self):
        self.assertEqual(Schedule.from_dict({"weekday": 3, "start_min": 0, "hours": 96, "source": "estreno"}).hours, 24)

    def test_always_has_no_limit(self):
        self.assertFalse(Schedule.always().time_schedule_limit("Europe/Madrid")["enabled"])
        self.assertEqual(Schedule.from_dict(Schedule.always().to_dict()), Schedule.always())

    def test_payload_only_watches_the_episode_grid(self):
        cd = ChangeDetectionClient("http://cd", "k", tag="kuro", check_minutes=60)
        body = cd.payload("https://paste.japan-paw.net/?v=1", "X - Japan-Paw! Descarga Calidad",
                          Schedule(3, 17 * 60, 24, "anilist"))
        self.assertEqual(body["include_filters"], [FILTER])
        self.assertEqual(body["time_between_check"], {"minutes": 60})
        self.assertEqual(body["tag"], "kuro")
        self.assertNotIn("notification_urls", body)


# ---------------------------------------------------------------- dobles
class FakeCD:
    enabled = True
    check_minutes = 60

    def __init__(self):
        self.watches: dict[str, str] = {}   # uuid -> url
        self.created, self.deleted, self.rescheduled = [], [], []
        self.fail = False

    async def find(self, url):
        return next((u for u, w in self.watches.items() if w == url), None)

    async def create(self, url, title, schedule):
        if self.fail:
            raise ChangeDetectionError("HTTP 500")
        uuid = f"w{len(self.watches) + 1}"
        self.watches[uuid] = url
        self.created.append((url, title, schedule))
        return uuid

    async def reschedule(self, uuid, schedule):
        self.rescheduled.append((uuid, schedule))

    async def delete(self, uuid):
        self.watches.pop(uuid, None)
        self.deleted.append(uuid)


class FakeAiring:
    def __init__(self):
        self.next_at = datetime(2026, 11, 26, 17, 30, tzinfo=MADRID).timestamp()
        self.status = "RELEASING"
        self.exact_titles: dict[str, str] = {}   # título exacto -> estado en AniList

    async def exact(self, title):
        st = self.exact_titles.get(title)
        return Airing(43, st, self.next_at, 9, 12) if st else None

    async def lookup(self, title):
        return Airing(42, self.status, self.next_at, 9, 12)

    async def by_id(self, anilist_id):
        return Airing(42, self.status, self.next_at, 9, 12)


class AiringSite(FakeSite):
    def __init__(self):
        super().__init__()
        self.airing_ids = {11}

    async def get_post(self, url, post_id, title=""):
        p = await super().get_post(url, post_id, title)
        p.airing = post_id in self.airing_ids
        return p


class TrackingTest(KuroTest):
    def make(self, **cfg):
        super().make(**{"tracking_sources": frozenset({"changedetection", "drive"}), **cfg})
        self.cd, self.airing = FakeCD(), FakeAiring()
        self.site = AiringSite()
        self.k.site = self.site
        self.k.tracker.cd, self.k.tracker.airing = self.cd, self.airing
        self.automator.library = {"status": "missing", "missing": [1, 2], "have": 0, "available": 2,
                                  "folder": "X", "title": "Post 11 - Japan-Paw! Descarga Calidad"}

    def offer_msg(self, chat):
        return next(m for m in reversed(self.bot.to(chat)) if any(d.startswith("tky:") for d in self.buttons(m)))

    def track_admin_msg(self):
        return next(m for m in reversed(self.bot.to(ADMIN)) if any(d.startswith("tka:") for d in self.buttons(m)))


class TestTrackingFlow(TrackingTest):
    async def test_client_offer_approve_and_stop(self):
        await self.press(Pick, CLIENT, "pick:11")
        offer = self.offer_msg(CLIENT)
        self.assertEqual(self.buttons(offer), ["tky:1", "tkn:1"])

        q = await self.press(TrackYes, CLIENT, "tky:1", message=offer)
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.PENDING)
        self.assertIn("jueves", q.message.text)
        admin = self.track_admin_msg()
        self.assertIn("los jueves desde las 17:00", admin.text)
        self.assertFalse(self.cd.created)            # sin el visto bueno no se crea nada

        await self.press(TrackDecision, ADMIN, "tka:1", message=admin)
        t = self.k.db.track_get(1)
        self.assertEqual((t.status, t.watch_uuid, t.owned), (TrackStatus.ACTIVE, "w1", True))
        url, title, schedule = self.cd.created[0]
        self.assertEqual(title, "Post 11 - Japan-Paw! Descarga Calidad")   # el <title> que usa Anime-Automator
        self.assertEqual(schedule.weekday, 3)
        self.assertIn("📡", self.bot.to(CLIENT)[-1].text)

        await self.type(Seguimientos, CLIENT)
        listing = self.bot.to(CLIENT)[-1]
        self.assertEqual(self.buttons(listing), ["tks:1"])
        await self.press(TrackStop, CLIENT, "tks:1", message=listing)
        self.assertEqual(self.cd.deleted, ["w1"])
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ENDED)

    async def test_no_offer_when_not_airing_or_disabled(self):
        await self.press(Pick, CLIENT, "pick:12")
        self.assertFalse(any(d.startswith("tky:") for m in self.bot.sent for d in self.buttons(m)))
        self.k.tracker.cd = type("Off", (), {"enabled": False})()
        self.k.tracker.sources = frozenset({"changedetection"})
        await self.press(Pick, ADMIN, "pick:11")
        self.assertFalse(any(d.startswith("tky:") for m in self.bot.sent for d in self.buttons(m)))

    async def test_anilist_confirms_airing_when_the_site_does_not(self):
        # el post 12 no está marcado en emisión en la web, pero AniList dice que se emite
        self.airing.exact_titles = {"Anime A 2nd Season": "RELEASING"}
        await self.press(Pick, CLIENT, "pick:12")
        self.assertTrue(self.offer_msg(CLIENT))
        self.assertTrue(self.k.db.get(1).airing)

    async def test_anilist_finished_does_not_make_it_airing(self):
        self.airing.exact_titles = {"Anime A 2nd Season": "FINISHED"}
        await self.press(Pick, CLIENT, "pick:12")
        self.assertFalse(any(d.startswith("tky:") for m in self.bot.sent for d in self.buttons(m)))

    async def test_offer_even_if_library_complete(self):
        self.automator.library = {"status": "nothing_new", "have": 8}
        await self.press(Pick, CLIENT, "pick:11")
        self.assertIsNone(self.k.db.get(1))
        self.assertTrue(self.offer_msg(CLIENT))

    async def test_decline(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(TrackNo, CLIENT, "tkn:1", message=self.offer_msg(CLIENT))
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.DECLINED)

    async def test_admin_tracks_directly(self):
        await self.press(Pick, ADMIN, "pick:11")
        await self.press(TrackYes, ADMIN, "tky:1", message=self.offer_msg(ADMIN))
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ACTIVE)
        self.assertEqual(len(self.cd.created), 1)

    async def test_someone_else_cannot_answer(self):
        await self.press(Pick, CLIENT, "pick:11")
        q = await self.press(TrackYes, ADMIN, "tky:1")    # desde otro chat
        self.assertTrue(q.answers[0][1])
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.OFFERED)

    async def test_join_existing_watch_without_approval(self):
        await self.press(Pick, ADMIN, "pick:11")
        await self.press(TrackYes, ADMIN, "tky:1", message=self.offer_msg(ADMIN))
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(TrackYes, CLIENT, "tky:2", message=self.offer_msg(CLIENT))
        t = self.k.db.track_get(2)
        self.assertEqual((t.status, t.watch_uuid), (TrackStatus.ACTIVE, "w1"))
        self.assertEqual(len(self.cd.created), 1)
        # el cliente se borra: el watch sigue, que el admin lo usa
        await self.press(TrackStop, CLIENT, "tks:2")
        self.assertFalse(self.cd.deleted)

    async def test_manual_watch_is_reused_and_never_deleted(self):
        self.cd.watches["manual"] = "https://paste.japan-paw.net/?v=11"
        await self.press(Pick, ADMIN, "pick:11")
        await self.press(TrackYes, ADMIN, "tky:1", message=self.offer_msg(ADMIN))
        t = self.k.db.track_get(1)
        self.assertEqual((t.watch_uuid, t.owned), ("manual", False))
        await self.press(TrackStop, ADMIN, "tks:1")
        self.assertFalse(self.cd.deleted)

    async def test_limit_per_client(self):
        self.make(tracking_limit=1)
        self.site.airing_ids = {11, 12}
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(TrackYes, CLIENT, "tky:1", message=self.offer_msg(CLIENT))
        await self.press(Pick, CLIENT, "pick:12")
        self.assertIsNone(self.k.db.track_get(2))         # ni se ofrece: ya tiene 1 de 1
        self.assertIn("/seguimientos", self.bot.to(CLIENT)[-1].text)

    async def test_shared_tracking_is_free(self):
        """Si ya lo sigue otro, apuntarse no gasta cupo (aunque el cupo esté lleno)."""
        other = 2001
        self.make(tracking_limit=1, allowed_chat_ids=frozenset({CLIENT, other}))
        self.chat_data[other] = {}
        self.site.airing_ids = {11, 12}
        await self.press(Pick, CLIENT, "pick:12")
        await self.press(TrackYes, CLIENT, "tky:1", message=self.offer_msg(CLIENT))   # 1 de 1
        await self.press(Pick, other, "pick:11")
        await self.press(TrackYes, other, "tky:2", message=self.offer_msg(other))
        await self.press(TrackDecision, ADMIN, "tka:2", message=self.track_admin_msg())
        # CLIENT está lleno, pero el 11 ya lo sigue otro: se le ofrece y se apunta sin gastar
        await self.press(Pick, CLIENT, "pick:11")
        q = await self.press(TrackYes, CLIENT, "tky:3", message=self.offer_msg(CLIENT))
        t = self.k.db.track_get(3)
        self.assertEqual((t.status, t.shared), (TrackStatus.ACTIVE, True))
        self.assertIn("cupo", q.message.text)
        self.assertEqual(self.k.db.track_counted(CLIENT), 1)
        await self.type(Seguimientos, CLIENT)
        self.assertIn("no gasta cupo", self.bot.to(CLIENT)[-1].text)

        # el admin ve de quién es cada uno
        await self.type(Seguimientos, ADMIN)
        listing = self.bot.to(ADMIN)[-1]
        texts = [b.text for row in listing.reply_markup.inline_keyboard for b in row]
        self.assertEqual(sum(t.endswith(" · Anime A") for t in texts), 2)   # el mismo anime, dos personas
        self.assertTrue(any(t.startswith(f"🗑 User{CLIENT} · ") for t in texts), texts)
        self.assertTrue(any(t.startswith(f"🗑 User{other} · ") for t in texts), texts)
        self.assertIn(f"👤 User{other}", listing.text)

    def test_short_name(self):
        from bot.handlers.tracking import short_name
        self.assertEqual(short_name("luis sagarvinaga (@Luisito_kun)"), "@Luisito_kun")
        self.assertEqual(short_name("Ana"), "Ana")

    async def test_failed_creation_offers_retry(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(TrackYes, CLIENT, "tky:1", message=self.offer_msg(CLIENT))
        self.cd.fail = True
        admin = self.track_admin_msg()
        await self.press(TrackDecision, ADMIN, "tka:1", message=admin)
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.FAILED)
        self.assertIn("tka:1", self.buttons(admin))
        self.cd.fail = False
        await self.press(TrackDecision, ADMIN, "tka:1", message=admin)
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ACTIVE)

    async def test_reject(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(TrackYes, CLIENT, "tky:1", message=self.offer_msg(CLIENT))
        await self.press(TrackDecision, ADMIN, "tkr:1", message=self.track_admin_msg())
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.REJECTED)
        self.assertEqual(self.k.db.track_counted(CLIENT), 0)

    async def test_bundle_offers_the_airing_season(self):
        self.site.with_details = False
        self.site.airing_ids = {12}
        self.automator.season_info = [{"key": "a", "season": "1", "base": "Anime A"},
                                      {"key": "a", "season": "2", "base": "Anime A"}]
        await self.type(FreeText, CLIENT, "anime a")
        await self.press(PickAll, CLIENT, "all:1")
        offer = self.offer_msg(CLIENT)
        self.assertIn("Anime A 2nd Season", offer.text)
        self.assertEqual(self.k.db.track_get(1).post_id, 12)
        self.assertIsNone(self.k.db.track_get(2))

    async def test_offer_is_not_repeated(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(Decision, ADMIN, "no:1", message=next(
            m for m in reversed(self.bot.to(ADMIN)) if "no:1" in self.buttons(m)))
        await self.press(Pick, CLIENT, "pick:11")
        self.assertIsNone(self.k.db.track_get(2))


class TestWatchEvents(TrackingTest):
    async def test_kuro_tells_followers_of_new_episodes(self):
        await self.press(Pick, ADMIN, "pick:11")
        await self.press(TrackYes, ADMIN, "tky:1", message=self.offer_msg(ADMIN))
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(TrackYes, CLIENT, "tky:2", message=self.offer_msg(CLIENT))
        n_admin, n_client = len(self.bot.to(ADMIN)), len(self.bot.to(CLIENT))
        ev = {"job_id": "watch:123", "event": "episode_done", "name": "Anime A", "episode": 9,
              "watch_url": "https://paste.japan-paw.net/?v=11", "kind": "series"}
        await self.k.events.route(ev)
        self.assertEqual(len(self.bot.to(CLIENT)), n_client + 1)
        self.assertIn("09", self.bot.to(CLIENT)[-1].text)
        self.assertEqual(len(self.bot.to(ADMIN)), n_admin)     # a él ya le avisa Anime-Automator
        await self.k.events.route({**ev, "event": "job_complete"})
        await self.k.events.route({**ev, "watch_url": "https://paste.japan-paw.net/?v=99"})
        self.assertEqual(len(self.bot.to(CLIENT)), n_client + 1)


class TestMaintenance(TrackingTest):
    async def activate(self):
        await self.press(Pick, ADMIN, "pick:11")
        await self.press(TrackYes, ADMIN, "tky:1", message=self.offer_msg(ADMIN))

    async def test_ends_when_site_stops_airing(self):
        await self.activate()
        self.site.airing_ids = set()
        self.airing.status = "FINISHED"                   # y AniList tampoco lo da por emitiéndose
        await self.k.tracker.maintain()
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ENDED)
        self.assertEqual(self.cd.deleted, ["w1"])

    async def test_reschedules_when_airing_time_moves(self):
        await self.activate()
        self.airing.next_at = datetime(2026, 11, 28, 1, 0, tzinfo=MADRID).timestamp()
        await self.k.tracker.maintain()
        self.assertEqual(len(self.cd.rescheduled), 1)
        self.assertEqual(Schedule.from_dict(self.k.db.track_get(1).schedule).weekday, 5)
        await self.k.tracker.maintain()
        self.assertEqual(len(self.cd.rescheduled), 1)     # sin cambios, no se toca

    async def test_site_unmarks_but_anilist_still_releasing(self):
        await self.activate()
        self.site.airing_ids = set()                      # la web ya no lo marca…
        await self.k.tracker.maintain()                   # …pero AniList sigue: no se acaba
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ACTIVE)
        self.airing.status = "FINISHED"
        await self.k.tracker.maintain()
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ENDED)

    async def test_anilist_finished_waits_for_the_site(self):
        await self.activate()
        self.airing.status, self.airing.next_at = "FINISHED", None
        await self.k.tracker.maintain()
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ACTIVE)   # dos semanas de margen


class TestDrive(TrackingTest):
    URL = "https://paste.japan-paw.net/?v=11"

    async def activate(self, chat=ADMIN):
        await self.press(Pick, chat, "pick:11")
        await self.press(TrackYes, chat, "tky:1", message=self.offer_msg(chat))
        if chat != ADMIN:
            await self.press(TrackDecision, ADMIN, "tka:1", message=self.track_admin_msg())

    async def test_list_is_sent_on_activate_and_stop(self):
        await self.activate()
        (w,) = self.automator.synced[-1]
        self.assertEqual((w["watch_url"], w["title"], w["timezone"]),
                         (self.URL, "Post 11 - Japan-Paw! Descarga Calidad", "Europe/Madrid"))
        self.assertEqual((w["schedule"]["weekday"], w["schedule"]["start_min"], w["schedule"]["hours"]),
                         (3, 17 * 60, 24))
        self.assertEqual(self.k.db.track_get(1).watch_title, w["title"])
        await self.k.tracker.stop(self.k.db.track_get(1))
        self.assertEqual(self.automator.synced[-1], [])

    async def test_drive_only_needs_no_changedetection(self):
        self.k.tracker.sources = frozenset({"drive"})
        self.k.tracker.cd = type("Off", (), {"enabled": False})()
        await self.activate(CLIENT)
        t = self.k.db.track_get(1)
        self.assertEqual((t.status, t.watch_uuid), (TrackStatus.ACTIVE, ""))
        self.assertFalse(self.cd.created)
        self.assertEqual(len(self.automator.synced[-1]), 1)

    async def test_failed_sync_is_retried(self):
        self.automator.sync_ok = False
        await self.activate()
        self.assertTrue(self.k.tracker._sync_pending)
        self.automator.sync_ok = True
        await self.k.tracker.sync_automator()
        self.assertFalse(self.k.tracker._sync_pending)

    async def test_phase_out_changedetection(self):
        await self.activate()
        self.k.tracker.sources = frozenset({"drive"})
        await self.k.tracker.maintain()
        self.assertEqual(self.cd.deleted, ["w1"])
        self.assertEqual(self.k.db.track_get(1).watch_uuid, "")
        self.assertIn("change-detection", self.bot.to(ADMIN)[-1].text)
        await self.k.tracker.maintain()
        self.assertEqual(self.cd.deleted, ["w1"])          # solo una vez
        self.assertEqual(len(self.automator.synced[-1]), 1)

    async def test_back_to_changedetection_only_empties_the_drive_list(self):
        await self.activate()
        self.k.tracker.sources = frozenset({"changedetection"})
        await self.k.tracker.sync_automator()
        self.assertEqual(self.automator.synced[-1], [])
        n = len(self.automator.synced)
        await self.k.tracker.sync_automator()
        self.assertEqual(len(self.automator.synced), n)    # ya vaciada: no insiste

    async def test_new_check_interval_reaches_existing_watches(self):
        await self.activate()
        await self.k.tracker.maintain()                    # apunta el intervalo actual
        self.assertFalse(self.cd.rescheduled)
        self.cd.check_minutes = 180
        await self.k.tracker.maintain()
        self.assertEqual(len(self.cd.rescheduled), 1)
        await self.k.tracker.maintain()
        self.assertEqual(len(self.cd.rescheduled), 1)

    async def test_old_two_day_windows_are_shrunk(self):
        await self.activate()
        self.k.db.track_update(1, schedule={"weekday": 3, "start_min": 17 * 60, "hours": 48, "source": "anilist"})
        await self.k.tracker.maintain()
        self.assertEqual(self.k.db.track_get(1).schedule["hours"], 24)
        self.assertEqual(len(self.cd.rescheduled), 1)
        self.assertEqual(self.automator.synced[-1][0]["schedule"]["hours"], 24)


class TestBypass(unittest.IsolatedAsyncioTestCase):
    async def test_blocked_page_goes_through_proxy_and_sticks(self):
        import httpx

        from bot.services.japanpaw.fetchers import DirectFetcher
        from bot.services.netblock import NetBypass

        calls = []

        class Proxy(NetBypass):
            async def get_proxied(self, url):
                calls.append(("proxy", url))
                return httpx.Response(200, text="ok", request=httpx.Request("GET", url))

        class Direct:
            async def get(self, url):
                calls.append(("direct", url))
                return httpx.Response(403, text="Forbidden", request=httpx.Request("GET", url))

        f = DirectFetcher(lambda: Direct(), Proxy("socks5://tor:9050"))
        self.assertEqual(await f.fetch("https://paste.japan-paw.net/?v=1"), "ok")
        self.assertEqual(await f.fetch("https://paste.japan-paw.net/?v=2"), "ok")
        self.assertEqual([c[0] for c in calls], ["direct", "proxy", "proxy"])


if __name__ == "__main__":
    unittest.main()


class TestAniListExact(unittest.IsolatedAsyncioTestCase):
    def client(self, media):
        from bot.services.airing import AiringClient

        class C(AiringClient):
            async def _query(self, query, variables, timeout=10):
                return {"Page": {"media": media}}
        return C()

    @staticmethod
    def media(mid, romaji, status, synonyms=()):
        return {"id": mid, "status": status, "episodes": None, "title": {"romaji": romaji, "english": None},
                "synonyms": list(synonyms), "nextAiringEpisode": None}

    async def test_only_the_same_title_counts(self):
        c = self.client([self.media(1, "Berserk: Ougon Jidai-hen - Memorial Edition", "RELEASING"),
                         self.media(2, "Berserk (2017)", "FINISHED", ["Berserk 2nd Season"])])
        info = await c.exact("Berserk 2nd Season")
        self.assertEqual((info.anilist_id, info.status), (2, "FINISHED"))
        self.assertIsNone(await c.exact("Berserk 3rd Season"))

    async def test_long_vowels_and_signs(self):
        c = self.client([self.media(7, "Tsuihou Sareta Tensei Juukishi wa Game Chishiki de Musou Suru", "RELEASING")])
        self.assertEqual((await c.exact("Tsuihō Sareta Tensei Jūkishi wa Game Chishiki de Musō Suru")).anilist_id, 7)
