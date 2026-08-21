"""Transport abstraction for the MiliPy SDK.

The SDK never talks to a raw socket directly. Instead every implementation of
``BridgeAdapter`` exposes the same contract, and the ``WebSocketAdapter``
realizes that contract over a real WebSocket connection while
``milipy.sim.SimAdapter`` provides an in-process fake bridge for testing.

This indirection is what makes the SDK fully testable in CI without any
Android device, and what keeps the Bot code identical in both worlds.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import string
from typing import Any, Callable, Coroutine

import websockets.asyncio.client

from .events import EventEmitter
from .protocol import (
    ProtocolError,
    auth_message,
    bridge_capabilities,
    decode_frame,
    encode_message,
    hello_message,
    protocol_version_supported,
)
from .protocol_schema import (
    AUTH_INVALID_TOKEN,
    DEFAULT_PORT,
    MSG_AUTH,
    MSG_AUTH_ERROR,
    MSG_AUTH_REQUIRED,
    MSG_EVENT,
    MSG_HELLO_ACK,
    MSG_PROTOCOL_ERROR,
    MSG_STATE,
    PAIRING_ALPHABET,
    PAIRING_LENGTH,
    PROTOCOL_UNSUPPORTED_VERSION,
    SDK_CONNECTED,
    SDK_DISCONNECTED,
)

logger = logging.getLogger("milipy.transport")


def generate_pairing_code(length: int = PAIRING_LENGTH) -> str:
    """Generate a random, unambiguous pairing code for the bridge UI."""
    alphabet = PAIRING_ALPHABET
    return "".join(secrets.choice(alphabet) for _ in range(length))


# Type for the raw frame handler installed by the Bot.
FrameHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class BridgeAdapter:
    """Abstract transport between the SDK and a MiliPy bridge.

    Concrete adapters implement :meth:`connect` and :meth:`send`. Incoming
    frames are funneled through :attr:`on_frame`; a ``None`` return means the
    frame could not be parsed and was dropped.
    """

    def __init__(self) -> None:
        self.events = EventEmitter()
        self._on_frame: FrameHandler | None = None
        self._paired: bool = False

    # -- adapter contract ---------------------------------------------------

    @property
    def is_connected(self) -> bool:
        raise NotImplementedError

    async def connect(
        self,
        on_frame: FrameHandler,
        pairing_token: str | None = None,
    ) -> dict[str, Any]:
        """Open the session, complete the handshake, and return ``hello_ack``.

        Raises ``ConnectionError`` on network failure, ``ProtocolError`` on
        protocol negotiation failure, and ``AuthenticationError`` when the
        pairing token is rejected.
        """
        self._on_frame = on_frame
        raise NotImplementedError

    async def send(self, message: dict[str, Any]) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        """Close the session gracefully. Idempotent."""
        raise NotImplementedError

    # -- helpers ------------------------------------------------------------

    async def _handle_incoming(self, raw: str) -> None:
        """Parse one inbound frame and dispatch it through the handler."""
        message = decode_frame(raw)
        if message is None:
            return
        if self._on_frame is not None:
            try:
                await self._on_frame(message)
            except Exception:  # noqa: BLE001
                logger.exception("Frame handler raised an exception")


class AuthenticationError(ProtocolError):
    """The bridge rejected the pairing token."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(reason, message)


class ConnectionFailure(ProtocolError):
    """The bridge could not be reached at all."""

    def __init__(self, host: str, port: int, detail: str | None = None) -> None:
        self.host = host
        self.port = port
        message = f"could not connect to {host}:{port}"
        if detail:
            message += f": {detail}"
        super().__init__("connection_failed", message)


class WebSocketAdapter(BridgeAdapter):
    """Real transport: an asyncio WebSocket client to a MiliPy Android bridge.

    Handles the full handshake (``hello`` → optional ``auth`` → ``hello_ack``),
    reconnection on transient errors, and never lets a bad frame crash the
    read loop.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        super().__init__()
        if not isinstance(host, str) or not host:
            raise ValueError("host must be a non-empty string")
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValueError("port must be an integer between 1 and 65535")
        self.host = host
        self.port = port
        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._pairing_token: str | None = None
        self._connected: bool = False
        self._closing: bool = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(  # type: ignore[override]
        self,
        on_frame: FrameHandler,
        pairing_token: str | None = None,
        *,
        timeout: float = 10.0,
        max_reconnect_attempts: int = 3,
        reconnect_interval: float = 2.0,
    ) -> dict[str, Any]:
        """Open the connection and complete the handshake with retries."""
        self._on_frame = on_frame
        self._pairing_token = pairing_token
        self._closing = False
        last_error: Exception | None = None

        for attempt in range(1, max_reconnect_attempts + 1):
            try:
                ws = await asyncio.wait_for(
                    websockets.asyncio.client.connect(
                        f"ws://{self.host}:{self.port}",
                        open_timeout=timeout,
                        close_timeout=5.0,
                    ),
                    timeout=timeout + 5.0,
                )
            except (
                OSError,
                asyncio.TimeoutError,
                websockets.InvalidURI,
                websockets.InvalidHandshake,
            ) as exc:
                last_error = exc
                logger.info("Connection attempt %d to %s:%d failed: %s", attempt, self.host, self.port, exc)
                if attempt < max_reconnect_attempts:
                    await asyncio.sleep(reconnect_interval)
                continue

            self._ws = ws
            try:
                ack = await self._perform_handshake()
            except (AuthenticationError, ProtocolError):
                await ws.close()
                self._ws = None
                raise
            except Exception as exc:  # noqa: BLE001
                await ws.close()
                self._ws = None
                last_error = exc
                if attempt < max_reconnect_attempts:
                    await asyncio.sleep(reconnect_interval)
                continue

            self._connected = True
            self._start_reader()
            return ack

        raise ConnectionFailure(self.host, self.port, repr(last_error) if last_error else None)

    async def _perform_handshake(self) -> dict[str, Any]:
        """Run the hello/auth handshake and return the ``hello_ack`` body."""
        assert self._ws is not None
        await self._ws.send(encode_message(hello_message()))
        first = await self._ws.recv()
        message = decode_frame(first)
        if message is None:
            raise ProtocolError("malformed_message", "bridge replied with an unparseable frame")

        if message["type"] == MSG_AUTH_REQUIRED:
            token = self._pairing_token
            if not token:
                raise AuthenticationError(
                    AUTH_INVALID_TOKEN,
                    "bridge requires a pairing code; pass pairing_token to bot.connect()",
                )
            await self._ws.send(encode_message(auth_message(token)))
            message = decode_frame(await self._ws.recv())
            if message is None:
                raise ProtocolError("malformed_message", "auth response was unparseable")
            if message["type"] == MSG_AUTH_ERROR:
                raise AuthenticationError(
                    message.get("reason", AUTH_INVALID_TOKEN),
                    f"pairing rejected: {message.get('reason', 'unknown')}",
                )

        if message["type"] == MSG_PROTOCOL_ERROR and message.get("reason") == PROTOCOL_UNSUPPORTED_VERSION:
            supported = message.get("supported", [])
            raise ProtocolError(
                "protocol_mismatch",
                f"bridge does not support protocol {message.get('protocol')!r}; it supports {supported}",
                message,
            )

        if message["type"] != MSG_HELLO_ACK:
            raise ProtocolError(
                "handshake_failed",
                f"expected hello_ack, got {message.get('type')!r}",
                message,
            )
        if not protocol_version_supported(message):
            raise ProtocolError(
                "protocol_mismatch",
                f"bridge negotiated protocol {message.get('protocol')!r}, expected {1}",
                message,
            )
        return message

    def _start_reader(self) -> None:
        assert self._ws is not None
        loop = asyncio.get_running_loop()
        self._read_task = loop.create_task(self._reader_loop())

    async def _reader_loop(self) -> None:
        """Read frames until the connection closes; never raises outward."""
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if self._closing:
                    break
                await self._handle_incoming(raw if isinstance(raw, str) else raw.decode("utf-8", "replace"))
        except websockets.ConnectionClosed as exc:
            logger.info("WebSocket closed: %s", exc)
        except Exception:  # noqa: BLE001
            logger.exception("Reader loop failed")
        finally:
            self._connected = False
            if not self._closing:
                self.events.emit(SDK_DISCONNECTED, reason="connection_lost")

    async def send(self, message: dict[str, Any]) -> None:
        if self._ws is None or not self._connected:
            raise ConnectionError("transport is not connected")
        await self._ws.send(encode_message(message))

    async def close(self) -> None:
        self._closing = True
        if self._read_task is not None and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
        self._connected = False


class ConsoleAdapter(BridgeAdapter):
    """Stdin/stdout transport for interactive Termux experimentation.

    Protocol frames are printed as JSON and read line-by-line from standard
    input. Useful when the bridge is being driven manually during
    development. Not used by the automated tests.
    """

    def __init__(self) -> None:
        super().__init__()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(  # type: ignore[override]
        self,
        on_frame: FrameHandler,
        pairing_token: str | None = None,
    ) -> dict[str, Any]:
        self._on_frame = on_frame
        self._connected = True
        ack: dict[str, Any] = {
            "type": MSG_HELLO_ACK,
            "protocol": 1,
            "bridge_version": "0.1.0",
            "capabilities": {
                "screen_capture": False,
                "gesture_input": False,
                "player_tracking": False,
                "chat": False,
                "settings_read": False,
                "settings_write": False,
            },
        }
        print(encode_message(ack), flush=True)
        self._start_reader()
        return ack

    def _start_reader(self) -> None:
        loop = asyncio.get_running_loop()
        loop.add_reader(__import__("sys").stdin, lambda: asyncio.ensure_future(self._stdin_step()))

    async def _stdin_step(self) -> None:
        import sys

        try:
            line = await asyncio.to_thread(sys.stdin.readline)
        except Exception:  # noqa: BLE001
            return
        if not line:
            self._connected = False
            self.events.emit(SDK_DISCONNECTED, reason="stdin_eof")
            return
        await self._handle_incoming(line)

    async def send(self, message: dict[str, Any]) -> None:
        import sys

        print(encode_message(message), flush=True)

    async def close(self) -> None:
        self._connected = False
