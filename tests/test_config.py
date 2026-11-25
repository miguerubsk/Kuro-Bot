"""Lectura de la configuración del entorno (.env)."""

import os
import unittest
from unittest import mock

from bot import config

REQUIRED = {"TELEGRAM_BOT_TOKEN": "123:abc", "ADMIN_CHAT_ID": "1000"}


def load(**env):
    with mock.patch.dict(os.environ, {**REQUIRED, **env}, clear=True):
        return config.load()


class TestLoad(unittest.TestCase):
    def load_fails(self, **env) -> str:
        """Mensaje con el que se para el arranque."""
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(SystemExit) as cm:
            config.load()
        return str(cm.exception.code)

    def test_defaults(self):
        cfg = load()
        self.assertEqual((cfg.token, cfg.admin_chat_id), ("123:abc", 1000))
        self.assertEqual(cfg.allowed_chat_ids, frozenset())
        self.assertEqual(cfg.weekly_limit, 3)
        self.assertEqual(cfg.automator_url, "http://anime-automator:5000")
        self.assertFalse(cfg.force_browser)
        self.assertEqual(cfg.events_port, 8080)
        self.assertEqual(cfg.tracking_sources, frozenset({"changedetection", "drive"}))
        self.assertEqual((cfg.tracking_limit, cfg.tracking_window_hours, cfg.tracking_check_minutes), (2, 24, 60))
        self.assertEqual(cfg.torrent_access, "admin")
        self.assertEqual(cfg.blocked_anime, ("One Piece", "Naruto"))

    def test_values_from_the_env(self):
        cfg = load(ALLOWED_CHAT_IDS="1; 2,3 ,", WEEKLY_LIMIT="5", ANIME_AUTOMATOR_URL="http://aa:1/",
                   FORCE_BROWSER="Yes", CHANGEDETECTION_URL=" http://cd/ ", TRACKING_SOURCES="Drive",
                   TORRENT_ACCESS=" ALL ", BLOCKED_ANIME="Bleach, ", TRACKING_CHECK_MINUTES="",
                   ACCESS_KEYWORD=" gato ")
        self.assertEqual(cfg.allowed_chat_ids, frozenset({1, 2, 3}))
        self.assertEqual(cfg.weekly_limit, 5)
        self.assertEqual(cfg.automator_url, "http://aa:1")
        self.assertTrue(cfg.force_browser)
        self.assertEqual(cfg.cd_url, "http://cd")
        self.assertEqual(cfg.tracking_sources, frozenset({"drive"}))
        self.assertEqual(cfg.torrent_access, "all")
        self.assertEqual(cfg.blocked_anime, ("Bleach",))
        self.assertEqual(cfg.tracking_check_minutes, 60)   # vacío: el de siempre
        self.assertEqual(cfg.access_keyword, "gato")

    def test_missing_required(self):
        msg = self.load_fails(ADMIN_CHAT_ID="1")
        self.assertIn("TELEGRAM_BOT_TOKEN", msg)
        self.assertNotIn("ADMIN_CHAT_ID", msg)
        msg = self.load_fails()
        self.assertIn("TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID", msg)

    def test_numbers_must_be_numbers(self):
        self.assertIn("deben ser números", self.load_fails(**REQUIRED, ALLOWED_CHAT_IDS="1,dos"))
        self.assertIn("deben ser números", self.load_fails(**REQUIRED, WEEKLY_LIMIT="tres"))

    def test_only_known_choices(self):
        self.assertIn("sobra: ftp", self.load_fails(**REQUIRED, TRACKING_SOURCES="drive,ftp"))
        self.assertIn("no «nadie»", self.load_fails(**REQUIRED, TORRENT_ACCESS="nadie"))
