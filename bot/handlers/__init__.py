"""Importar los módulos registra sus órdenes en base.REGISTRY (en este orden)."""

from . import admin, general, orders, search, torrent, tracking  # noqa: F401
from .base import REGISTRY

__all__ = ["REGISTRY"]
