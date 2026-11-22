"""Configuración leída del entorno (.env)."""

import os
import sys
from dataclasses import dataclass


def _int_set(raw: str) -> frozenset[int]:
    out = set()
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.add(int(part))
    return frozenset(out)


@dataclass(frozen=True)
class Settings:
    token: str
    admin_chat_id: int
    allowed_chat_ids: frozenset[int]
    access_keyword: str
    weekly_limit: int
    automator_url: str
    sockpuppet_url: str
    japanpaw_base: str
    force_browser: bool
    data_dir: str
    callback_secret: str
    events_port: int


def load() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    admin = os.environ.get("ADMIN_CHAT_ID", "").strip()
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", token), ("ADMIN_CHAT_ID", admin)) if not v]
    if missing:
        sys.exit(f"Faltan variables obligatorias en el .env: {', '.join(missing)}")
    try:
        return Settings(
            token=token,
            admin_chat_id=int(admin),
            allowed_chat_ids=_int_set(os.environ.get("ALLOWED_CHAT_IDS", "")),
            access_keyword=os.environ.get("ACCESS_KEYWORD", "").strip(),
            weekly_limit=int(os.environ.get("WEEKLY_LIMIT", "3") or 3),
            automator_url=os.environ.get("ANIME_AUTOMATOR_URL", "http://anime-automator:5000").rstrip("/"),
            sockpuppet_url=os.environ.get("SOCKPUPPET_URL", "ws://browser-sockpuppet-chrome:3000"),
            japanpaw_base=os.environ.get("JAPANPAW_BASE", "https://japanpaw.com").rstrip("/"),
            force_browser=os.environ.get("FORCE_BROWSER", "0").strip().lower() in ("1", "true", "yes"),
            data_dir=os.environ.get("DATA_DIR", "/data"),
            callback_secret=os.environ.get("CALLBACK_SECRET", "").strip(),
            events_port=int(os.environ.get("EVENTS_PORT", "8080") or 8080),
        )
    except ValueError as e:
        sys.exit(f"Valor inválido en el .env (los ids de chat y WEEKLY_LIMIT deben ser números): {e}")
