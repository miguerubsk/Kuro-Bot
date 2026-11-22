"""
Quién puede hablar con Kuro (patrón estrategia).

Según el .env se usa una sola de estas políticas; el resto del bot solo
pregunta `allows(chat_id)` y no sabe cuál es:

- WhitelistPolicy  ALLOWED_CHAT_IDS: solo esos chats.
- KeywordPolicy    ACCESS_KEYWORD: quien se dé de alta con /start <palabra>.
- OpenPolicy       ninguna de las dos: cualquiera (todo pasa por el admin).

El admin siempre puede, y con las dos primeras puede además dejar pasar a
alguien por su código de chat (/alta).
"""

import hmac
from abc import ABC, abstractmethod


class AccessPolicy(ABC):
    deny_key = "deny_id"       # frase para quien no tiene acceso
    open = False               # sin restricciones (se avisa al entrar)

    def __init__(self, admin_chat_id: int):
        self.admin = admin_chat_id

    def allows(self, chat_id: int) -> bool:
        return chat_id == self.admin or self._allows(chat_id)

    @abstractmethod
    def _allows(self, chat_id: int) -> bool: ...

    def blocked(self, chat_id: int) -> bool:
        """Se le ignora en silencio (demasiados intentos fallidos)."""
        return False

    def try_register(self, chat_id: int, given: str, name: str) -> bool:
        """Alta con palabra clave. Las políticas sin altas nunca dan de alta a nadie."""
        return False

    can_add = False   # el admin puede dar de alta a alguien por su código (/alta)

    def add(self, chat_id: int, name: str):
        raise NotImplementedError


class WhitelistPolicy(AccessPolicy):
    """Los de la lista y los que el admin dé de alta con /alta."""
    can_add = True

    def __init__(self, admin_chat_id: int, chat_ids: frozenset[int], db=None):
        super().__init__(admin_chat_id)
        self.chat_ids = chat_ids
        self.db = db

    def _allows(self, chat_id: int) -> bool:
        return chat_id in self.chat_ids or (self.db is not None and self.db.is_registered(chat_id))

    def add(self, chat_id: int, name: str):
        self.db.register(chat_id, name)


class OpenPolicy(AccessPolicy):
    open = True

    def _allows(self, chat_id: int) -> bool:
        return True


class KeywordPolicy(AccessPolicy):
    deny_key = "deny_keyword"   # contraseña o código para el admin
    can_add = True
    MAX_FAILED = 5   # intentos fallidos antes de ignorar a ese chat en silencio

    def __init__(self, admin_chat_id: int, keyword: str, db):
        super().__init__(admin_chat_id)
        self.keyword = keyword
        self.db = db
        self.failed: dict[int, int] = {}

    def _allows(self, chat_id: int) -> bool:
        return self.db.is_registered(chat_id)

    def blocked(self, chat_id: int) -> bool:
        return self.failed.get(chat_id, 0) >= self.MAX_FAILED

    def try_register(self, chat_id: int, given: str, name: str) -> bool:
        if not given:
            return False
        if hmac.compare_digest(given.encode(), self.keyword.encode()):
            self.db.register(chat_id, name)
            self.failed.pop(chat_id, None)
            return True
        self.failed[chat_id] = self.failed.get(chat_id, 0) + 1
        return False

    def add(self, chat_id: int, name: str):
        self.db.register(chat_id, name)
        self.failed.pop(chat_id, None)


def make_policy(cfg, db) -> AccessPolicy:
    if cfg.allowed_chat_ids:
        return WhitelistPolicy(cfg.admin_chat_id, cfg.allowed_chat_ids, db)
    if cfg.access_keyword:
        return KeywordPolicy(cfg.admin_chat_id, cfg.access_keyword, db)
    return OpenPolicy(cfg.admin_chat_id)
