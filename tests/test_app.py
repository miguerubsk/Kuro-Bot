"""Arranque y apagado de Kuro, y las visitas del miauestro."""

import asyncio
from types import SimpleNamespace

from telegram.error import TelegramError

from bot import lonely
from bot.app import ADMIN_COMMANDS, USER_COMMANDS, KuroBot, startup_summary
from bot.core.models import Status
from bot.services.japanpaw import PostInfo
from tests.test_flows import ADMIN, CLIENT, FakeBot, KuroTest, said, settings


class CommandBot(FakeBot):
    def __init__(self, admin_fails=False):
        super().__init__()
        self.commands = []
        self.admin_fails = admin_fails

    async def set_my_commands(self, commands, scope=None):
        if scope is not None and self.admin_fails:
            raise TelegramError("sin permiso")
        self.commands.append((commands, scope.chat_id if scope else None))


class TestLifecycle(KuroTest):
    async def start(self, bot):
        self.app = KuroBot(self.k)
        application = SimpleNamespace(bot=bot)
        await self.app.post_init(application)
        self.addAsyncCleanup(self.app.post_shutdown, application)
        return self.app

    async def test_start_warns_of_orders_cut_halfway(self):
        post = PostInfo(11, "Frieren", "u", "p", "11", False, "")
        rid = self.k.db.add(CLIENT, "Ana", post, Status.PROCESSING)
        bot = CommandBot()
        await self.start(bot)
        self.assertEqual(self.k.db.get(rid).status, Status.FAILED)
        (warning,) = bot.to(ADMIN)
        self.assertIn(f"#{rid}", warning.text)
        self.assertIn("<b>Frieren</b>", warning.text)
        self.assertIn("/pendientes", warning.text)
        self.assertEqual(bot.commands, [(USER_COMMANDS, None), (ADMIN_COMMANDS, ADMIN)])

    async def test_admin_commands_are_optional(self):
        bot = CommandBot(admin_fails=True)
        with self.assertLogs("requester-bot", "WARNING"):
            await self.start(bot)
        self.assertEqual(bot.commands, [(USER_COMMANDS, None)])
        self.assertFalse(bot.sent)

    async def test_shutdown_stops_the_background_work(self):
        app = await self.start(CommandBot())
        tasks = list(app._tasks)
        self.assertEqual(len(tasks), 3)
        await app.post_shutdown(SimpleNamespace(bot=None))
        await asyncio.sleep(0)
        self.assertTrue(all(t.cancelled() for t in tasks))


class TestAdminVisits(KuroTest):
    def update(self, chat_id, text="", query=None):
        if chat_id is None:
            return SimpleNamespace(effective_chat=None)
        return super().update(chat_id, text, query)

    async def visit(self, chat_id):
        await KuroBot(self.k).track_admin(self.update(chat_id), self.ctx(ADMIN))

    async def test_only_the_admin_counts(self):
        self.k.db.kv_set(lonely.K_LEVEL, 1)          # Kuro le echaba de menos
        await self.visit(CLIENT)
        await self.visit(None)                       # p. ej. un cambio en un canal
        self.assertFalse(self.bot.sent)
        await self.visit(ADMIN)
        self.assertTrue(said("lonely_back", self.bot.to(ADMIN)[-1].text))

    async def test_a_failure_does_not_stop_the_update(self):
        async def broken():
            raise RuntimeError("BD rota")
        self.k.lonely.touch = broken
        with self.assertLogs("requester-bot", "ERROR"):
            await self.visit(ADMIN)


class TestStartupSummary(KuroTest):
    def test_who_watches(self):
        cfg = settings(self.tmp.name, tracking_sources=frozenset({"changedetection", "drive"}),
                       cd_url="http://cd", cd_api_key="k", tracking_check_minutes=30, tracking_window_hours=48)
        tracking, kuro = startup_summary(cfg)
        self.assertEqual(tracking, "Seguimiento semanal: change-detection en http://cd cada 30 min + "
                                   "el Drive (Anime-Automator); ventana de 24 h")
        self.assertEqual(kuro, f"Arrancando Kuro (admin={ADMIN}, lista blanca=1, palabra clave=no, "
                               f"límite=3/semana, torrent=admin)")

    def test_changedetection_without_credentials(self):
        tracking, _ = startup_summary(settings(self.tmp.name, access_keyword="gato"))
        self.assertIn("change-detection NO (faltan", tracking)
        self.assertNotIn("Drive", tracking)
        self.assertIn("palabra clave=sí", startup_summary(settings(self.tmp.name, access_keyword="gato"))[1])

    def test_nobody_watches(self):
        tracking, _ = startup_summary(settings(self.tmp.name, tracking_sources=frozenset()))
        self.assertTrue(tracking.startswith("Seguimiento semanal: desactivado;"))
