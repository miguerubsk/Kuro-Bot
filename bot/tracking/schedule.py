"""
Cuándo merece la pena mirar si hay capítulo nuevo.

Un anime en emisión sale una vez por semana, siempre el mismo día y a la
misma hora (en Japón). Fuera de unas horas después de la emisión no va a
aparecer nada en la web, así que change-detection solo comprueba dentro de
esa ventana (time_schedule_limit) y el resto de la semana descansa.

    s = Schedule.from_airing(ts_de_emisión, horas=48)
    s.time_schedule_limit("Europe/Madrid")   # lo que pide la API
"""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_NAMES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MAX_HOURS = 6 * 24     # más de esto ya es mirar toda la semana


@dataclass(frozen=True)
class Schedule:
    weekday: int | None     # 0 = lunes; None = sin ventana (se mira siempre)
    start_min: int = 0      # minuto del día (hora local) en que empieza
    hours: int = 48         # duración de la ventana
    source: str = ""        # "anilist" (hora de emisión), "estreno" (solo el día) o ""

    # --------------------------------------------------------- creación
    @classmethod
    def from_airing(cls, ts: float, tz: ZoneInfo, hours: int) -> "Schedule":
        """Ventana desde la hora en punto de la emisión (en hora local)."""
        t = datetime.fromtimestamp(ts, tz)
        return cls(t.weekday(), t.hour * 60, min(hours, MAX_HOURS), "anilist")

    @classmethod
    def from_premiere(cls, premiere: str, hours: int) -> "Schedule | None":
        """
        Solo se sabe la fecha de estreno ("2025-07-04"): se emite el mismo día
        de la semana, a una hora desconocida. La ventana empieza a medianoche
        y dura un día más (la hora en Japón puede caer el día anterior aquí).
        """
        try:
            d = date.fromisoformat((premiere or "").strip()[:10])
        except ValueError:
            return None
        return cls((d.weekday() - 1) % 7, 0, min(hours + 48, MAX_HOURS), "estreno")

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
        return cls(d.get("weekday"), int(d.get("start_min") or 0), int(d.get("hours") or 0), d.get("source") or "")

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
        """«los jueves desde las 17:00, durante 48 h» (texto plano)."""
        if not self.limited:
            return "todos los días"
        h, m = divmod(self.start_min, 60)
        day = DAY_NAMES[self.weekday]
        plural = day if day.endswith("s") else day + "s"
        when = "desde medianoche" if self.source == "estreno" else f"desde las {h:02d}:{m:02d}"
        return f"los {plural} {when}, durante {self.hours} h"
