"""Modelo de datos: una petición y sus estados."""

from dataclasses import dataclass


class Status:
    """
    pending     esperando al admin
    processing  enviándose a Anime-Automator
    approved    en cola / descargándose
    completed   terminado con al menos un capítulo descargado
    rejected    rechazado por el admin
    failed      fallo técnico o ningún capítulo descargado
    nothing_new ya estaba completo / ya se estaba descargando
    """
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    NOTHING_NEW = "nothing_new"

    # el admin puede decidir (o reintentar) sobre ellas
    OPEN = (PENDING, FAILED)
    # en marcha: no se deja pedir otra vez lo mismo
    ACTIVE = (PENDING, PROCESSING, APPROVED)
    # consumen cupo: tienen opciones de acabar en descarga real. Las de un
    # mismo lote cuentan como una y las quota_exempt no cuentan.
    COUNTED = (PENDING, PROCESSING, APPROVED, COMPLETED)
    # salen en /descargados
    HISTORY = (COMPLETED, APPROVED, PROCESSING)


@dataclass
class Request:
    id: int
    chat_id: int
    user_name: str
    post_id: int
    title: str
    post_url: str
    paste_url: str
    airing: bool
    label: str
    status: str
    created_at: float
    admin_msg_id: int | None
    eps_total: int = 0
    eps_done: int = 0
    eps_failed: int = 0
    movie: bool = False
    bundle_id: int = 0
    quota_exempt: bool = False
    source: str = ""           # "" = la web de siempre; "torrent" = por AniList y torrent
    anilist_id: int = 0
    season: str = ""           # temporada (solo torrent; el admin la puede corregir)

    @property
    def torrent(self) -> bool:
        return self.source == "torrent"


class TrackStatus:
    """
    offered    Kuro lo ha ofrecido; falta que el cliente diga que sí
    declined   el cliente no lo quiere
    pending    esperando al admin
    processing creándose en change-detection
    active     vigilándose en change-detection
    rejected   rechazado por el admin
    ended      terminó la emisión (o se canceló): ya no se vigila
    failed     no se pudo crear en change-detection
    """
    OFFERED = "offered"
    DECLINED = "declined"
    PENDING = "pending"
    PROCESSING = "processing"
    ACTIVE = "active"
    REJECTED = "rejected"
    ENDED = "ended"
    FAILED = "failed"

    # ocupan hueco en el límite de cada cliente
    COUNTED = (PENDING, PROCESSING, ACTIVE)
    # el admin puede decidir (o reintentar)
    OPEN = (PENDING, FAILED)


@dataclass
class Tracking:
    id: int
    chat_id: int
    user_name: str
    post_id: int
    title: str
    post_url: str
    paste_url: str
    status: str
    created_at: float
    watch_uuid: str = ""
    owned: bool = False        # el watch lo creó Kuro (se borra al acabar); si no, es de otro o manual
    anilist_id: int = 0
    schedule: dict | None = None
    request_id: int = 0
    watch_title: str = ""      # <title> de la ficha: con él elige Anime-Automator la carpeta
    shared: bool = False       # ya lo seguía otro cuando se apuntó: no gasta cupo
