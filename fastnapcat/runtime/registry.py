"""Runtime bridge lookup helpers for dependency providers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from fastevents import RuntimeEvent

if TYPE_CHECKING:
    from fastnapcat.runtime.bridge import RuntimeBridge


BRIDGE_ID_META_KEY = "fastnapcat_bridge_id"

_BRIDGES: WeakValueDictionary[str, RuntimeBridge] = WeakValueDictionary()


def register_bridge(bridge: RuntimeBridge) -> str:
    bridge_id = f"bridge-{id(bridge)}"
    _BRIDGES[bridge_id] = bridge
    return bridge_id


def bridge_meta(bridge_id: str) -> dict[str, str]:
    return {BRIDGE_ID_META_KEY: bridge_id}


def bridge_from_event(event: RuntimeEvent) -> RuntimeBridge:
    bridge_id = event.meta.get(BRIDGE_ID_META_KEY)
    if not isinstance(bridge_id, str):
        raise RuntimeError("FastNapCat bridge id is not available on this event")
    bridge = _BRIDGES.get(bridge_id)
    if bridge is None:
        raise RuntimeError("FastNapCat bridge is no longer available")
    return bridge
