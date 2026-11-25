"""Buzón de salida: los avisos que no se pudieron entregar se reenvían luego, en orden."""

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError

from bot.messaging import messenger as m
from tests.test_flows import ADMIN, CLIENT, FakeBot, KuroTest


class FlakyBot(FakeBot):
    """Falla con cada error de `errors` (None = entrega), uno por envío."""
    def __init__(self, *errors):
        super().__init__()
        self.errors = list(errors)

    async def send_message(self, chat_id, text, **kw):
        if self.errors:
            ex = self.errors.pop(0)
            if ex is not None:
                raise ex
        return self._record(chat_id, text, kw)


class OutboxTest(KuroTest):
    def setUp(self):
        super().setUp()
        self.k.messenger.attach(None)          # sin Telegram: todo va al buzón
        self.slept = []

        async def sleep(seconds):
            self.slept.append(seconds)
        p = mock.patch.object(m, "asyncio", SimpleNamespace(sleep=sleep))
        p.start()
        self.addCleanup(p.stop)

    async def queue(self, *items):
        for chat, text in items:
            await self.k.messenger.send(chat, text)

    def pending(self):
        return [t for _, _, t, _ in self.k.db.outbox_items()]

    async def flush(self, bot):
        self.k.messenger.attach(bot)
        await self.k.messenger.flush_outbox()


class TestOutbox(OutboxTest):
    async def test_without_bot_everything_waits(self):
        await self.queue((CLIENT, "uno"))
        await self.k.messenger.flush_outbox()
        self.assertEqual(self.pending(), ["uno"])

    async def test_buttons_are_not_kept(self):
        await self.k.messenger.send(CLIENT, "con botones", reply_markup=object())
        self.assertEqual(self.pending(), [])

    async def test_permanent_errors_are_dropped_and_the_rest_go_on(self):
        await self.queue((CLIENT, "uno"), (ADMIN, "dos"), (CLIENT, "tres"), (ADMIN, "cuatro"))
        bot = FlakyBot(BadRequest("chat not found"), Forbidden("blocked"), TelegramError("raro"))
        await self.flush(bot)
        self.assertEqual([x.text for x in bot.sent], ["cuatro"])
        self.assertEqual(self.pending(), [])

    async def test_still_offline_keeps_everything_in_order(self):
        await self.queue((CLIENT, "uno"), (CLIENT, "dos"))
        bot = FlakyBot(None, NetworkError("sin red"))
        await self.flush(bot)
        self.assertEqual([x.text for x in bot.sent], ["uno"])
        self.assertEqual(self.pending(), ["dos"])

    async def test_too_many_requests_waits_what_telegram_says(self):
        await self.queue((CLIENT, "uno"), (CLIENT, "dos"))
        for wait, expected in ((7, 7.0), (timedelta(seconds=3), 3.0)):
            with self.subTest(wait=wait):
                ex = RetryAfter(7)
                ex.retry_after = wait     # según la versión de la librería, segundos o timedelta
                await self.flush(FlakyBot(ex))
                self.assertEqual(self.slept[-1], expected)
                self.assertEqual(self.pending(), ["uno", "dos"])
        await self.flush(FlakyBot())
        self.assertEqual(self.pending(), [])

    async def test_a_week_old_notice_is_dropped(self):
        await self.queue((CLIENT, "viejo"))
        later = time.time() + m.Messenger.OUTBOX_MAX_AGE + 60
        bot = FlakyBot()
        with mock.patch.object(m, "time", SimpleNamespace(time=lambda: later)):
            with self.assertLogs("bot.messaging.messenger", "ERROR"):
                await self.flush(bot)
        self.assertEqual((bot.sent, self.pending()), ([], []))


class TestSend(OutboxTest):
    async def test_offline_notice_with_buttons_is_lost(self):
        self.k.messenger.attach(FlakyBot(NetworkError("sin red")))
        with self.assertLogs("bot.messaging.messenger", "WARNING"):
            await self.k.messenger.send(CLIENT, "¿lo vigilo?", reply_markup=object())
        self.assertEqual(self.pending(), [])     # un botón viejo, días después, no tendría sentido

    async def test_other_telegram_errors_are_not_retried(self):
        self.k.messenger.attach(FlakyBot(TelegramError("raro")))
        with self.assertLogs("bot.messaging.messenger", "WARNING"):
            await self.k.messenger.send(CLIENT, "uno")
        self.assertEqual(self.pending(), [])

    async def test_waits_behind_older_notices(self):
        await self.queue((CLIENT, "uno"))
        bot = FlakyBot()
        self.k.messenger.attach(bot)
        await self.k.messenger.send(CLIENT, "dos")
        self.assertEqual((bot.sent, self.pending()), ([], ["uno", "dos"]))
        await self.k.messenger.send(ADMIN, "a otro chat no le afecta")
        self.assertEqual(len(bot.sent), 1)
