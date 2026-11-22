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
