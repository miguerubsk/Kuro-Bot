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
    def test_window_split_by_days(self):
        # jueves 17:30 en Madrid, 48 h -> jueves 17:00-24:00, viernes entero, sábado hasta las 17:00
        ts = datetime(2026, 11, 26, 17, 30, tzinfo=MADRID).timestamp()
        s = Schedule.from_airing(ts, MADRID, 48)
        self.assertEqual(s.windows(), {3: (17 * 60, 7 * 60), 4: (0, 24 * 60), 5: (0, 17 * 60)})
        lim = s.time_schedule_limit("Europe/Madrid")
        self.assertTrue(lim["enabled"])
        self.assertEqual(lim["thursday"], {"enabled": True, "start_time": "17:00",
                                           "duration": {"hours": "7", "minutes": "00"}})
        self.assertFalse(lim["monday"]["enabled"])
        self.assertEqual(s.describe(), "los jueves desde las 17:00, durante 48 h")

    def test_wraps_the_week(self):
        ts = datetime(2026, 11, 29, 20, 0, tzinfo=MADRID).timestamp()   # domingo
        # domingo 20:00 + 30 h: 4 h del domingo, el lunes entero y 2 h del martes
        self.assertEqual(Schedule.from_airing(ts, MADRID, 30).windows(),
                         {6: (20 * 60, 4 * 60), 0: (0, 24 * 60), 1: (0, 2 * 60)})

    def test_premiere_starts_the_day_before(self):
        s = Schedule.from_premiere("2025-07-04", 48)                     # viernes
        self.assertEqual((s.weekday, s.start_min, s.hours), (3, 0, 96))
        self.assertIsNone(Schedule.from_premiere("?", 48))

    def test_always_has_no_limit(self):
        self.assertFalse(Schedule.always().time_schedule_limit("Europe/Madrid")["enabled"])
        self.assertEqual(Schedule.from_dict(Schedule.always().to_dict()), Schedule.always())

    def test_payload_only_watches_the_episode_grid(self):
        cd = ChangeDetectionClient("http://cd", "k", tag="kuro", check_minutes=60)
        body = cd.payload("https://paste.japan-paw.net/?v=1", "X - Japan-Paw! Descarga Calidad",
                          Schedule(3, 17 * 60, 48, "anilist"))
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
        super().make(**cfg)
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
        await self.press(Pick, ADMIN, "pick:11")
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

    async def test_anilist_finished_waits_for_the_site(self):
        await self.activate()
        self.airing.status, self.airing.next_at = "FINISHED", None
        await self.k.tracker.maintain()
        self.assertEqual(self.k.db.track_get(1).status, TrackStatus.ACTIVE)   # dos semanas de margen


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
