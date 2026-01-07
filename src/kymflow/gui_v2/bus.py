"""Event bus for GUI v2 with per-client isolation.

This module provides an EventBus implementation that creates separate bus instances
per NiceGUI client (browser tab/window), ensuring event subscriptions don't leak
across client sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, Dict, List, Type, TypeVar

from nicegui import ui

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

TEvent = TypeVar("TEvent")

# Module-level registry of buses per client
# Key: client ID (str), Value: EventBus instance
_CLIENT_BUSES: Dict[str, EventBus] = {}


@dataclass(frozen=True, slots=True)
class BusConfig:
    """Configuration for EventBus behavior.

    Attributes:
        trace: If True, log all event emissions and handler executions.
    """

    trace: bool = True


class EventBus:
    """A typed event bus for explicit GUI signal flow with per-client isolation.

    Each client (browser tab/window) gets its own EventBus instance to prevent
    cross-client event leakage. Events are routed synchronously to all subscribers
    for a specific event type.

    Attributes:
        _config: Bus configuration (trace mode).
        _subs: Map from event type to list of handler functions.
        _client_id: Client identifier for this bus instance.
    """

    def __init__(self, client_id: str, config: BusConfig | None = None) -> None:
        """Initialize EventBus for a specific client.

        Args:
            client_id: Unique identifier for the NiceGUI client.
            config: Optional bus configuration. Defaults to BusConfig(trace=True).
        """
        self._config: BusConfig = config or BusConfig()
        self._subs: DefaultDict[Type[Any], List[Callable[[Any], None]]] = DefaultDict(list)
        self._client_id: str = client_id
        logger.debug(f"[bus] Created EventBus for client {client_id}")

    def subscribe(self, event_type: Type[TEvent], handler: Callable[[TEvent], None]) -> None:
        """Subscribe a handler for a specific concrete event type.

        Handlers are automatically de-duplicated - subscribing the same handler
        twice for the same event type has no effect. This prevents duplicate
        handlers when pages are rebuilt during navigation.

        Args:
            event_type: The concrete event type to subscribe to (e.g., FileSelected).
            handler: Callback function that will receive events of this type.
        """
        handlers = self._subs[event_type]
        if handler in handlers:
            logger.debug(
                f"[bus] Handler {handler.__qualname__} already subscribed to {event_type.__name__}, skipping"
            )
            return
        handlers.append(handler)
        logger.debug(
            f"[bus] Subscribed {handler.__qualname__} to {event_type.__name__} "
            f"(client={self._client_id}, total_handlers={len(handlers)})"
        )

    def unsubscribe(self, event_type: Type[TEvent], handler: Callable[[TEvent], None]) -> None:
        """Unsubscribe a handler from an event type.

        Useful for cleanup when components are destroyed. Safe to call even if
        the handler was never subscribed.

        Args:
            event_type: The event type to unsubscribe from.
            handler: The handler function to remove.
        """
        handlers = self._subs.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
            logger.debug(
                f"[bus] Unsubscribed {handler.__qualname__} from {event_type.__name__} "
                f"(client={self._client_id}, remaining_handlers={len(handlers)})"
            )
        except ValueError:
            pass

    def emit(self, event: Any) -> None:
        """Emit an event to all subscribed handlers.

        Events are delivered synchronously in subscription order. If a handler
        raises an exception, it is logged but doesn't prevent other handlers
        from receiving the event.

        Args:
            event: The event instance to emit (type determines which handlers receive it).
        """
        etype = type(event)
        handlers = list(self._subs.get(etype, []))

        if self._config.trace:
            logger.info(f"[bus] emit {etype.__name__}: {event} (client={self._client_id}, handlers={len(handlers)})")

        for h in handlers:
            if self._config.trace:
                name = getattr(h, "__qualname__", repr(h))
                logger.info(f"[bus] -> {etype.__name__} handled by {name} (client={self._client_id})")
            try:
                h(event)
            except Exception:
                logger.exception(
                    f"[bus] Exception in handler {h.__qualname__} for {etype.__name__} (client={self._client_id})"
                )

    def clear(self) -> None:
        """Clear all subscriptions from this bus.

        Useful for cleanup when a client disconnects. The bus instance remains
        but has no subscribers.
        """
        count = sum(len(handlers) for handlers in self._subs.values())
        self._subs.clear()
        logger.debug(f"[bus] Cleared {count} subscriptions (client={self._client_id})")


def get_client_id() -> str:
    """Get the current NiceGUI client ID.

    Returns:
        Client ID string. If client context is unavailable, returns "default".

    Note:
        This function must be called within a NiceGUI request context (page function).
    """
    try:
        # NiceGUI provides client context via ui.context.client.id
        if hasattr(ui.context, "client") and hasattr(ui.context.client, "id"):
            return str(ui.context.client.id)
    except (AttributeError, RuntimeError):
        # Fallback if client context is not available (e.g., during testing)
        pass
    return "default"


def get_event_bus(config: BusConfig | None = None) -> EventBus:
    """Get or create an EventBus for the current NiceGUI client.

    Each client (browser tab/window) gets its own isolated EventBus instance.
    This prevents event subscriptions from leaking across client sessions.

    Args:
        config: Optional bus configuration. Defaults to BusConfig(trace=True).

    Returns:
        EventBus instance for the current client.

    Note:
        This function must be called within a NiceGUI request context (page function).
        For testing, you can create EventBus instances directly.
    """
    client_id = get_client_id()

    # Get existing bus or create new one
    if client_id not in _CLIENT_BUSES:
        _CLIENT_BUSES[client_id] = EventBus(client_id, config)
        logger.info(f"[bus] Created new EventBus for client {client_id}")

    return _CLIENT_BUSES[client_id]


def clear_client_bus(client_id: str | None = None) -> None:
    """Clear subscriptions for a specific client's bus, or current client if None.

    Useful for cleanup when a client disconnects. In practice, NiceGUI handles
    client lifecycle automatically, but this can be useful for testing.

    Args:
        client_id: Client ID to clear. If None, clears the current client's bus.
    """
    if client_id is None:
        client_id = get_client_id()

    if client_id in _CLIENT_BUSES:
        _CLIENT_BUSES[client_id].clear()
        logger.debug(f"[bus] Cleared bus for client {client_id}")