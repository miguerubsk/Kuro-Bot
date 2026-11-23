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
    # seguimiento semanal de lo que está en emisión (change-detection.io); sin URL o clave, desactivado
    cd_url: str = ""
    cd_api_key: str = ""
    cd_tag: str = "kuro"
    cd_fetch_backend: str = ""
    cd_notify_url: str = ""
    tracking_limit: int = 2
    tracking_window_hours: int = 24    # como mucho 24 (Schedule.MAX_HOURS)
    # quién vigila: change-detection (la página de pastes) y/o Anime-Automator (la unidad de Drive)
    tracking_sources: frozenset = frozenset({"changedetection", "drive"})
    tracking_check_minutes: int = 60
    # proxy para cuando la web nos bloquea (p. ej. Tor: socks5://host:9050); vacío = sin proxy
    bypass_proxy: str = ""
    # pedir por torrent lo que no está en la web: off, admin (solo el miauestro) o all
    torrent_access: str = "admin"


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
            cd_url=os.environ.get("CHANGEDETECTION_URL", "").strip().rstrip("/"),
            cd_api_key=os.environ.get("CHANGEDETECTION_API_KEY", "").strip(),
            cd_tag=os.environ.get("CHANGEDETECTION_TAG", "kuro").strip(),
            cd_fetch_backend=os.environ.get("CHANGEDETECTION_FETCH_BACKEND", "").strip(),
            cd_notify_url=os.environ.get("CHANGEDETECTION_NOTIFY_URL", "").strip(),
            tracking_limit=int(os.environ.get("TRACKING_LIMIT", "2") or 2),
            tracking_window_hours=int(os.environ.get("TRACKING_WINDOW_HOURS", "24") or 24),
            tracking_sources=_sources(os.environ.get("TRACKING_SOURCES", "changedetection,drive")),
            bypass_proxy=os.environ.get("BLOCK_BYPASS_PROXY", "").strip(),
            tracking_check_minutes=int(os.environ.get("TRACKING_CHECK_MINUTES", "60") or 60),
            torrent_access=_torrent_access(os.environ.get("TORRENT_ACCESS", "admin")),
        )
    except ValueError as e:
        sys.exit(f"Valor inválido en el .env (los ids de chat, WEEKLY_LIMIT y TRACKING_* deben ser números): {e}")


TRACKING_SOURCES = ("changedetection", "drive")


def _sources(raw: str) -> frozenset:
    out = frozenset(x.strip().lower() for x in raw.split(",") if x.strip())
    bad = out - set(TRACKING_SOURCES)
    if bad:
        sys.exit(f"TRACKING_SOURCES solo admite {', '.join(TRACKING_SOURCES)} (sobra: {', '.join(sorted(bad))})")
    return out


TORRENT_ACCESS = ("off", "admin", "all")


def _torrent_access(raw: str) -> str:
    value = (raw or "admin").strip().lower()
    if value not in TORRENT_ACCESS:
        sys.exit(f"TORRENT_ACCESS solo admite {', '.join(TORRENT_ACCESS)} (no «{value}»)")
    return value
