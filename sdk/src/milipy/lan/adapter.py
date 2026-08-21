"""LANAdapter — Bot adapter that speaks directly to a Mini Militia LAN host.

Architecture (standalone client, no Android bridge needed):

    Termux (bot)                 Mini Militia host phone
        |                                |
        | raw UDP (LAN protocol)         |
        +--------------------------------+

``LANAdapter`` implements the same :class:`milipy.transport.BridgeAdapter`
contract as the WebSocket and simulator transports: it owns a UDP socket,
sends the LAN discovery handshake, runs the codec on every inbound datagram,
and funnels the resulting frames through the Bot's frame handler.

HONEST GATE (Aug 2026): the Mini Militia LAN packet format is UNKNOWN — no
capture has been analyzed yet. Connecting with a raw host string raises
``CapabilityError`` (see ``milipy.bot.Bot``). This module is a prepared
scaffold: the discovery payload, join bytes, and packet decoder are all
marked ``UNKNOWN`` and will be filled in ONLY from evidence captured in a
real PCAP (``protocol/research/pcap_report.py`` output). Do not fill them
in by guessing.

Unit tests against a test UDP server live in ``tests/test_lan_adapter.py``.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Callable

from ..events import EventEmitter
from ..protocol import CapabilityError
from ..transport import BridgeAdapter, FrameHandler
from .codec import MiniMilitiaCodec, LANPacket

logger = logging.getLogger("milipy.lan.adapter")

# Placeholder only — the real discovery port is UNKNOWN until a capture
# shows what Mini Militia broadcasts and on which port.
LAN_DISCOVERY_PORT_DEFAULT: int = 64090


class LANAdapter(BridgeAdapter):
    """Raw-UDP adapter for a Mini Militia LAN host.

    Usage (once the codec is validated against a real capture)::

        adapter = LANAdapter("192.168.1.128", port=34197)
        bot = Bot(adapter)
        bot.connect()

    Until then, constructing with a host/port is allowed but the codec will
    refuse to translate real packets (``NotImplementedError``), which makes
    the bot fail honestly instead of silently talking gibberish.
    """

    def __init__(
        self,
        host: str,
        port: int = 0,
        *,
        codec: MiniMilitiaCodec | None = None,
        broadcast_port: int = LAN_DISCOVERY_PORT_DEFAULT,
        discovery_only: bool = False,
    ) -> None:
        super().__init__()
        if not isinstance(host, str) or not host:
            raise ValueError("host must be a non-empty string")
        if not isinstance(port, int) or not (0 <= port <= 65535):
            raise ValueError("port must be an integer between 0 and 65535")
        self.host = host
        self.port = port or LAN_DISCOVERY_PORT_DEFAULT
        self.broadcast_port = broadcast_port
        self.codec = codec if codec is not None else MiniMilitiaCodec()
        self.discovery_only = discovery_only

        self._sock: socket.socket | None = None
        self._sock_fileno: int = -1
        self._reader: asyncio.Task[None] | None = None
        self._discovered: dict[str, tuple[str, int]] = {}  # ip -> (name?, port?)
        self._connected = False
        self._closing = False

    # -- BridgeAdapter contract ----------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(
        self,
        on_frame: FrameHandler,
        pairing_token: str | None = None,  # noqa: ARG002 — LAN has no pairing
    ) -> dict[str, Any]:
        """Open a UDP socket, (optionally) discover the host, and start reading.

        Returns a synthetic ``hello_ack`` so the Bot's handshake handling can
        run the same code path as the WebSocket adapter. The real LAN host
        has no handshake documented yet — ``pairing_token`` is intentionally
        unused.
        """
        self._on_frame = on_frame
        self._closing = False

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock_fileno = self._sock.fileno()
        self._connected = True

        if self.discovery_only or self.port == LAN_DISCOVERY_PORT_DEFAULT:
            await self.discover_once()

        loop = asyncio.get_running_loop()
        if not self.discovery_only:
            loop.add_reader(self._sock_fileno, lambda: asyncio.ensure_future(self._step()))

        # Synthetic ack — the Bot requires hello_ack fields to proceed.
        ack: dict[str, Any] = {
            "type": "hello_ack",
            "protocol": 1,
            "bridge_version": "lan-scaffold-0.4.0",
            "capabilities": {
                "screen_capture": False,
                "gesture_input": False,
                "player_tracking": True,
                "chat": False,
                "settings_read": False,
                "settings_write": False,
            },
            "screen": {"width": 1280, "height": 720},
            "lan": {"host": self.host, "port": self.port},
        }
        return ack

    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON action over UDP to the host.

        Until the real packet format is OBSERVED, this wraps the JSON frame
        in the documented scaffold envelope. If the real protocol turns out
        to be binary, this method MUST be rewritten from capture evidence —
        never silently upgraded without tests proving the round-trip.
        """
        if self._sock is None:
            raise ConnectionError("LANAdapter is not connected")
        payload = self.codec.encode(message)
        loop = asyncio.get_running_loop()
        await loop.sock_sendto(self._sock, payload, (self.host, self.port))

    async def close(self) -> None:
        self._closing = True
        if self._reader is not None and not self._reader.done():
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        loop = asyncio.get_event_loop()
        if self._sock_fileno != -1 and self._sock is not None:
            try:
                loop.remove_reader(self._sock_fileno)
            except (OSError, RuntimeError):
                pass
            self._sock_fileno = -1
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._connected = False

    # -- Discovery -------------------------------------------------------------

    async def discover_once(self) -> dict[str, tuple[str, int]]:
        """Send a LAN discovery broadcast and collect replies for a short window.

        The discovery payload is UNKNOWN — this sends nothing (an empty
        datagram is useless; Mini Militia ignores unknown probes, as proven
        in the ``protocol/research/`` sweep runs). Callers must set
        ``codec.discovery_payload`` from capture evidence before this can
        actually discover anything.
        """
        if self._sock is None or not self.codec.discovery_payload:
            return {}
        loop = asyncio.get_running_loop()
        await loop.sock_sendto(
            self._sock, self.codec.discovery_payload, ("255.255.255.255", self.broadcast_port)
        )
        # Passive collection happens in the normal read loop for 3 seconds.
        await asyncio.sleep(3.0)
        return dict(self._discovered)

    # -- Read loop -------------------------------------------------------------

    async def _step(self) -> None:
        """Drain all pending datagrams without blocking the event loop."""
        assert self._sock is not None
        try:
            while True:
                try:
                    data, addr = self._sock.recvfrom(65536)
                except (BlockingIOError, OSError):
                    break
                if self._closing:
                    break
                self._discovered[addr[0]] = (addr[0], addr[1])
                await self._dispatch(data, addr)
        except asyncio.CancelledError:
            raise

    async def _dispatch(self, data: bytes, addr: tuple[str, int]) -> None:
        """Parse one inbound datagram through the codec and deliver frames."""
        try:
            packet = self.codec.parse(data, addr)
        except NotImplementedError:
            logger.info("received %d bytes from %s — codec is not yet implemented (UNKNOWN protocol)", len(data), addr)
            return
        except Exception:  # noqa: BLE001
            logger.exception("codec parse failed for %d bytes from %s", len(data), addr)
            return
        frame = self.codec.to_frame(packet, addr)
        if frame is not None and self._on_frame is not None:
            try:
                result = self._on_frame(frame)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001
                logger.exception("frame handler raised")
