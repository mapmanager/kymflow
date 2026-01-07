# src/kymflow/gui_v2/bus.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, Dict, List, Type, TypeVar

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

TEvent = TypeVar("TEvent")


@dataclass(frozen=True, slots=True)
class BusConfig:
    """Configuration for EventBus.

    Attributes:
        trace: If True, log every emitted event and which handlers ran.
    """

    trace: bool = True


class EventBus:
    """A tiny typed event bus for explicit GUI signal flow.

    Design goals:
        - Keep views dumb: emit events only.
        - Keep controllers smart: subscribe and coordinate.
        - Make signal flow debuggable: one trace log shows who emitted what and who handled it.

    Notes:
        - Handlers run synchronously, in subscription order.
        - Keep handlers short; delegate heavy work to backend methods or tasks.
    """

    def __init__(self, config: BusConfig | None = None) -> None:
        self._config: BusConfig = config or BusConfig()
        self._subs: DefaultDict[Type[Any], List[Callable[[Any], None]]] = DefaultDict(list)

    def subscribe(self, event_type: Type[TEvent], handler: Callable[[TEvent], None]) -> None:
        """Subscribe a handler for a specific concrete event type."""
        self._subs[event_type].append(handler)

    def emit(self, event: Any) -> None:
        """Emit an event to subscribers of its concrete type."""
        etype = type(event)
        handlers = list(self._subs.get(etype, []))

        if self._config.trace:
            logger.info(f"[bus] emit {etype.__name__}: {event}")

        for h in handlers:
            if self._config.trace:
                name = getattr(h, "__qualname__", repr(h))
                logger.info(f"[bus] -> {etype.__name__} handled by {name}")
            h(event)
