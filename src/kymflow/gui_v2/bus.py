"""Event bus for GUI v2 with per-client isolation.

This module provides an EventBus implementation that creates separate bus instances
per NiceGUI client (browser tab/window), ensuring event subscriptions don't leak
across client sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, Dict, List, Literal, Tuple, Type, TypeVar

from nicegui import ui

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

TEvent = TypeVar("TEvent")

# Type for event phase
EventPhase = Literal["intent", "state"]

# Module-level registry of buses per client
# Key: client ID (str), Value: EventBus instance
_CLIENT_BUSES: Dict[str, EventBus] = {}


@dataclass(frozen=True, slots=True)
class BusConfig:
    """Configuration for EventBus behavior.

    Attributes:
        trace: If True, log all event emissions and handler executions.
    """

    trace: bool = False


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
        # Map: event_type -> list of (handler, phase_filter)
        # phase_filter is None for legacy subscribe(), or "intent"/"state" for phase-filtered subscriptions
        self._subs: DefaultDict[
            Type[Any], List[Tuple[Callable[[Any], None], EventPhase | None]]
        ] = DefaultDict(list)
        self._client_id: str = client_id
        logger.debug(f"[bus] Created EventBus for client {client_id}")

    def subscribe(
        self,
        event_type: Type[TEvent],
        handler: Callable[[TEvent], None],
        phase: EventPhase | None = None,
    ) -> None:
        """Subscribe a handler for a specific concrete event type.

        Handlers are automatically de-duplicated - subscribing the same handler
        twice for the same event type with the same phase has no effect. This
        prevents duplicate handlers when pages are rebuilt during navigation.

        Args:
            event_type: The concrete event type to subscribe to (e.g., FileSelection).
            handler: Callback function that will receive events of this type.
            phase: Optional phase filter ("intent" or "state"). If None, handler
                receives all events of this type (legacy behavior). If "intent",
                only receives events with phase="intent". If "state", only receives
                events with phase="state".
        """
        handlers = self._subs[event_type]
        # Check if handler with same phase is already subscribed
        if any(h == handler and p == phase for h, p in handlers):
            logger.debug(
                f"[bus] Handler {handler.__qualname__} already subscribed to {event_type.__name__} "
                f"(phase={phase}), skipping"
            )
            return
        handlers.append((handler, phase))
        
        if self._config.trace:
            logger.debug(
                f"[bus] Subscribed {handler.__qualname__} to {event_type.__name__} "
                f"(phase={phase}, client={self._client_id}, total_handlers={len(handlers)})"
            )

    def subscribe_intent(
        self, event_type: Type[TEvent], handler: Callable[[TEvent], None]
    ) -> None:
        """Subscribe a handler to intent-phase events only.

        Convenience method for subscribing to events with phase="intent".
        Controllers typically subscribe to intent events.

        Args:
            event_type: The concrete event type to subscribe to.
            handler: Callback function that will receive intent events of this type.
        """
        self.subscribe(event_type, handler, phase="intent")

    def subscribe_state(
        self, event_type: Type[TEvent], handler: Callable[[TEvent], None]
    ) -> None:
        """Subscribe a handler to state-phase events only.

        Convenience method for subscribing to events with phase="state".
        Bindings typically subscribe to state events.

        Args:
            event_type: The concrete event type to subscribe to.
            handler: Callback function that will receive state events of this type.
        """
        self.subscribe(event_type, handler, phase="state")

    def unsubscribe_intent(
        self, event_type: Type[TEvent], handler: Callable[[TEvent], None]
    ) -> None:
        """Unsubscribe a handler from intent-phase events.

        Convenience method for unsubscribing from events with phase="intent".

        Args:
            event_type: The event type to unsubscribe from.
            handler: The handler function to remove.
        """
        self.unsubscribe(event_type, handler, phase="intent")

    def unsubscribe_state(
        self, event_type: Type[TEvent], handler: Callable[[TEvent], None]
    ) -> None:
        """Unsubscribe a handler from state-phase events.

        Convenience method for unsubscribing from events with phase="state".

        Args:
            event_type: The event type to unsubscribe from.
            handler: The handler function to remove.
        """
        self.unsubscribe(event_type, handler, phase="state")

    def unsubscribe(
        self,
        event_type: Type[TEvent],
        handler: Callable[[TEvent], None],
        phase: EventPhase | None = None,
    ) -> None:
        """Unsubscribe a handler from an event type.

        Useful for cleanup when components are destroyed. Safe to call even if
        the handler was never subscribed. If phase is None, removes all subscriptions
        for this handler regardless of phase.

        Args:
            event_type: The event type to unsubscribe from.
            handler: The handler function to remove.
            phase: Optional phase filter. If None, removes handler regardless of phase.
                If specified, only removes handler with matching phase.
        """
        handlers = self._subs.get(event_type)
        if not handlers:
            return

        original_count = len(handlers)
        if phase is None:
            # Remove all subscriptions for this handler (any phase)
            handlers[:] = [(h, p) for h, p in handlers if h != handler]
        else:
            # Remove only handler with matching phase
            handlers[:] = [(h, p) for h, p in handlers if not (h == handler and p == phase)]

        removed = original_count - len(handlers)
        if removed > 0:
            logger.debug(
                f"[bus] Unsubscribed {handler.__qualname__} from {event_type.__name__} "
                f"(phase={phase}, removed={removed}, client={self._client_id}, "
                f"remaining_handlers={len(handlers)})"
            )

    def emit(self, event: Any) -> None:
        """Emit an event to all subscribed handlers.

        Events are delivered synchronously in subscription order. Handlers are
        filtered by phase if the event has a 'phase' attribute and the handler
        was subscribed with a phase filter. If a handler raises an exception,
        it is logged but doesn't prevent other handlers from receiving the event.

        Args:
            event: The event instance to emit (type determines which handlers receive it).
        """
        etype = type(event)
        all_handlers = self._subs.get(etype, [])

        # Filter handlers by phase if event has phase attribute
        event_phase: EventPhase | None = getattr(event, "phase", None)
        filtered_handlers: List[Tuple[Callable[[Any], None], EventPhase | None]] = []

        for handler, handler_phase in all_handlers:
            if handler_phase is None:
                # Legacy subscription (no phase filter) - receives all events
                filtered_handlers.append((handler, handler_phase))
            elif event_phase is None:
                # Event has no phase - only deliver to legacy subscriptions
                if handler_phase is None:
                    filtered_handlers.append((handler, handler_phase))
            elif handler_phase == event_phase:
                # Phase matches - deliver event
                filtered_handlers.append((handler, handler_phase))

        if self._config.trace:
            logger.info(f"[bus] received {etype.__name__} phase={event_phase}")
            logger.info(f'  event:{event}')
            # logger.info(f"  phase={event_phase}")
            logger.info(f'  client={self._client_id}')
            logger.info(f'  num handlers={len(filtered_handlers)}')


        for handler, phase in filtered_handlers:
            if self._config.trace:
                name = getattr(handler, "__qualname__", repr(handler))
                logger.info(f"[bus] emit -> {etype.__name__} handling by {name}")
                logger.info(f"  phase={event_phase}, client={self._client_id}")
            try:
                handler(event)
            except Exception:
                handler_name = getattr(handler, "__qualname__", repr(handler))
                logger.exception(
                    f"[bus] Exception in handler {handler_name} for {etype.__name__} "
                    f"(client={self._client_id})"
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