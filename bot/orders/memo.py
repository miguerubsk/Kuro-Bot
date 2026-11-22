"""
Apuntes de cada encargo que no van en la BD: la nota de biblioteca para el
admin y la temporada de cada petición de un lote. Viven en memoria: tras un
reinicio los mensajes salen sin ellos, pero todo sigue funcionando.
"""

from dataclasses import dataclass, field


@dataclass
class OrderMemo:
    notes: dict[int, str] = field(default_factory=dict)       # req_id -> nota para el admin
    seasons: dict[int, str] = field(default_factory=dict)     # req_id -> "2"
    bundle_names: dict[int, str] = field(default_factory=dict)  # bundle_id -> nombre del anime
