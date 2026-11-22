"""Cupo semanal de encargos (ventana móvil de 7 días)."""


class Quota:
    def __init__(self, db, limit: int, admin_chat_id: int):
        self.db = db
        self.limit = limit
        self.admin = admin_chat_id

    def remaining(self, chat_id: int) -> int:
        return max(self.limit - self.db.used_this_week(chat_id), 0)

    def exhausted(self, chat_id: int) -> bool:
        """El admin no tiene cupo."""
        return chat_id != self.admin and self.remaining(chat_id) == 0

    def next_slot(self, chat_id: int) -> float | None:
        return self.db.next_slot(chat_id, self.limit)
