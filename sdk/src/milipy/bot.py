"""MiliPy Bot — the developer-facing entry point.

Usage::

    from milipy import Bot

    bot = Bot("192.168.43.1", port=8765)

    @bot.on("ready")
    def ready():
        print("Bot has spawned")

    @bot.on("player_seen")
    def enemy(player):
        print("Enemy:", player.name)

    @bot.on("tick")
    def tick(state):
        enemy = bot.nearest_enemy()
        if enemy:
            bot.aim_at(enemy)
            bot.fire()

    bot.connect()
    bot.run()

The ``Bot`` owns the event loop, the transport, the capability negotiation,
and the world-state cache. Every higher-level module (``chat``, ``settings``,
``actions``) is a view onto this central object.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

from .actions import ActionBuilder
from .events import EventEmitter
from .protocol import CapabilityError, decode_frame, parse_message
from .protocol_schema import (
    EVENT_CAPTURE_STARTED,
    EVENT_CAPTURE_STOPPED,
    EVENT_FRAME,
    EVENT_PLAYER_LOST,
    EVENT_PLAYER_SEEN,
    MSG_ACK,
    MSG_ERROR,
    MSG_EVENT,
    MSG_RESULT,
    MSG_STATE,
    SDK_CONNECTED,
    SDK_DISCONNECTED,
    SDK_READY,
    SDK_STATE_UPDATE,
    SDK_TICK,
)
from .state import Capabilities, GameSession, GameState, Player, parse_player
from .transport import BridgeAdapter, WebSocketAdapter

logger = logging.getLogger("milipy.bot")


class ChatAPI:
    """``bot.chat`` — chat operations.

    All methods raise :class:`CapabilityError` until the bridge reports
    ``capabilities.chat``. Sending without the capability is an error, not a
    silent no-op.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    def send(self, text: str) -> None:
        """Send a chat message. Synchronous convenience; enqueues the action."""
        name, payload = self._bot._actions.chat_send(text)
        self._bot._dispatch_action(name, payload)


class SettingsAPI:
    """``bot.settings`` — bridge and game setting access.

    Only MiliPy bridge settings are writable in protocol v0.1; everything
    else returns ``None`` or raises :class:`CapabilityError`.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    def get(self) -> dict[str, Any]:
        """Request the current settings snapshot from the bridge."""
        name, payload = self._bot._actions.get_settings()
        self._bot._dispatch_action(name, payload)
        return {}

    def set(self, key: str, value: Any) -> None:
        """Change a MiliPy bridge setting."""
        name, payload = self._bot._actions.set_setting(key, value)
        self._bot._dispatch_action(name, payload)


class Bot:
    """The central MiliPy bot object.

    Parameters:
        host_or_adapter: A bridge host address (string) or a
            :class:`~milipy.transport.BridgeAdapter` instance (such as the
            simulator's ``SimAdapter``). Passing an adapter is how tests and
            demos run without a real device.

            **Important:** ``host`` is the network address of the *MiliPy
            Android Bridge* — the Kotlin app running on the controlled
            Android device — **not** the Mini Militia game server. Mini
            Militia's LAN lobby networking is handled by the game itself;
            MiliPy only talks to its own bridge over WebSocket.
        port: WebSocket port of the MiliPy bridge (default ``8765``).
        pairing_token: Pairing code displayed by the bridge UI. May also be
            supplied via the ``MILIPY_PAIRING`` environment variable.
    """

    def __init__(
        self,
        host_or_adapter: str | BridgeAdapter,
        port: int = 8765,
        pairing_token: str | None = None,
    ) -> None:
        if isinstance(host_or_adapter, str):
            self._adapter: BridgeAdapter = WebSocketAdapter(host_or_adapter, port)
        elif isinstance(host_or_adapter, BridgeAdapter):
            self._adapter = host_or_adapter
        else:
            raise TypeError(
                "host_or_adapter must be a host string or a BridgeAdapter instance"
            )

        self._events = EventEmitter()
        self._capabilities = Capabilities()
        self._actions = ActionBuilder(self._capabilities.to_dict())
        self._state = GameState(tick=0)
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._action_counter: int = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._pairing_token = pairing_token or os.environ.get("MILIPY_PAIRING")

        # Convenience views.
        self.chat = ChatAPI(self)
        self.settings = SettingsAPI(self)

    # -- public properties --------------------------------------------------

    @property
    def events(self) -> EventEmitter:
        """The underlying event emitter."""
        return self._events

    @property
    def capabilities(self) -> Capabilities:
        """Capabilities negotiated with the bridge during handshake."""
        return self._capabilities

    @property
    def player(self) -> Player | None:
        """The bot's own player, or ``None`` before the first observation."""
        return self._state.player

    @property
    def players(self) -> dict[str, Player]:
        """All known players, including the bot itself."""
        return dict(self._state.players)

    @property
    def state(self) -> GameState:
        """A fresh snapshot of the current world state."""
        return self._state.snapshot()

    @property
    def game_session(self) -> GameSession | None:
        """Current high-level game session state reported by the bridge.

        ``None`` until the first observation includes it. The bridge reports
        ``UNKNOWN`` whenever it cannot legitimately determine the screen, and
        only reports concrete states (``MAIN_MENU``, ``LAN_MENU``,
        ``LOBBY_VISIBLE``, ``IN_LOBBY``, ``IN_GAME``, ``GAME_OVER``,
        ``NONE``) once the perception layer actually supports detecting
        them.
        """
        return self._state.game_session

    @property
    def is_connected(self) -> bool:
        return self._adapter.is_connected

    # -- event registration -------------------------------------------------

    def on(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a persistent event listener.

        Supported events in v0.1: ``connected``, ``disconnected``, ``ready``,
        ``tick``, ``state_update``, ``damage``, ``death``, ``spawn``,
        ``player_seen``, ``player_lost``, ``weapon_changed``, ``chat``.
        """
        return self._events.on(event)

    def once(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a listener that fires at most once."""
        return self._events.once(event)

    def off(self, event: str, callback: Callable[..., Any]) -> None:
        """Remove a registered listener."""
        self._events.off(event, callback)

    # -- connection lifecycle -----------------------------------------------

    def connect(self, pairing_token: str | None = None) -> None:
        """Open the WebSocket connection and run the handshake synchronously.

        Blocks until the handshake completes (or fails). After a successful
        handshake, ``connected`` fires and the state observation stream
        begins.
        """
        token = pairing_token or self._pairing_token
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_connect(token))

    async def connect_async(self, pairing_token: str | None = None) -> None:
        """Async version of :meth:`connect` for use inside an existing loop."""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        await self._async_connect(pairing_token or self._pairing_token)

    async def _async_connect(self, token: str | None) -> None:
        try:
            ack = await self._adapter.connect(self._handle_frame, token)
        except Exception as exc:  # noqa: BLE001
            logger.error("Connection failed: %s", exc)
            raise
        self._capabilities = Capabilities.from_dict(ack.get("capabilities", {}))
        self._actions = ActionBuilder(self._capabilities.to_dict())
        screen = ack.get("screen")
        if isinstance(screen, dict):
            self._state.screen_width = screen.get("width")
            self._state.screen_height = screen.get("height")
        self._events.emit(SDK_CONNECTED)
        self._events.emit(SDK_READY)
        logger.info(
            "Connected to bridge; capabilities=%s",
            {k: v for k, v in self._capabilities.to_dict().items() if v},
        )

    def run(self) -> None:
        """Start the event loop and keep it alive until disconnection.

        Only meaningful after :meth:`connect`; harmless (logs a warning) if
        called on the simulator adapter, which drives its own loop.
        """
        if self._loop is None:
            logger.warning("bot.run() called before bot.connect(); doing nothing")
            return
        loop = self._loop
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Interrupted; shutting down")
        finally:
            loop.run_until_complete(self._adapter.close())
            loop.close()

    def stop(self) -> None:
        """Schedule a graceful shutdown from any thread."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.disconnect_async()))

    async def disconnect_async(self, reason: str = "shutdown") -> None:
        """Gracefully close the session."""
        name, payload = self._actions.disconnect(reason)
        try:
            await self._adapter.send({"type": "action", "action": name, **payload})
        except Exception:  # noqa: BLE001
            pass
        await self._adapter.close()
        self._events.emit(SDK_DISCONNECTED, reason=reason)

    async def stop_bridge_async(self) -> None:
        """Remote-shutdown the bridge foreground service.

        The bridge acknowledges the action, tears down its WebSocket
        listener, and the Android UI/notification reflect the new state.
        This closes the session as a side effect — call
        :meth:`disconnect_async` afterwards if you need cleanup on the SDK
        side.
        """
        name, payload = self._actions.stop_bridge()
        await self._adapter.send({"type": "action", "action": name, **payload})

    # -- action dispatch ----------------------------------------------------

    def _dispatch_action(self, name: str, payload: dict[str, Any]) -> None:
        """Validate capability support and enqueue an action.

        Raises :class:`CapabilityError` immediately when the bridge has
        reported the backing capability unavailable — this is the SDK's
        honest failure mode.
        """
        from .protocol_schema import ACTION_SPECS, ERR_UNSUPPORTED_CAPABILITY

        spec = ACTION_SPECS.get(name)
        if spec is not None and spec.capability and not self._capabilities.supports(spec.capability):
            raise CapabilityError(name, spec.capability)
        if self._loop is not None and self._loop.is_running():
            asyncio.ensure_future(self._send_action(name, payload))  # noqa: RUF006
            return
        # Synchronous path (tests, sim demos): block until sent.
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        if self._loop.is_running():
            # Called from inside the running loop (e.g. sync listener body);
            # schedule the coroutine rather than nesting run_until_complete.
            asyncio.ensure_future(self._send_action(name, payload))  # noqa: RUF006
        else:
            self._loop.run_until_complete(self._send_action(name, payload))

    def _next_action_id(self) -> str:
        """Unique action identifier, e.g. ``"action-7"``.

        The bridge echoes it verbatim on the matching ``ack``/``error``, so
        listeners can correlate asynchronous confirmations with the action
        they were sent for. See protocol spec §3.4.
        """
        self._action_counter += 1
        return f"action-{self._action_counter}"

    async def _send_action(self, name: str, payload: dict[str, Any]) -> None:
        message: dict[str, Any] = {
            "type": "action",
            "action": name,
            "id": self._next_action_id(),
            **payload,
        }
        try:
            await self._adapter.send(message)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send action %s: %s", name, exc)
            self._events.emit("action_failed", action=name, reason=str(exc))

    # -- high-level actions -------------------------------------------------

    def move(self, direction: str) -> None:
        """Sustain movement in ``direction`` (``left``, ``right``, ``up``, ``down``)."""
        name, payload = self._actions.move(direction)
        self._dispatch_action(name, payload)

    def stop_movement(self) -> None:
        """Release all sustained movement and aim inputs."""
        name, payload = self._actions.stop()
        self._dispatch_action(name, payload)

    def jump(self) -> None:
        name, payload = self._actions.jump()
        self._dispatch_action(name, payload)

    def crouch(self) -> None:
        name, payload = self._actions.crouch()
        self._dispatch_action(name, payload)

    def set_control(self, **controls: bool) -> None:
        """Low-level sustained-press control state."""
        name, payload = self._actions.set_control(**controls)
        self._dispatch_action(name, payload)

    def aim(self, nx: float, ny: float) -> None:
        """Sustain aim at a normalized screen point (top-left origin)."""
        name, payload = self._actions.aim(nx, ny)
        self._dispatch_action(name, payload)

    def aim_at(self, player: Player) -> None:
        """Sustain aim at a tracked player (requires observed position)."""
        name, payload = self._actions.aim_at(player)
        self._dispatch_action(name, payload)

    def fire(self) -> None:
        """Begin sustained firing."""
        name, payload = self._actions.fire()
        self._dispatch_action(name, payload)

    def stop_fire(self) -> None:
        name, payload = self._actions.stop_fire()
        self._dispatch_action(name, payload)

    def punch(self) -> None:
        name, payload = self._actions.punch()
        self._dispatch_action(name, payload)

    def throw_grenade(self) -> None:
        name, payload = self._actions.throw_grenade()
        self._dispatch_action(name, payload)

    def pickup(self) -> None:
        name, payload = self._actions.pickup()
        self._dispatch_action(name, payload)

    def switch_weapon(self, index: int) -> None:
        name, payload = self._actions.switch_weapon(index)
        self._dispatch_action(name, payload)

    def request_state(self) -> None:
        """Ask the bridge for an immediate state observation."""
        name, payload = self._actions.request_state()
        self._dispatch_action(name, payload)

    # -- queries over observed state ----------------------------------------

    def nearest_player(self, excluding_self: bool = True) -> Player | None:
        """Return the closest player to the bot by observed position.

        Operates purely on currently observed state; returns ``None`` when no
        player with an observable position exists.
        """
        me = self._state.player
        if me is None or me.position is None:
            return None
        candidates = [
            p
            for p in self._state.players.values()
            if p.position is not None and not (excluding_self and p.is_self)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: me.position.distance_to(p.position))  # type: ignore[arg-type]

    def nearest_enemy(self) -> Player | None:
        """Return the closest non-self player, by observed position."""
        return self.nearest_player(excluding_self=True)

    # -- frame handling -----------------------------------------------------

    async def _handle_frame(self, message: dict[str, Any]) -> None:
        """Route an inbound protocol message to state updates, events, acks."""
        msg_type = message.get("type")

        if msg_type == MSG_STATE:
            await self._apply_state(message)
            return
        if msg_type == MSG_EVENT:
            await self._apply_event(message)
            return
        if msg_type in (MSG_ACK, MSG_RESULT):
            request_id = message.get("request_id")
            if request_id is not None and request_id in self._pending:
                future = self._pending.pop(request_id)
                if not future.done():
                    future.set_result(message)
            status = message.get("status")
            action_name = message.get("action")
            if msg_type == MSG_ACK and status == "rejected":
                self._events.emit("action_rejected", action=action_name, message=message.get("message"))
            elif action_name is not None:
                self._events.emit("action_ack", action=action_name, status=status or "accepted")
            return
        if msg_type == MSG_ERROR:
            self._events.emit("bridge_error", code=message.get("code"), message=message.get("message"))
            action_id = message.get("id")
            if action_id is not None:
                self._events.emit("action_rejected", action=None, message=message.get("message"))
            return
        logger.debug("Unhandled inbound message type: %s", msg_type)

    async def _apply_state(self, message: dict[str, Any]) -> None:
        """Merge a ``state`` observation into the world-state cache."""
        try:
            tick = int(message["tick"])
        except (KeyError, TypeError, ValueError):
            logger.warning("State message missing valid tick; dropping")
            return

        frame = message.get("frame") if isinstance(message.get("frame"), dict) else None
        player_payload = message.get("player")
        if isinstance(player_payload, dict):
            self._state.player = parse_player(player_payload, "self")
            self._state.players["self"] = self._state.player

        snapshot = self._state.snapshot()
        snapshot.tick = tick
        snapshot.frame = frame
        if "game_session" in message and isinstance(message["game_session"], str):
            try:
                self._state.game_session = GameSession(message["game_session"])
                snapshot.game_session = self._state.game_session
            except ValueError:
                logger.warning("Unknown game_session value: %s", message["game_session"])
        self._state.tick = tick
        self._events.emit(SDK_TICK, state=snapshot)
        self._events.emit(SDK_STATE_UPDATE, state=snapshot)

    async def _apply_event(self, message: dict[str, Any]) -> None:
        """Translate a protocol ``event`` into SDK events."""
        event_name = message.get("event")
        data = message.get("data") if isinstance(message.get("data"), dict) else {}

        if event_name in (EVENT_PLAYER_SEEN, EVENT_PLAYER_LOST):
            player_payload = data.get("player") if isinstance(data.get("player"), dict) else {}
            player_id = str(player_payload.get("id", "unknown"))
            player = parse_player(player_payload, player_id)
            if event_name == EVENT_PLAYER_SEEN:
                self._state.players[player_id] = player
                self._events.emit("player_seen", player=player)
            else:
                self._state.players.pop(player_id, None)
                self._events.emit("player_lost", player=player)
            return
        if event_name == EVENT_CAPTURE_STARTED:
            self._events.emit("capture_started")
            return
        if event_name == EVENT_CAPTURE_STOPPED:
            self._events.emit("capture_stopped")
            return
        if event_name == EVENT_FRAME:
            self._events.emit("frame", frame=data)
            return
        logger.debug("Unknown bridge event: %s", event_name)
