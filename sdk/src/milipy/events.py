"""Event system for the MiliPy SDK.

Provides an ``EventEmitter`` with ``on``, ``once``, and ``off`` semantics,
mirroring the event-driven style of Mineflayer. Listeners receive keyword
arguments packed into a dict for convenience, and errors raised inside a
listener are caught, logged, and never propagated to the protocol loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

Callback = Callable[..., Any]
AsyncCallback = Callable[..., Coroutine[Any, Any, Any]]

logger = logging.getLogger("milipy.events")


class EventEmitter:
    """Synchronous/asynchronous event dispatcher.

    Example::

        emitter = EventEmitter()

        @emitter.on("player_seen")
        def handle(player):
            print("saw", player.name)

        emitter.emit("player_seen", player=some_player)
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[tuple[Callback, bool]]] = defaultdict(list)
        self._running_once: set[int] = set()

    # -- registration -------------------------------------------------------

    def on(self, event: str) -> Callable[[Callback], Callback]:
        """Decorator that registers a persistent listener for ``event``."""

        def decorator(callback: Callback) -> Callback:
            self._listeners[event].append((callback, False))
            return callback

        return decorator

    def once(self, event: str) -> Callable[[Callback], Callback]:
        """Decorator that registers a listener that fires exactly once."""

        def decorator(callback: Callback) -> Callback:
            self._listeners[event].append((callback, True))
            return callback

        return decorator

    def off(self, event: str, callback: Callback) -> None:
        """Remove a previously registered listener."""
        self._listeners[event] = [
            (cb, once) for cb, once in self._listeners[event] if cb is not callback
        ]

    def remove_all_listeners(self, event: str | None = None) -> None:
        """Remove listeners. With no argument, clears every event."""
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)

    # -- dispatch -----------------------------------------------------------

    def listeners(self, event: str) -> list[Callback]:
        """Return currently registered callbacks for ``event``."""
        return [cb for cb, _ in self._listeners.get(event, [])]

    def emit(self, event: str, **kwargs: Any) -> int:
        """Invoke all listeners for ``event``, passing ``kwargs``.

        Returns the number of listeners invoked. Exceptions raised inside a
        listener are logged and swallowed so one bad handler cannot kill the
        protocol loop. ``once`` listeners are removed after their first call.
        """
        bucket = list(self._listeners.get(event, []))
        count = 0
        for callback, is_once in bucket:
            try:
                result = callback(**kwargs)
                if asyncio.iscoroutine(result):
                    # Fire-and-forget async listener; schedule on the loop.
                    asyncio.ensure_future(result)  # noqa: RUF006
                count += 1
            except Exception:  # noqa: BLE001
                logger.exception("Listener for '%s' raised an exception", event)
            if is_once:
                # ``once`` listeners only fire for their first emission.
                self._listeners[event] = [
                    (cb, once)
                    for cb, once in self._listeners[event]
                    if not (cb is callback and once)
                ]
        return count
