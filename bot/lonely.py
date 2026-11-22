"""
Kuro echa de menos al miauestro.

Si el admin pasa un tiempo sin hablarle, Kuro le escribe como si se sintiera
abandonado, cada vez más dramático (LEVELS niveles; después se calla hasta
que vuelva, para no dar la lata). Cuando vuelve, le recibe.

Para que no sea siempre igual:
- el plazo depende de cada cuánto suele aparecer el admin (mediana de sus
  últimos ratos sin hablar), multiplicado por un factor al azar, con un
  mínimo y un máximo; cada nivel se calcula de nuevo;
- solo escribe a horas razonables (QUIET_HOURS fuera) y a un minuto al azar;
- a veces menciona cosas reales: el último anime que pidió, los clientes que
  han pasado mientras tanto, cuántos días lleva solo.
"""

import asyncio
import logging
import random
import statistics
import time
from datetime import datetime

from .persona import TZ

log = logging.getLogger(__name__)

DAY = 24 * 3600
LEVELS = 4
MIN_WAIT = 1 * DAY            # nunca antes de día sin hablarle
MAX_WAIT = 30 * DAY           # ni más tarde de esto
DEFAULT_GAP = 2 * DAY         # si aún no hay historial
HISTORY = 30                  # ratos sin hablar que se recuerdan
TOUCH_GRANULARITY = 3600      # varias interacciones seguidas cuentan como una
AWAKE_HOURS = (7, 00)         # de 07:00 a 23:59
CHECK_EVERY = 15 * 60

K_LAST = "admin_last_seen"
K_GAPS = "admin_gaps"
K_LEVEL = "lonely_level"
K_NEXT = "lonely_next_at"
K_SENT_AT = "lonely_sent_at"


def _now_local() -> datetime:
    return datetime.now(TZ)


class Lonely:
    def __init__(self, db, admin_chat_id: int, send, persona):
        self.db = db
        self.admin = admin_chat_id
        self.send = send  # async (chat_id, text)
        self.persona = persona

    # --------------------------------------------------------- cálculo
    def _typical_gap(self) -> float:
        gaps = self.db.kv_get(K_GAPS, []) or []
        if len(gaps) < 3:
            return DEFAULT_GAP
        return statistics.median(gaps)

    def _plan_next(self, from_ts: float, level: int) -> float:
        """Cuándo toca el siguiente mensaje (nivel `level`, empezando en 1)."""
        typical = self._typical_gap()
        if level == 1:
            wait = typical * random.uniform(2.0, 3.5)
        else:
            # entre nivel y nivel, algo menos que la primera vez y siempre distinto
            wait = typical * random.uniform(1.2, 2.5)
        wait = max(MIN_WAIT, min(MAX_WAIT, wait))
        return self._at_awake_hour(from_ts + wait)

    @staticmethod
    def _at_awake_hour(ts: float) -> float:
        """Mueve ts a una hora despierta (y a un minuto al azar)."""
        start, end = AWAKE_HOURS
        dt = datetime.fromtimestamp(ts, TZ)
        if dt.hour >= end:  # demasiado tarde: a la mañana siguiente
            dt = datetime.fromtimestamp(ts + DAY, TZ).replace(hour=start)
        if dt.hour < start:
            dt = dt.replace(hour=random.randint(start, start + 3))
        dt = dt.replace(minute=random.randint(0, 59), second=random.randint(0, 59))
        return dt.timestamp()

    # ------------------------------------------------------- eventos
    async def touch(self):
        """El admin ha hablado con Kuro."""
        now = time.time()
        last = self.db.kv_get(K_LAST)
        level = self.db.kv_get(K_LEVEL, 0) or 0
        if last is None or now - last >= TOUCH_GRANULARITY:
            if last is not None:
                gaps = (self.db.kv_get(K_GAPS, []) or [])[-(HISTORY - 1):]
                # los ratos de abandono también cuentan, pero sin pasarse
                gaps.append(min(now - last, MAX_WAIT))
                self.db.kv_set(K_GAPS, gaps)
            self.db.kv_set(K_LAST, now)
        elif last is not None:
            self.db.kv_set(K_LAST, now)
        self.db.kv_set(K_NEXT, self._plan_next(now, 1))
        if level:
            self.db.kv_set(K_LEVEL, 0)
            away = now - (last or now)
            await self.send(self.admin, self.persona.say(
                "lonely_back_hurt" if level >= 3 else "lonely_back", self.admin,
                days=_days(away)))

    async def loop(self):
        if self.db.kv_get(K_NEXT) is None:
            self.db.kv_set(K_NEXT, self._plan_next(self.db.kv_get(K_LAST) or time.time(), 1))
        while True:
            await asyncio.sleep(CHECK_EVERY + random.uniform(-120, 120))
            try:
                await self._tick()
            except Exception:
                log.exception("Fallo en el aviso de soledad de Kuro")

    async def _tick(self):
        now = time.time()
        level = self.db.kv_get(K_LEVEL, 0) or 0
        nxt = self.db.kv_get(K_NEXT)
        if level >= LEVELS or nxt is None or now < nxt:
            return
        hour = _now_local().hour
        if not AWAKE_HOURS[0] <= hour < AWAKE_HOURS[1]:
            return
        level += 1
        last = self.db.kv_get(K_LAST) or now
        text = self._message(level, now - last, last)
        await self.send(self.admin, text)
        log.info("Kuro se siente solo (nivel %s, %.1f días sin el miauestro)", level, (now - last) / DAY)
        self.db.kv_set(K_LEVEL, level)
        self.db.kv_set(K_SENT_AT, now)
        self.db.kv_set(K_NEXT, self._plan_next(now, level + 1))

    def _message(self, level: int, away: float, last: float) -> str:
        text = self.persona.say(f"lonely_{level}", self.admin, days=_days(away))
        extras = []
        clients = self.db.requests_since(last, exclude_chat=self.admin)
        if clients:
            names = sorted({c.user_name.split(" (")[0] for c in clients})
            extras.append(self.persona.say("lonely_clients", self.admin, count=len(clients),
                                      who=", ".join(names[:3])))
        prev = self.db.last_request_of(self.admin)
        if prev:
            extras.append(self.persona.say("lonely_last_title", self.admin, title=prev.title))
        if extras and random.random() < 0.7:
            text += "\n\n" + random.choice(extras)
        return text


def _days(seconds: float) -> str:
    d = seconds / DAY
    if d < 1.5:
        return "un día"
    return f"{round(d)} días"
