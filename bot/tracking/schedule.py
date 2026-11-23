"""
Cuándo merece la pena mirar si hay capítulo nuevo.

Un anime en emisión sale una vez por semana, siempre el mismo día y a la
misma hora (en Japón). Fuera de unas horas después de la emisión no va a
aparecer nada en la web, así que change-detection y el Drive (Anime-Automator)
solo miran dentro de esa ventana, y el resto de la semana descansan.

La ventana dura como mucho 24 h (MAX_HOURS) desde la hora de emisión. Si
solo se sabe el día del estreno, es el día entero en Japón: de medianoche
a medianoche de allí, pasado a la hora local.

    s = Schedule.from_airing(ts_de_emisión, tz, horas=24)
    s.time_schedule_limit("Europe/Madrid")   # lo que pide la API
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_NAMES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MAX_HOURS = 24         # nunca más de un día desde la emisión
JAPAN = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class Schedule:
    weekday: int | None     # 0 = lunes; None = sin ventana (se mira siempre)
    start_min: int = 0      # minuto del día (hora local) en que empieza
    hours: int = MAX_HOURS  # duración de la ventana
    source: str = ""        # "anilist" (hora de emisión), "estreno" (solo el día) o ""

    # --------------------------------------------------------- creación
    @classmethod
    def from_airing(cls, ts: float, tz: ZoneInfo, hours: int) -> "Schedule":
        """Ventana desde la hora en punto de la emisión (en hora local)."""
        t = datetime.fromtimestamp(ts, tz)
        return cls(t.weekday(), t.hour * 60, max(1, min(hours, MAX_HOURS)), "anilist")

    @classmethod
    def from_premiere(cls, premiere: str, tz: ZoneInfo, now: datetime | None = None) -> "Schedule | None":
        """
        Solo se sabe la fecha de estreno ("2025-07-04", día de Japón): sale ese
        día de la semana, a una hora desconocida. La ventana es ese día entero
        en Japón (24 h desde su medianoche), en hora local. El cambio de hora
        de aquí se calcula para la próxima emisión (el mantenimiento lo reajusta).
        """
        try:
            d = date.fromisoformat((premiere or "").strip()[:10])
        except ValueError:
            return None
        today = (now or datetime.now(JAPAN)).astimezone(JAPAN).date()
        nxt = today + timedelta(days=(d.weekday() - today.weekday()) % 7)
        start = datetime(nxt.year, nxt.month, nxt.day, tzinfo=JAPAN).astimezone(tz)
        return cls(start.weekday(), start.hour * 60 + start.minute, MAX_HOURS, "estreno")

    @classmethod
    def always(cls) -> "Schedule":
        return cls(None, 0, 0, "")

    # ------------------------------------------------------ persistencia
    def to_dict(self) -> dict:
        return {"weekday": self.weekday, "start_min": self.start_min, "hours": self.hours, "source": self.source}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Schedule":
        if not d:
            return cls.always()
        # las de antes podían durar días: nunca más de MAX_HOURS
        hours = min(int(d.get("hours") or 0), MAX_HOURS)
        return cls(d.get("weekday"), int(d.get("start_min") or 0), hours, d.get("source") or "")

    # ------------------------------------------------------------ salida
    @property
    def limited(self) -> bool:
        return self.weekday is not None and 0 < self.hours <= MAX_HOURS

    def windows(self) -> dict[int, tuple[int, int]]:
        """{día de la semana: (minuto de inicio, minutos de duración)} de la ventana, troceada por días."""
        if not self.limited:
            return {}
        out = {}
        day, start, left = self.weekday, self.start_min, self.hours * 60
        while left > 0:
            span = min(24 * 60 - start, left)
            out[day] = (start, span)
            left -= span
            day, start = (day + 1) % 7, 0
        return out

    def time_schedule_limit(self, tz_name: str) -> dict:
        wins = self.windows()
        out = {"enabled": bool(wins), "timezone": tz_name}
        for i, name in enumerate(DAYS):
            start, span = wins.get(i, (0, 24 * 60))
            out[name] = {
                "enabled": i in wins,
                "start_time": f"{start // 60:02d}:{start % 60:02d}",
                "duration": {"hours": str(span // 60), "minutes": f"{span % 60:02d}"},
            }
        return out

    def describe(self) -> str:
        """«los jueves desde las 17:00, durante 24 h» (texto plano)."""
        if not self.limited:
            return "todos los días"
        h, m = divmod(self.start_min, 60)
        day = DAY_NAMES[self.weekday]
        plural = day if day.endswith("s") else day + "s"
        japan = " (medianoche en Japón)" if self.source == "estreno" else ""
        return f"los {plural} desde las {h:02d}:{m:02d}{japan}, durante {self.hours} h"
