"""
Raíz de composición: crea una vez cada pieza del bot y las conecta.

Las piezas reciben `kuro` y piden a través de él lo que necesitan
(inyección de dependencias): así no hay estado global suelto por los
módulos y en las pruebas se puede montar un Kuro con dobles (automator,
web o BD falsos) sin tocar nada más.
"""

from .config import Settings
from .core.access import make_policy
from .core.quota import Quota
from .core.storage import Storage
from .events.handlers import EventRouter
from .lonely import Lonely
from .messaging.messenger import Messenger
from .orders.dispatcher import Dispatcher
from .orders.library import LibraryChecker
from .orders.memo import OrderMemo
from .persona import Persona
from .services.automator import AutomatorClient
from .services.japanpaw import JapanpawClient
from .ui.cards import CardDeck, CoverCache
from .ui.history import HistoryView
from .ui.texts import Texts


class Kuro:
    def __init__(self, cfg: Settings, *, db: Storage | None = None, automator: AutomatorClient | None = None,
                 site: JapanpawClient | None = None, persona: Persona | None = None):
        self.cfg = cfg
        self.admin = cfg.admin_chat_id

        self.persona = persona or Persona.instance()
        self.persona.set_boss(self.admin)
        self.db = db or Storage(cfg.data_dir)
        self.access = make_policy(cfg, self.db)
        self.quota = Quota(self.db, cfg.weekly_limit, self.admin)
        self.messenger = Messenger(self.db)

        self.automator = automator or AutomatorClient(cfg.automator_url)
        self.site = site or JapanpawClient(cfg.japanpaw_base, cfg.sockpuppet_url, cfg.force_browser)

        self.memo = OrderMemo()
        self.texts = Texts(self)
        self.library = LibraryChecker(self)
        self.dispatcher = Dispatcher(self)
        self.cards = CardDeck(CoverCache(self.site))
        self.history = HistoryView(self)
        self.events = EventRouter(self)
        self.lonely = Lonely(self.db, self.admin, self.messenger.send, self.persona)

    def is_admin(self, chat_id: int) -> bool:
        return chat_id == self.admin
