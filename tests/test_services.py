"""Clientes de servicios externos, con la red simulada (httpx.MockTransport)."""

import json
import unittest
from unittest import mock

import httpx


def fake_http(handler):
    """Parchea httpx.AsyncClient para que todas las peticiones vayan a `handler`."""
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    return mock.patch("httpx.AsyncClient", side_effect=factory)


class AniListQueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_data(self):
        from bot.services import anilist
        seen = []

        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"Media": {"id": 7}}})

        with fake_http(handler):
            data = await anilist.query("query Q", {"id": 7})
        self.assertEqual(data, {"Media": {"id": 7}})
        self.assertEqual(seen, [{"query": "query Q", "variables": {"id": 7}}])

    async def test_failure_gives_none(self):
        from bot.services import anilist
        with fake_http(lambda request: httpx.Response(500)):
            self.assertIsNone(await anilist.query("query Q", {}))

    def test_names(self):
        from bot.services.anilist import names
        m = {"title": {"romaji": "Kimi ni Todoke", "english": None}, "synonyms": ["From Me to You"]}
        self.assertEqual(names(m), ["Kimi ni Todoke", "From Me to You"])
        self.assertEqual(names({}), [])

    def test_media(self):
        from bot.services.anilist import media
        self.assertEqual(media({"Page": {"media": [{"id": 1}]}}), [{"id": 1}])
        self.assertEqual(media({"Page": {"media": None}}), [])
        self.assertEqual(media({"Page": None}), [])
        self.assertEqual(media(None), [])


def search(*entries):
    """Un AniList falso que responde a todo con esas entradas."""
    return fake_http(lambda request: httpx.Response(200, json={"data": {"Page": {"media": list(entries)}}}))


def entry(i, romaji, english=None, synonyms=(), **extra):
    return {"id": i, "title": {"romaji": romaji, "english": english}, "synonyms": list(synonyms), **extra}


class AlternativeTitlesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from bot.services import aliases
        patcher = mock.patch.dict(aliases._cache, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_romaji_first_only_latin_and_related(self):
        from bot.services.aliases import alternative_titles
        found = [entry(1, "Sousou no Frieren", "Frieren: Beyond Journey’s End",
                       ["葬送のフリーレン", "Frieren at the Funeral", "Frieren 2", "Frieren 3"]),
                 entry(2, "Space Dandy", "Space☆Dandy"),
                 entry(3, "Frieren: Mini", "Frieren: Beyond Journey's End")]
        with search(*found):
            titles = await alternative_titles("Frieren", limit=10)
        self.assertEqual(titles, ["Sousou no Frieren", "Frieren: Mini", "Frieren: Beyond Journey's End",
                                  "Frieren at the Funeral"])

    async def test_cached_and_limited(self):
        from bot.services.aliases import alternative_titles
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(200, json={"data": {"Page": {"media": [
                entry(1, "Dandadan", "DAN DA DAN"), entry(2, "Dandadan 2nd Season", "DAN DA DAN Season 2")]}}})

        with fake_http(handler):
            self.assertEqual(await alternative_titles("dan da dan"), ["Dandadan", "Dandadan 2nd Season",
                                                                      "DAN DA DAN Season 2"])
            self.assertEqual(await alternative_titles("Dan-Da-Dan", limit=1), ["Dandadan"])
        self.assertEqual(calls, [1])

    async def test_stale_cache_asks_again(self):
        from bot.services import aliases
        aliases._cache["dandadan"] = (0, ["Viejo"])
        with search(entry(1, "Dandadan")):
            self.assertEqual(await aliases.alternative_titles("Dandadan"), [])     # el propio nombre no cuenta

    async def test_failure_gives_nothing(self):
        from bot.services.aliases import alternative_titles
        with fake_http(lambda request: httpx.Response(500)):
            self.assertEqual(await alternative_titles("Frieren"), [])
        with search(entry(1, None, None)):
            self.assertEqual(await alternative_titles("Frieren"), [])


class RelatedTest(unittest.TestCase):
    def test_related(self):
        from bot.services.aliases import related
        self.assertTrue(related("Dandadan", "DAN DA DAN Season 2"))
        self.assertTrue(related("Shingeki no Kyojin", "Shingeki no Kyoujin: The Final Season"))
        self.assertTrue(related("Kimi ni Todoke 3rd Season", "Kimi ni Todoke: From Me to You"))
        self.assertTrue(related("Re:Zero kara Hajimeru Isekai Seikatsu", "Re Zero Isekai Seikatsu"))
        self.assertFalse(related("Space☆Dandy", "Dan Da Dan"))
        self.assertFalse(related("The 2nd", "Season 2"))
        self.assertFalse(related("Boku no Hero", "Boku no Pico"))


class AiringTest(unittest.IsolatedAsyncioTestCase):
    async def test_lookup_prefers_what_is_airing(self):
        from bot.services.airing import AiringClient
        found = [entry(1, "Space Dandy", status="FINISHED"),
                 entry(2, "Dandadan", status="FINISHED", episodes=12),
                 entry(3, "Dandadan 2nd Season", status="RELEASING",
                       nextAiringEpisode={"airingAt": 1750000000, "episode": 4})]
        with search(*found):
            a = await AiringClient().lookup("Dandadan")
        self.assertEqual((a.anilist_id, a.next_at, a.next_ep, a.releasing), (3, 1750000000, 4, True))

    async def test_lookup_takes_the_first_related(self):
        from bot.services.airing import AiringClient
        with search(entry(1, "Space Dandy"), entry(2, "Dandadan", status="FINISHED", episodes=12)):
            a = await AiringClient().lookup("Dandadan")
        self.assertEqual((a.anilist_id, a.status, a.episodes, a.next_at, a.releasing),
                         (2, "FINISHED", 12, None, False))

    async def test_lookup_without_anything_related(self):
        from bot.services.airing import AiringClient
        with search(entry(1, "Space Dandy")):
            self.assertIsNone(await AiringClient().lookup("Dandadan"))
        with fake_http(lambda request: httpx.Response(500)):
            self.assertIsNone(await AiringClient().lookup("Dandadan"))

    async def test_exact(self):
        from bot.services.airing import AiringClient
        with search(entry(1, "Dandadan 2nd Season"), entry(2, "Dandadan", synonyms=["Dan Da Dan"])):
            self.assertEqual((await AiringClient().exact("DAN DA DAN")).anilist_id, 2)
            self.assertIsNone(await AiringClient().exact("Dandadan 3"))
            self.assertIsNone(await AiringClient().exact("D!"))

    async def test_by_id(self):
        from bot.services.airing import AiringClient
        with fake_http(lambda request: httpx.Response(200, json={"data": {"Media": entry(5, "X", status="HIATUS")}})):
            self.assertEqual((await AiringClient().by_id(5)).status, "HIATUS")
        with fake_http(lambda request: httpx.Response(200, json={"data": {"Media": None}})):
            self.assertIsNone(await AiringClient().by_id(5))


class AutomatorClientTest(unittest.IsolatedAsyncioTestCase):
    def client(self):
        from bot.services.automator import AutomatorClient
        return AutomatorClient("http://automator:8000/", secret="s3")

    async def test_download_body_and_answer(self):
        seen = []

        def handler(request):
            seen.append((str(request.url), json.loads(request.content), request.headers.get("X-Callback-Secret")))
            return httpx.Response(200, json={"status": "queued", "queued": [1, 2]})

        with fake_http(handler):
            data = await self.client().request_download("https://paste/x", job_id=7, movie=True, title="Película")
            await self.client().request_download("https://paste/y")
            await self.client().check_library("https://paste/z", title="Serie")
        self.assertEqual(data, {"status": "queued", "queued": [1, 2]})
        self.assertEqual(seen, [
            ("http://automator:8000/download",
             {"url": "https://paste/x", "job_id": "7", "kind": "movie", "title": "Película"}, None),
            ("http://automator:8000/download", {"url": "https://paste/y"}, None),
            ("http://automator:8000/check", {"url": "https://paste/z", "title": "Serie"}, None)])

    async def test_torrent_is_signed(self):
        seen = []

        def handler(request):
            seen.append((request.url.path, json.loads(request.content), request.headers.get("X-Callback-Secret")))
            return httpx.Response(200, json={"status": "missing"})

        with fake_http(handler):
            await self.client().torrent_check("42", season="2")
            await self.client().torrent_download(42, job_id=3)
        self.assertEqual(seen, [("/torrent/check", {"anilist_id": 42, "season": "2"}, "s3"),
                                ("/torrent/download", {"anilist_id": 42, "job_id": "3"}, "s3")])

    async def test_unreachable(self):
        def handler(request):
            raise httpx.ConnectError("sin red")

        with fake_http(handler):
            data = await self.client().request_download("https://paste/x")
        self.assertEqual(data, {"status": "unreachable", "error": "sin red"})

    async def test_answers_without_status(self):
        with fake_http(lambda request: httpx.Response(502, text="Bad Gateway")):
            self.assertEqual(await self.client().check_library("u"),
                             {"status": "http_error", "error": "HTTP 502", "_raw": None})
        with fake_http(lambda request: httpx.Response(500, json={"detail": "boom"})):
            self.assertEqual(await self.client().check_library("u"),
                             {"status": "http_error", "error": "HTTP 500", "_raw": {"detail": "boom"}})
        with fake_http(lambda request: httpx.Response(200, json=["queued"])):
            self.assertEqual((await self.client().check_library("u"))["status"], "http_error")

    async def test_seasons(self):
        seen = []

        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={"seasons": [{"title": "A", "season": "2"}]})

        with fake_http(handler):
            self.assertEqual(await self.client().seasons([]), [])
            self.assertEqual(await self.client().seasons(["A"], budget=5), [{"title": "A", "season": "2"}])
        self.assertEqual(seen, [{"titles": ["A"], "budget": 5}])
        with fake_http(lambda request: httpx.Response(200, json={"seasons": None})):
            self.assertEqual(await self.client().seasons(["A"]), [])
        with fake_http(lambda request: httpx.Response(200, json=[])):
            self.assertEqual(await self.client().seasons(["A"]), [])
        with fake_http(lambda request: httpx.Response(500, text="no")):
            self.assertEqual(await self.client().seasons(["A"]), [])

    async def test_watches(self):
        seen = []

        def handler(request):
            seen.append((request.method, request.url.path, json.loads(request.content),
                         request.headers["X-Callback-Secret"]))
            return httpx.Response(200, json={"status": "ok"})

        with fake_http(handler):
            self.assertTrue(await self.client().sync_watches([{"watch_url": "w"}]))
            self.assertEqual(await self.client().poll_watch("w"), {"status": "ok"})
        self.assertEqual(seen, [("PUT", "/watches", {"watches": [{"watch_url": "w"}]}, "s3"),
                                ("POST", "/watches/poll", {"watch_url": "w"}, "s3")])
        with fake_http(lambda request: httpx.Response(401, text="no")):
            self.assertFalse(await self.client().sync_watches([]))
            self.assertEqual((await self.client().poll_watch("w"))["status"], "unreachable")


class DescribeTest(unittest.TestCase):
    def test_queued(self):
        from bot.services.automator import describe
        r = {"status": "queued", "name": "K&K", "queued": [3, 4, 5], "available": 12, "have": 2,
             "already_in_progress": [6, 7], "folder": "/anime/K"}
        self.assertEqual(describe(r, "x"), "📥 <b>K&amp;K</b>: 3 capítulo(s) en cola (3-5) de 12 disponibles; "
                                           "ya había 2.\nYa estaban en cola: 6-7")
        self.assertEqual(describe({"status": "queued"}, "Fallback", for_admin=True),
                         "📥 <b>Fallback</b>: 0 capítulo(s) en cola () de ? disponibles.")
        self.assertTrue(describe(r, "x", for_admin=True).endswith("6-7\nCarpeta: <code>/anime/K</code>"))

    def test_nothing_new(self):
        from bot.services.automator import describe
        r = {"status": "nothing_new", "name": "K", "have": 12, "available": 12, "folder": "/a"}
        self.assertEqual(describe(r, "x"), "✅ <b>K</b> ya está completo (12 de 12 capítulos disponibles).")
        self.assertEqual(describe({"status": "nothing_new"}, "K", for_admin=True),
                         "✅ <b>K</b> ya está completo (? de ? capítulos disponibles).")

    def test_movie(self):
        from bot.services.automator import describe
        m = {"kind": "movie", "name": "Kimi no Na wa", "folder": "/pelis", "file": "Kimi.mkv"}
        self.assertEqual(describe({**m, "status": "queued", "queued": [1]}, "x"),
                         "🎬 Película <b>Kimi no Na wa</b> en cola.")
        self.assertEqual(describe({**m, "status": "queued", "queued": [1]}, "x", for_admin=True),
                         "🎬 Película <b>Kimi no Na wa</b> en cola.\nDestino: <code>/pelis/Kimi.mkv</code>")
        self.assertEqual(describe({**m, "status": "queued", "queued": []}, "x", for_admin=True),
                         "🎬 La película <b>Kimi no Na wa</b> ya estaba en cola.")
        self.assertEqual(describe({**m, "status": "nothing_new"}, "x", for_admin=True),
                         "✅ La película <b>Kimi no Na wa</b> ya estaba en la colección.\n"
                         "Destino: <code>/pelis/Kimi.mkv</code>")
        self.assertEqual(describe({**m, "status": "bad_url"}, "x"),
                         "❌ No se pudo encolar <b>Kimi no Na wa</b>: el enlace no es válido.")

    def test_errors(self):
        from bot.services.automator import describe
        r = {"status": "unreachable", "error": "<timeout>" + "x" * 600}
        self.assertEqual(describe(r, "K"), "❌ No se pudo encolar <b>K</b>: el servicio de descargas no responde.")
        self.assertEqual(describe(r, "K", for_admin=True),
                         "❌ No se pudo encolar <b>K</b>: el servicio de descargas no responde.\n<code>"
                         + ("&lt;timeout&gt;" + "x" * 600)[:500] + "</code>")
        self.assertEqual(describe({"status": "<raro>"}, "K"),
                         "❌ No se pudo encolar <b>K</b>: estado desconocido «&lt;raro&gt;».")

    def test_torrent(self):
        from bot.services.automator import describe_torrent
        self.assertEqual(describe_torrent({"status": "in_progress", "season": 2}, "K"),
                         "⏳ <b>K</b>: lo que falta ya se está descargando.\n🧲 Torrent · T2")
        self.assertEqual(
            describe_torrent({"status": "missing", "name": "K", "missing": [1, 2, 4], "folder": "/a/K",
                              "groups": {"Erai": 1, "Toons<Hub>": 3}, "not_added": [4]}, "x"),
            "🧲 <b>K</b>: faltan 1-2, 4.\n🧲 Torrent · Toons&lt;Hub&gt; ×3, Erai ×1 · Transmission no aceptó 4"
            "\nCarpeta: <code>/a/K</code>")
        # la carpeta ya la pone describe(): no se repite
        txt = describe_torrent({"status": "nothing_new", "name": "K", "have": 3, "available": 3, "folder": "/a/K"},
                               "x")
        self.assertEqual(txt, "✅ <b>K</b> ya está completo (3 de 3 capítulos disponibles).\n"
                              "Carpeta: <code>/a/K</code>")
        self.assertEqual(describe_torrent({"status": "missing"}, "K"), "🧲 <b>K</b>: faltan .")


class FakeSchedule:
    def __init__(self, limited):
        self.limited = limited

    def time_schedule_limit(self, tz):
        return {"enabled": self.limited, "tz": tz}


class ChangeDetectionTest(unittest.IsolatedAsyncioTestCase):
    def client(self, **kw):
        from bot.services.changedetection import ChangeDetectionClient
        return ChangeDetectionClient("http://cd:5000/", "key", **kw)

    def test_payload(self):
        from bot.services.changedetection import FILTER, NOTIFY_BODY
        bare = self.client(check_minutes=1).payload("u", "T", FakeSchedule(True))
        self.assertEqual(bare, {"url": "u", "title": "T", "include_filters": [FILTER],
                                "time_between_check_use_default": False, "time_between_check": {"minutes": 5},
                                "time_schedule_limit": {"enabled": True, "tz": "Europe/Madrid"}})
        full = self.client(tag="kuro", fetch_backend="html_webdriver", notify_url="json://a/webhook",
                           tz="UTC").payload("u", "T", FakeSchedule(False))
        self.assertEqual((full["time_between_check"], full["time_schedule_limit"]["tz"], full["tag"],
                          full["fetch_backend"], full["notification_urls"], full["notification_body"],
                          full["notification_format"]),
                         ({"hours": 6}, "UTC", "kuro", "html_webdriver", ["json://a/webhook"], NOTIFY_BODY, "text"))

    def test_enabled(self):
        from bot.services.changedetection import ChangeDetectionClient
        self.assertTrue(self.client().enabled)
        self.assertFalse(ChangeDetectionClient("http://cd", "").enabled)

    async def test_create_and_the_rest(self):
        seen = []

        def handler(request):
            seen.append((request.method, request.url.path, request.headers["x-api-key"],
                         json.loads(request.content) if request.content else None))
            if request.method == "POST":
                return httpx.Response(201, json={"uuid": "abc"})
            return httpx.Response(200, text="OK")

        c = self.client(check_minutes=30)
        with fake_http(handler):
            self.assertEqual(await c.create("u", "T", FakeSchedule(True)), "abc")
            await c.reschedule("abc", FakeSchedule(True))
            await c.delete("abc")
        self.assertEqual([s[:3] for s in seen], [("POST", "/api/v1/watch", "key"),
                                                 ("PUT", "/api/v1/watch/abc", "key"),
                                                 ("DELETE", "/api/v1/watch/abc", "key")])
        self.assertEqual(seen[0][3]["url"], "u")
        self.assertEqual(seen[1][3], {"time_between_check_use_default": False, "time_between_check": {"minutes": 30},
                                      "time_schedule_limit": {"enabled": True, "tz": "Europe/Madrid"}})

    async def test_create_without_uuid_looks_it_up(self):
        watches = {"k1": {"url": "otra"}, "k2": "raro", "k3": {"url": " u ", "uuid": "real"}}

        def handler(request):
            if request.method == "POST":
                return httpx.Response(200, text="OK")
            return httpx.Response(200, json=watches)

        with fake_http(handler):
            self.assertEqual(await self.client().create("u", "T", FakeSchedule(False)), "real")
            del watches["k3"]["uuid"]
            self.assertEqual(await self.client().find("u"), "k3")
            self.assertIsNone(await self.client().find("nada"))

    async def test_create_without_any_uuid(self):
        from bot.services.changedetection import ChangeDetectionError

        def handler(request):
            return httpx.Response(200, json={"ok": True} if request.method == "POST" else [])

        with fake_http(handler), self.assertRaises(ChangeDetectionError):
            await self.client().create("u", "T", FakeSchedule(False))

    async def test_errors(self):
        from bot.services.changedetection import ChangeDetectionError

        def down(request):
            raise httpx.ConnectError("sin red")

        with fake_http(down), self.assertRaisesRegex(ChangeDetectionError, "no responde: sin red"):
            await self.client().find("u")
        with fake_http(lambda request: httpx.Response(403, text="bad key")), \
                self.assertRaisesRegex(ChangeDetectionError, "HTTP 403: bad key"):
            await self.client().delete("abc")


if __name__ == "__main__":
    unittest.main()
