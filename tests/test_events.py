"""Avisos de Anime-Automator: el endpoint /events y lo que Kuro cuenta de cada uno."""

from aiohttp.test_utils import TestClient, TestServer

from bot.core.models import Status
from bot.events.server import EventServer
from bot.handlers.orders import Decision, Pick
from tests.test_flows import ADMIN, CLIENT, KuroTest, said


class TestEndpoint(KuroTest):
    async def asyncSetUp(self):
        self.server = EventServer(self.k.events, "s3cret", 0)
        self.http = TestClient(TestServer(self.server.app()))
        await self.http.start_server()
        self.addAsyncCleanup(self.http.close)

    async def post(self, body, secret="s3cret", **kw):
        return await self.http.post("/events", headers={"X-Callback-Secret": secret}, **kw,
                                    **({} if "data" in kw else {"json": body}))

    async def test_needs_the_secret(self):
        self.assertEqual((await self.post({}, secret="otro")).status, 403)
        self.assertEqual((await self.http.post("/events", json={})).status, 403)

    async def test_bad_json(self):
        r = await self.post(None, data=b"{no es json")
        self.assertEqual(r.status, 400)

    async def test_event_reaches_the_client(self):
        await self.press(Pick, CLIENT, "pick:11")
        await self.press(Decision, ADMIN, "ok:1", message=self.admin_request_msg())
        r = await self.post({"job_id": "1", "event": "episode_done", "episode": 1, "done": 1, "total": 2})
        self.assertEqual((r.status, await r.json()), (200, {"ok": True}))
        self.assertTrue(said("ep_done", self.bot.to(CLIENT)[-1].text))

    async def test_a_failure_still_answers_ok(self):
        async def broken(ev):
            raise RuntimeError("roto")
        self.k.events.route = broken
        with self.assertLogs("bot.events.server", "ERROR"):
            r = await self.post({"job_id": "1"})
        self.assertEqual(r.status, 200)   # un reintento solo duplicaría mensajes

    async def test_without_secret_nothing_is_accepted(self):
        server = EventServer(self.k.events, "", 0)
        with self.assertLogs("bot.events.server", "WARNING"):
            await server.start()           # ni siquiera escucha
        await server.stop()
        async with TestClient(TestServer(server.app())) as http:
            r = await http.post("/events", headers={"X-Callback-Secret": ""}, json={})
            self.assertEqual(r.status, 403)


class EventsTest(KuroTest):
    async def order(self, chat, post="11"):
        """Un pedido ya aprobado (en marcha); devuelve su id."""
        await self.press(Pick, chat, f"pick:{post}")
        rid = self.k.db.last_request_of(chat).id
        if chat != ADMIN:
            await self.press(Decision, ADMIN, f"ok:{rid}", message=self.admin_request_msg())
        return rid

    async def event(self, rid, event, **kw):
        self.n = {c: len(self.bot.to(c)) for c in (ADMIN, CLIENT)}
        await self.k.events.route({"job_id": str(rid), "event": event, **kw})

    def new(self, chat):
        return [m.text for m in self.bot.to(chat)[self.n[chat]:]]


class TestEpisodeProgress(EventsTest):
    def test_when_to_tell(self):
        from bot.events.handlers import worth_telling
        told = lambda total: [n for n in range(1, total + 1) if worth_telling(n, total)]
        self.assertEqual(told(2), [1])                   # el último lo cuenta el aviso de «completo»
        self.assertEqual(told(4), [1, 2, 3])
        self.assertEqual(told(12), [1, 3, 6, 9])
        self.assertEqual(told(24), [1, 6, 12, 18])
        self.assertEqual(told(100), [1, 25, 50, 75])
        self.assertTrue(worth_telling(7, None))          # sin total, como siempre: cada capítulo
        self.assertTrue(worth_telling(7, 0))

    async def test_a_big_order_gets_a_few_notices(self):
        rid = await self.order(CLIENT)
        self.n = {c: len(self.bot.to(c)) for c in (ADMIN, CLIENT)}
        for n in range(1, 13):
            await self.k.events.route({"job_id": str(rid), "event": "episode_done", "episode": n,
                                       "done": n, "total": 12})
        notices = self.new(CLIENT)
        self.assertEqual(len(notices), 4)
        self.assertTrue(said("ep_done", notices[0]))     # el primero: ya ha empezado
        self.assertTrue(all(said("ep_batch", t) for t in notices[1:]), notices)
        self.assertIn("6", notices[2])
        self.assertIn("12", notices[2])
        self.assertEqual(self.k.db.get(rid).eps_done, 12)   # el progreso se guarda siempre


class TestEpisodeFailed(EventsTest):
    async def test_client_series(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "episode_failed", episode=3, error="<timeout>", failed=1, total=2)
        (client,), (admin,) = self.new(CLIENT), self.new(ADMIN)
        self.assertTrue(said("ep_failed", client))
        self.assertNotIn("timeout", client)               # el detalle técnico, solo al miauestro
        self.assertTrue(said("admin_ep_failed", admin))
        self.assertIn("&lt;timeout&gt;", admin)
        self.assertEqual(self.k.db.get(rid).eps_failed, 1)

    async def test_client_movie(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "episode_failed", error="boom", kind="movie")
        self.assertEqual(self.new(CLIENT), [])            # ya se le avisa al final (job_complete)
        (admin,) = self.new(ADMIN)
        self.assertTrue(said("admin_movie_failed", admin))

    async def test_admin_series(self):
        rid = await self.order(ADMIN)
        await self.event(rid, "episode_failed", episode=3, error="boom")
        (text,) = self.new(ADMIN)                         # un solo aviso, con el detalle
        self.assertTrue(said("ep_failed", text))
        self.assertIn("<code>boom</code>", text)

    async def test_admin_movie(self):
        rid = await self.order(ADMIN)
        await self.event(rid, "episode_failed", error="boom", kind="movie")
        (text,) = self.new(ADMIN)
        self.assertTrue(said("movie_failed", text))
        self.assertIn("<code>boom</code>", text)


class TestJobComplete(EventsTest):
    async def test_everything_arrived(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "job_complete", done=[1, 2], failed=[])
        (client,), (admin,) = self.new(CLIENT), self.new(ADMIN)
        self.assertTrue(said("job_done_all", client))
        self.assertTrue(said("admin_job_done", admin))
        self.assertEqual(self.k.db.get(rid).status, Status.COMPLETED)

    async def test_some_failed(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "job_complete", done=[1], failed=[2, 3])
        self.assertTrue(said("job_done_partial", self.new(CLIENT)[0]))
        self.assertIn("(2-3)", self.new(ADMIN)[0])

    async def test_nothing_arrived(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "job_complete", done=[], failed=[1, 2])
        self.assertTrue(said("job_failed", self.new(CLIENT)[0]))
        self.assertEqual(self.k.db.get(rid).status, Status.FAILED)   # devuelve el carro
        self.assertTrue(said("admin_job_done", self.new(ADMIN)[0]))

    async def test_movie(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "job_complete", done=[1], failed=[], kind="movie")
        self.assertTrue(said("movie_done", self.new(CLIENT)[0]))
        rid = await self.order(CLIENT, post="12")
        await self.event(rid, "job_complete", done=[], failed=[1], kind="movie")
        self.assertTrue(said("movie_failed", self.new(CLIENT)[0]))
        self.assertNotIn("(1)", self.new(ADMIN)[0])       # en películas no se listan capítulos

    async def test_admin_movie_that_failed(self):
        rid = await self.order(ADMIN)
        await self.event(rid, "job_complete", done=[], failed=[1], kind="movie")
        self.assertEqual(self.new(ADMIN), [])             # ya se le dijo, con el detalle, en episode_failed


class TestCancelled(EventsTest):
    """Lo que el miauestro quita de la cola: un aviso por encargo, nunca uno por capítulo."""

    async def test_part_of_a_client_order(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "episodes_cancelled", episodes=[5, 6, 7, 9], done=0, failed=0, total=10)
        (client,) = self.new(CLIENT)
        self.assertTrue(said("ep_cancelled", client, boss=False), client)
        self.assertIn("5-7, 9", client)
        self.assertIn("miauestro", client)
        self.assertNotIn("administrador", client)
        self.assertEqual(self.new(ADMIN), [])             # lo ha hecho él: no hace falta contárselo

    async def test_part_of_the_boss_order(self):
        rid = await self.order(ADMIN)
        await self.event(rid, "episodes_cancelled", episodes=[2, 3], total=4)
        (text,) = self.new(ADMIN)
        self.assertTrue(said("ep_cancelled", text, boss=True), text)
        self.assertIn("2-3", text)

    async def test_a_whole_client_order(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "job_complete", done=[], failed=[], cancelled=[1, 2, 3])
        (client,) = self.new(CLIENT)
        self.assertTrue(said("job_cancelled", client, boss=False), client)
        self.assertEqual(self.new(ADMIN), [])
        self.assertEqual(self.k.db.get(rid).status, Status.FAILED)   # devuelve el carro

    async def test_a_whole_boss_order(self):
        rid = await self.order(ADMIN)
        await self.event(rid, "job_complete", done=[], failed=[], cancelled=[1, 2], kind="movie")
        (text,) = self.new(ADMIN)
        self.assertTrue(said("job_cancelled", text, boss=True), text)

    async def test_the_summary_tells_what_was_removed(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "job_complete", done=[1, 2], failed=[3], cancelled=[4, 5])
        (client,) = self.new(CLIENT)
        self.assertTrue(said("job_done_partial", client))
        self.assertIn("4-5", client)
        self.assertIn("miauestro", client)
        rid = await self.order(ADMIN, post="12")
        await self.event(rid, "job_complete", done=[1], failed=[], cancelled=[2])
        (text,) = self.new(ADMIN)
        self.assertTrue(said("job_done_all", text))
        self.assertIn("(2)", text)


class TestOtherEvents(EventsTest):
    async def test_retry_only_the_first_time(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "episode_retry", episode=2, attempt=1, delay="5 min")
        self.assertTrue(said("ep_retry", self.new(CLIENT)[0]))
        await self.event(rid, "episode_retry", episode=2, attempt=2)
        self.assertEqual(self.new(CLIENT), [])

    async def test_fallback_and_unknown(self):
        rid = await self.order(CLIENT)
        await self.event(rid, "episode_fallback", episode=2)
        self.assertTrue(said("ep_fallback", self.new(CLIENT)[0]))
        with self.assertLogs("bot.events.handlers", "WARNING"):
            await self.event(rid, "algo_nuevo")
        self.assertEqual(self.new(CLIENT), [])
        with self.assertLogs("bot.events.handlers", "WARNING"):
            await self.event("no-es-un-id", "episode_done")
