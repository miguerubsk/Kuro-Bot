"""Persistencia en SQLite: peticiones, chats dados de alta, avisos pendientes y valores sueltos."""

import json
import os
import sqlite3
import threading
import time

from .models import Request, Status, Tracking, TrackStatus

WEEK = 7 * 24 * 3600

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    post_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    post_url TEXT NOT NULL,
    paste_url TEXT NOT NULL,
    airing INTEGER NOT NULL DEFAULT 0,
    label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    decided_at REAL,
    admin_msg_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_requests_chat ON requests(chat_id, created_at);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trackings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    post_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    post_url TEXT NOT NULL,
    paste_url TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    decided_at REAL,
    watch_uuid TEXT NOT NULL DEFAULT '',
    owned INTEGER NOT NULL DEFAULT 0,
    anilist_id INTEGER NOT NULL DEFAULT 0,
    schedule TEXT NOT NULL DEFAULT '',
    request_id INTEGER NOT NULL DEFAULT 0,
    watch_title TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_trackings_paste ON trackings(paste_url, status);
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    registered_at REAL NOT NULL
);
"""
# columnas añadidas después de la primera versión
_LATE_COLUMNS = ("eps_total", "eps_done", "eps_failed", "quota_exempt", "movie", "bundle_id", "anilist_id")
_LATE_TEXT_COLUMNS = ("source", "season")


def _marks(values) -> str:
    return ",".join("?" * len(values))


class Storage:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        self._db = sqlite3.connect(os.path.join(data_dir, "requester.db"), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)
            cols = {r[1] for r in self._db.execute("PRAGMA table_info(requests)")}
            for col in _LATE_COLUMNS:
                if col not in cols:
                    self._db.execute(f"ALTER TABLE requests ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            for col in _LATE_TEXT_COLUMNS:
                if col not in cols:
                    self._db.execute(f"ALTER TABLE requests ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            tcols = {r[1] for r in self._db.execute("PRAGMA table_info(trackings)")}
            if "watch_title" not in tcols:   # el título de la ficha (carpeta en el Drive y en la biblioteca)
                self._db.execute("ALTER TABLE trackings ADD COLUMN watch_title TEXT NOT NULL DEFAULT ''")

    # ------------------------------------------------------------ acceso
    def _write(self, sql: str, args=()) -> sqlite3.Cursor:
        with self._lock, self._db:
            return self._db.execute(sql, args)

    def _rows(self, sql: str, args=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _first(self, sql: str, args=()) -> sqlite3.Row | None:
        with self._lock:
            return self._db.execute(sql, args).fetchone()

    @staticmethod
    def _request(r) -> Request | None:
        if r is None:
            return None
        return Request(
            id=r["id"], chat_id=r["chat_id"], user_name=r["user_name"], post_id=r["post_id"],
            title=r["title"], post_url=r["post_url"], paste_url=r["paste_url"],
            airing=bool(r["airing"]), label=r["label"], status=r["status"],
            created_at=r["created_at"], admin_msg_id=r["admin_msg_id"],
            eps_total=r["eps_total"], eps_done=r["eps_done"], eps_failed=r["eps_failed"],
            movie=bool(r["movie"]), bundle_id=r["bundle_id"], quota_exempt=bool(r["quota_exempt"]),
            source=r["source"], anilist_id=r["anilist_id"], season=r["season"],
        )

    def _request_one(self, sql: str, args=()) -> Request | None:
        return self._request(self._first(sql, args))

    def _request_all(self, sql: str, args=()) -> list[Request]:
        return [self._request(r) for r in self._rows(sql, args)]

    # ------------------------------------------- chats con palabra clave
    def is_registered(self, chat_id: int) -> bool:
        return self._first("SELECT 1 FROM chats WHERE chat_id=?", (chat_id,)) is not None

    def register(self, chat_id: int, name: str):
        self._write("INSERT OR REPLACE INTO chats(chat_id, name, registered_at) VALUES (?,?,?)",
                    (chat_id, name, time.time()))

    # --------------------------------------------------------- peticiones
    def add(self, chat_id, user_name, post, status, bundle_id: int = 0, quota_exempt: bool = False) -> int:
        """`post` es un PostInfo de la web o un TorrentPost (que trae source, anilist_id y season)."""
        cur = self._write(
            """INSERT INTO requests(chat_id, user_name, post_id, title, post_url, paste_url,
                                    airing, label, status, created_at, movie, bundle_id, quota_exempt,
                                    source, anilist_id, season)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (chat_id, user_name, post.post_id, post.title, post.url, post.paste_url,
             int(post.airing), post.label, status, time.time(), int(getattr(post, "movie", False)),
             bundle_id, int(quota_exempt), getattr(post, "source", ""), getattr(post, "anilist_id", 0),
             getattr(post, "season", "")),
        )
        return cur.lastrowid

    def set_season(self, req_id: int, season: str):
        self._write("UPDATE requests SET season=? WHERE id=?", (season, req_id))

    def get(self, req_id: int) -> Request | None:
        return self._request_one("SELECT * FROM requests WHERE id=?", (req_id,))

    def new_bundle_id(self) -> int:
        return int(self._first("SELECT COALESCE(MAX(bundle_id), 0) + 1 FROM requests")[0])

    def bundle(self, bundle_id: int) -> list[Request]:
        return self._request_all("SELECT * FROM requests WHERE bundle_id=? ORDER BY id", (bundle_id,))

    def set_admin_msg(self, req_id: int, msg_id: int):
        self._write("UPDATE requests SET admin_msg_id=? WHERE id=?", (msg_id, req_id))

    def set_status(self, req_id: int, status: str):
        self._write("UPDATE requests SET status=?, decided_at=? WHERE id=?", (status, time.time(), req_id))

    def transition(self, req_id: int, from_states: tuple[str, ...], to_state: str) -> bool:
        """Cambia el estado solo si está en uno de from_states (evita dobles decisiones)."""
        cur = self._write(
            f"UPDATE requests SET status=?, decided_at=? WHERE id=? AND status IN ({_marks(from_states)})",
            (to_state, time.time(), req_id, *from_states),
        )
        return cur.rowcount == 1

    def set_progress(self, req_id: int, total=None, done=None, failed=None):
        self._write(
            "UPDATE requests SET eps_total=COALESCE(?, eps_total), eps_done=COALESCE(?, eps_done), "
            "eps_failed=COALESCE(?, eps_failed) WHERE id=?",
            (total, done, failed, req_id),
        )

    def active_for_post(self, chat_id: int, post_id: int) -> Request | None:
        return self._request_one(
            f"SELECT * FROM requests WHERE chat_id=? AND post_id=? AND status IN ({_marks(Status.ACTIVE)})",
            (chat_id, post_id, *Status.ACTIVE),
        )

    def pending(self, limit: int = 20) -> list[Request]:
        return self._request_all(
            f"SELECT * FROM requests WHERE status IN ({_marks(Status.OPEN)}) ORDER BY created_at LIMIT ?",
            (*Status.OPEN, limit),
        )

    def requests_since(self, since: float, exclude_chat: int | None = None) -> list[Request]:
        return self._request_all(
            "SELECT * FROM requests WHERE created_at>=? AND chat_id IS NOT ? ORDER BY created_at",
            (since, exclude_chat),
        )

    def last_request_of(self, chat_id: int) -> Request | None:
        return self._request_one(
            "SELECT * FROM requests WHERE chat_id=? ORDER BY created_at DESC LIMIT 1", (chat_id,))

    def fail_stuck_processing(self) -> list[Request]:
        """
        Una petición en 'processing' al arrancar es que el bot se cortó mientras
        la enviaba a Anime-Automator: se pasa a 'failed' para que el admin la
        pueda reintentar (aparece en /pendientes con el botón de reintentar).
        """
        with self._lock, self._db:
            rows = self._db.execute("SELECT * FROM requests WHERE status=?", (Status.PROCESSING,)).fetchall()
            self._db.execute("UPDATE requests SET status=?, decided_at=? WHERE status=?",
                             (Status.FAILED, time.time(), Status.PROCESSING))
        return [self._request(r) for r in rows]

    # -------------------------------------------------------------- cupo
    def _counted_since(self, chat_id: int, since: float) -> list[float]:
        rows = self._rows(
            f"SELECT MIN(created_at) AS created_at FROM requests WHERE chat_id=? AND created_at>=? "
            f"AND quota_exempt=0 AND status IN ({_marks(Status.COUNTED)}) "
            f"GROUP BY CASE WHEN bundle_id > 0 THEN -bundle_id ELSE id END ORDER BY created_at",
            (chat_id, since, *Status.COUNTED),
        )
        return [r["created_at"] for r in rows]

    def used_this_week(self, chat_id: int) -> int:
        return len(self._counted_since(chat_id, time.time() - WEEK))

    def next_slot(self, chat_id: int, limit: int) -> float | None:
        """Momento en que vuelve a quedar un hueco (None si ya lo hay)."""
        times = self._counted_since(chat_id, time.time() - WEEK)
        if len(times) < limit:
            return None
        return times[len(times) - limit] + WEEK

    def reset_quota(self, chat_id: int | None = None) -> int:
        """Deja de contar para el cupo todas las peticiones hechas hasta ahora (de un chat o de todos)."""
        if chat_id is None:
            return self._write("UPDATE requests SET quota_exempt=1 WHERE quota_exempt=0").rowcount
        return self._write("UPDATE requests SET quota_exempt=1 WHERE quota_exempt=0 AND chat_id=?",
                           (chat_id,)).rowcount

    # ---------------------------------------------------------- historial
    def history(self, chat_id: int) -> list[Request]:
        """Lo que ha pedido ese chat y se ha bajado (o se está bajando), sin repetir post."""
        rows = self._request_all(
            f"SELECT * FROM requests WHERE chat_id=? AND status IN ({_marks(Status.HISTORY)}) "
            f"ORDER BY created_at DESC", (chat_id, *Status.HISTORY))
        best: dict[int, Request] = {}
        for r in rows:
            prev = best.get(r.post_id)
            # el completado manda sobre un intento anterior a medias
            if prev is None or (prev.status != Status.COMPLETED and r.status == Status.COMPLETED):
                best[r.post_id] = r
        return sorted(best.values(), key=lambda r: r.created_at, reverse=True)

    def requesters(self) -> list[tuple[int, str]]:
        """(chat_id, nombre más reciente) de quien tenga algo en el historial."""
        rows = self._rows(
            f"SELECT chat_id, user_name, MAX(created_at) AS last FROM requests "
            f"WHERE status IN ({_marks(Status.HISTORY)}) GROUP BY chat_id ORDER BY last DESC",
            Status.HISTORY)
        return [(r["chat_id"], r["user_name"]) for r in rows]

    def served_count(self, chat_id: int) -> int:
        """Cuántos animes distintos se le han bajado (o se le están bajando) a ese chat."""
        r = self._first(f"SELECT COUNT(DISTINCT post_id) AS n FROM requests WHERE chat_id=? "
                        f"AND status IN ({_marks(Status.HISTORY)})", (chat_id, *Status.HISTORY))
        return r["n"] if r else 0

    def served_titles(self, limit: int = 60) -> list[str]:
        """Títulos de lo último que se ha bajado (de quien sea), sin repetir."""
        rows = self._rows("SELECT title, MAX(created_at) AS last FROM requests WHERE status=? "
                          "GROUP BY post_id ORDER BY last DESC LIMIT ?", (Status.COMPLETED, limit))
        return [r["title"] for r in rows]

    # ----------------------------------------------------- seguimientos
    @staticmethod
    def _tracking(r) -> Tracking | None:
        if r is None:
            return None
        return Tracking(
            id=r["id"], chat_id=r["chat_id"], user_name=r["user_name"], post_id=r["post_id"], title=r["title"],
            post_url=r["post_url"], paste_url=r["paste_url"], status=r["status"], created_at=r["created_at"],
            watch_uuid=r["watch_uuid"], owned=bool(r["owned"]), anilist_id=r["anilist_id"],
            schedule=json.loads(r["schedule"]) if r["schedule"] else None, request_id=r["request_id"],
            watch_title=r["watch_title"],
        )

    def _trackings(self, sql: str, args=()) -> list[Tracking]:
        return [self._tracking(r) for r in self._rows(sql, args)]

    def track_add(self, chat_id: int, user_name: str, post, request_id: int = 0) -> int:
        return self._write(
            "INSERT INTO trackings(chat_id, user_name, post_id, title, post_url, paste_url, status, created_at, "
            "request_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (chat_id, user_name, post.post_id, post.title, post.url, post.paste_url, TrackStatus.OFFERED,
             time.time(), request_id),
        ).lastrowid

    def track_get(self, tid: int) -> Tracking | None:
        return self._tracking(self._first("SELECT * FROM trackings WHERE id=?", (tid,)))

    def track_transition(self, tid: int, from_states: tuple[str, ...], to_state: str) -> bool:
        cur = self._write(
            f"UPDATE trackings SET status=?, decided_at=? WHERE id=? AND status IN ({_marks(from_states)})",
            (to_state, time.time(), tid, *from_states))
        return cur.rowcount == 1

    def track_update(self, tid: int, **fields):
        if "schedule" in fields:
            fields["schedule"] = json.dumps(fields["schedule"]) if fields["schedule"] else ""
        if "owned" in fields:
            fields["owned"] = int(fields["owned"])
        cols = ", ".join(f"{k}=?" for k in fields)
        self._write(f"UPDATE trackings SET {cols} WHERE id=?", (*fields.values(), tid))

    def track_live_for(self, chat_id: int, paste_url: str) -> Tracking | None:
        """El seguimiento de ese chat para ese anime que siga en pie (ofrecido, pendiente o activo)."""
        states = (TrackStatus.OFFERED, *TrackStatus.COUNTED)
        return self._tracking(self._first(
            f"SELECT * FROM trackings WHERE chat_id=? AND paste_url=? AND status IN ({_marks(states)}) "
            f"ORDER BY id DESC LIMIT 1", (chat_id, paste_url, *states)))

    def track_counted(self, chat_id: int) -> int:
        return self._first(
            f"SELECT COUNT(*) FROM trackings WHERE chat_id=? AND status IN ({_marks(TrackStatus.COUNTED)})",
            (chat_id, *TrackStatus.COUNTED))[0]

    def track_active_for_url(self, paste_url: str) -> list[Tracking]:
        return self._trackings("SELECT * FROM trackings WHERE paste_url=? AND status=? ORDER BY id",
                               (paste_url, TrackStatus.ACTIVE))

    def track_list(self, chat_id: int | None = None, states: tuple[str, ...] = (TrackStatus.ACTIVE,)) -> list[Tracking]:
        if chat_id is None:
            return self._trackings(f"SELECT * FROM trackings WHERE status IN ({_marks(states)}) ORDER BY title, id",
                                   states)
        return self._trackings(
            f"SELECT * FROM trackings WHERE chat_id=? AND status IN ({_marks(states)}) ORDER BY title, id",
            (chat_id, *states))

    # ---------------------------------------------------- valores sueltos
    def kv_get(self, k: str, default=None):
        r = self._first("SELECT v FROM kv WHERE k=?", (k,))
        return json.loads(r["v"]) if r else default

    def kv_set(self, k: str, v):
        self._write("INSERT OR REPLACE INTO kv(k, v) VALUES (?,?)", (k, json.dumps(v)))

    # ------------------ avisos de Telegram pendientes (p. ej. sin Internet)
    def outbox_add(self, chat_id: int, text: str):
        self._write("INSERT INTO outbox(chat_id, text, created_at) VALUES (?,?,?)", (chat_id, text, time.time()))

    def outbox_has(self, chat_id: int) -> bool:
        return self._first("SELECT 1 FROM outbox WHERE chat_id=? LIMIT 1", (chat_id,)) is not None

    def outbox_items(self, limit: int = 50) -> list[tuple[int, int, str, float]]:
        rows = self._rows("SELECT id, chat_id, text, created_at FROM outbox ORDER BY id LIMIT ?", (limit,))
        return [(r["id"], r["chat_id"], r["text"], r["created_at"]) for r in rows]

    def outbox_delete(self, item_id: int):
        self._write("DELETE FROM outbox WHERE id=?", (item_id,))
