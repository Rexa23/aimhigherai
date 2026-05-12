"""
WebSocket broadcast registry.
Allows agents and services to broadcast events to the dashboard
without importing from app.main (which would create circular imports).
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass

_manager = None


def register_manager(manager: Any) -> None:
    global _manager
    _manager = manager


async def broadcast(data: dict[str, Any]) -> None:
    if _manager is None:
        return
    await _manager.broadcast(data)
