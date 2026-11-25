"""Kuro echa de menos al miauestro: cuándo le escribe, qué le dice y cómo le recibe."""

from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from bot import lonely
from bot.core.models import Status
from bot.persona import TZ
from bot.services.japanpaw import PostInfo
from tests.test_flows import ADMIN, CLIENT, KuroTest, said

DAY, HOUR = lonely.DAY, 3600
START = datetime(2026, 11, 2, 12, 0, tzinfo=TZ).timestamp()   # lunes a mediodía


class Clock:
    def __init__(self, now: float):
        self.now = now

    def time(self) -> float:
        return self.now

    def local(self) -> datetime:
        return datetime.fromtimestamp(self.now, TZ)


class StopLoop(Exception):
    pass


class LonelyTest(KuroTest):
    def setUp(self):
        super().setUp()
        self.clock = Clock(START)
        self.sent_at: list[float] = []   # cuándo llegó cada mensaje al miauestro
        # el azar, siempre en su extremo más bajo: así se sabe cuándo toca cada cosa
        fixed = SimpleNamespace(uniform=lambda a, b: a, randint=lambda a, b: a, random=lambda: 0.0,
                                choice=lambda xs: xs[0])
        for target, value in (("time", self.clock), ("_now_local", self.clock.local), ("random", fixed)):
            p = mock.patch.object(lonely, target, value)
            p.start()
            self.addCleanup(p.stop)
        send = self.k.lonely.send

        async def timed_send(chat_id, text):
            self.sent_at.append(self.clock.now)
            await send(chat_id, text)
        self.k.lonely.send = timed_send

    async def wait(self, seconds: float, step: float = HOUR):
        """Deja correr el bucle de Kuro `seconds` segundos (cada vuelta, `step`)."""
        until = self.clock.now + seconds

        async def sleep(_):
            if self.clock.now >= until:
                raise StopLoop
            self.clock.now += step
        with mock.patch.object(lonely, "asyncio", SimpleNamespace(sleep=sleep)):
            with self.assertRaises(StopLoop):
                await self.k.lonely.loop()

    async def visit(self, at: float | None = None):
        if at is not None:
            self.clock.now = at
        await self.k.lonely.touch()

    def to_admin(self):
        return [m.text for m in self.bot.to(ADMIN)]


class TestMissing(LonelyTest):
    async def test_gets_more_dramatic_and_then_shuts_up(self):
        await self.visit()
        await self.wait(120 * DAY)
        texts = self.to_admin()
        self.assertEqual(len(texts), lonely.LEVELS)
        for level, text in enumerate(texts, 1):
            self.assertTrue(said(f"lonely_{level}", text), (level, text))
        # sin historial, el primero llega a los 4 días (2 días de media × 2) y siempre de día
        self.assertEqual(self.sent_at[0], START + 4 * DAY)
        for ts in self.sent_at:
            self.assertGreaterEqual(datetime.fromtimestamp(ts, TZ).hour, lonely.AWAKE_HOURS[0])
        self.assertTrue(all(b - a >= lonely.MIN_WAIT for a, b in zip(self.sent_at, self.sent_at[1:])))

    async def test_mentions_what_happened_meanwhile(self):
        await self.visit()
        post = PostInfo(1, "Frieren", "u", "p", "1", False, "")
        self.k.db.add(ADMIN, "Miauestro", post, Status.COMPLETED)
        self.k.db.add(CLIENT, "Ana (@ana)", PostInfo(2, "Dandadan", "u", "p", "2", False, ""), Status.COMPLETED)
        await self.wait(5 * DAY)
        (text,) = self.to_admin()
        first, extra = text.split("\n\n", 1)
        self.assertTrue(said("lonely_1", first))
        self.assertTrue(said("lonely_clients", extra))
        self.assertIn("Ana", extra)
        self.assertNotIn("@ana", extra)

    async def test_without_clients_remembers_his_last_order(self):
        await self.visit()
        self.k.db.add(ADMIN, "Miauestro", PostInfo(1, "Frieren", "u", "p", "1", False, ""), Status.COMPLETED)
        await self.wait(5 * DAY)
        extra = self.to_admin()[-1].split("\n\n", 1)[1]
        self.assertTrue(said("lonely_last_title", extra))
        self.assertIn("Frieren", extra)

    async def test_with_nothing_to_tell_he_tells_what_he_did(self):
        await self.visit()
        await self.wait(5 * DAY)
        extra = self.to_admin()[-1].split("\n\n", 1)[1]
        self.assertTrue(said("lonely_meanwhile", extra))

    async def test_never_writes_at_night(self):
        await self.visit(START + 11 * HOUR)                    # le tocará a las 23:00 dentro de 4 días…
        await self.wait(4 * DAY + 3 * HOUR, step=4 * DAY + 3 * HOUR)   # …pero se despierta a las 2:00
        self.assertFalse(self.to_admin())
        await self.wait(5 * HOUR)                              # espera a la mañana
        self.assertEqual(len(self.to_admin()), 1)
        self.assertEqual(datetime.fromtimestamp(self.sent_at[0], TZ).hour, lonely.AWAKE_HOURS[0])

    async def test_a_failure_does_not_stop_him(self):
        await self.visit()
        calls = []
        send = self.k.lonely.send

        async def flaky(chat_id, text):
            calls.append(text)
            if len(calls) == 1:
                raise RuntimeError("sin red")
            await send(chat_id, text)
        self.k.lonely.send = flaky
        with self.assertLogs("bot.lonely", "ERROR"):
            await self.wait(5 * DAY)
        self.assertEqual(len(calls), 2)                   # lo vuelve a intentar en la vuelta siguiente
        self.assertEqual(len(self.to_admin()), 1)

    async def test_first_start_without_visits_plans_from_now(self):
        await self.wait(3 * DAY)
        self.assertFalse(self.to_admin())
        await self.wait(2 * DAY)
        self.assertEqual(len(self.to_admin()), 1)


class TestWelcomeBack(LonelyTest):
    async def reach(self, level: int):
        await self.visit()
        while len(self.to_admin()) < level:
            await self.wait(DAY)

    async def test_no_fuss_if_he_was_not_missed(self):
        await self.visit()
        await self.visit(START + 2 * DAY)
        self.assertFalse(self.to_admin())

    async def welcome(self, level: int, key: str):
        await self.reach(level)
        await self.visit()
        self.assertTrue(said(key, self.to_admin()[-1]), self.to_admin()[-1])
        n = len(self.to_admin())
        await self.visit(self.clock.now + 2 * HOUR)    # ya está contento: no lo repite
        self.assertEqual(len(self.to_admin()), n)

    async def test_a_bit_missed(self):
        await self.welcome(1, "lonely_back")

    async def test_hurt(self):
        await self.welcome(3, "lonely_back_hurt")

    async def test_drama(self):
        await self.welcome(lonely.LEVELS, "lonely_back_drama")

    async def test_learns_how_often_he_comes(self):
        # viene cada 4 días (varias veces seguidas cuentan como una): le espera el doble, 8 días
        for at in (0, 4 * DAY, 4 * DAY + 10 * 60, 4 * DAY + 20 * 60, 8 * DAY, 12 * DAY):
            await self.visit(START + at)
        await self.wait(8 * DAY - HOUR)
        self.assertFalse(self.to_admin())
        await self.wait(2 * HOUR)
        self.assertEqual(self.sent_at, [START + 20 * DAY])

    async def test_short_visits_do_not_shrink_the_wait(self):
        # tres ratos cortos (menos de una hora) no son «ratos sin hablar»: sigue la media por defecto
        for at in (0, 10 * 60, 20 * 60, 30 * 60, 40 * 60):
            await self.visit(START + at)
        await self.wait(4 * DAY + HOUR)
        self.assertEqual(len(self.to_admin()), 1)
        self.assertEqual(self.sent_at[0], START + 40 * 60 + 4 * DAY)
