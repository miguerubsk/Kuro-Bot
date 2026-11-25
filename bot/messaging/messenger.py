"""
Envío de avisos a Telegram con buzón de salida.

Si Telegram no es alcanzable (p. ej. al volver de un corte de luz sin
Internet todavía), el aviso se guarda en la BD y se reenvía más tarde en vez
de perderse. Los errores permanentes (bot bloqueado, chat inexistente, texto
inválido) no se reintentan.
"""

import asyncio
import logging
import time

from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError

log = logging.getLogger(__name__)

HTML = ParseMode.HTML


class Messenger:
    OUTBOX_MAX_AGE = 7 * 24 * 3600
    OUTBOX_EVERY = 30

    def __init__(self, db):
        self.db = db
        self.bot = None   # se engancha al arrancar (attach)

    def attach(self, bot):
        self.bot = bot

    async def _deliver(self, chat_id: int, text: str, **kw):
        await self.bot.send_message(chat_id, text, parse_mode=HTML, disable_web_page_preview=True, **kw)

    async def send(self, chat_id: int, text: str, **kw):
        """
        Los avisos con botones (kw) no se guardan: un botón viejo reenviado días
        después no tendría sentido.
        """
        retryable = not kw
        if self.bot is None or (retryable and self.db.outbox_has(chat_id)):
            # aún sin bot, o hay avisos anteriores sin entregar: se respeta el orden
            if retryable:
                self.db.outbox_add(chat_id, text)
            return
        try:
            await self._deliver(chat_id, text, **kw)
        except (BadRequest, Forbidden) as ex:   # va antes: BadRequest hereda de NetworkError
            log.warning("No se pudo avisar al chat %s: %s", chat_id, ex)
        except (NetworkError, RetryAfter) as ex:
            if not retryable:
                log.warning("No se pudo avisar al chat %s: %s", chat_id, ex)
                return
            log.warning("Telegram no responde (%s): el aviso al chat %s se reenviará más tarde", ex, chat_id)
            self.db.outbox_add(chat_id, text)
        except TelegramError as ex:
            log.warning("No se pudo avisar al chat %s: %s", chat_id, ex)

    # ------------------------------------------------------------ buzón
    async def run_outbox(self):
        while True:
            await asyncio.sleep(self.OUTBOX_EVERY)
            try:
                await self.flush_outbox()
            except Exception:
                log.exception("Fallo reenviando avisos pendientes")

    async def flush_outbox(self):
        if self.bot is None:
            return
        for item_id, chat_id, text, created_at in self.db.outbox_items():
            if time.time() - created_at > self.OUTBOX_MAX_AGE:
                log.error("Aviso al chat %s descartado tras 7 días sin poder entregarse", chat_id)
            elif not await self._redeliver(chat_id, text):
                return   # Telegram aún no está para avisos: se sigue en la próxima vuelta
            self.db.outbox_delete(item_id)

    async def _redeliver(self, chat_id: int, text: str) -> bool:
        """Reenvía un aviso pendiente. False si hay que parar (y dejarlo en el buzón)."""
        try:
            await self._deliver(chat_id, text)
        except RetryAfter as ex:
            delay = ex.retry_after   # segundos o timedelta, según la versión
            await asyncio.sleep(delay.total_seconds() if hasattr(delay, "total_seconds") else float(delay))
            return False
        except (BadRequest, Forbidden) as ex:   # va antes: BadRequest hereda de NetworkError
            log.warning("Aviso pendiente al chat %s descartado: %s", chat_id, ex)
        except NetworkError:
            return False   # sigue sin haber conexión
        except TelegramError as ex:
            log.warning("Aviso pendiente al chat %s descartado: %s", chat_id, ex)
        else:
            log.info("Aviso pendiente entregado al chat %s", chat_id)
        return True
