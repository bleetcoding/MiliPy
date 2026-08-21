"""Tests for milipy.lan.adapter.LANAdapter wiring.

These tests use a small in-process UDP server as a stand-in Mini Militia
host. They prove the adapter's socket lifecycle, broadcast scaffolding, and
the honest NOT_IMPLEMENTED gate — they do NOT claim any knowledge of the
real Mini Militia packet format (that stays UNKNOWN until a real PCAP is
analyzed).
"""
from __future__ import annotations

import asyncio
import socket
import sys
import unittest

sys.path.insert(0, "/tmp/_milipy_sdk_src")

from milipy.lan.adapter import LANAdapter, LAN_DISCOVERY_PORT_DEFAULT
from milipy.lan.codec import MiniMilitiaCodec
from milipy.protocol import CapabilityError


class MiniUDPHost:
    """A stand-in Mini Militia LAN host that records what clients send."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.setblocking(False)
        self.received: list[tuple[bytes, tuple[str, int]]] = []
        self.port = self.sock.getsockname()[1]
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def run(self):
        self._running = True
        loop = asyncio.get_running_loop()

        def on_read():
            try:
                while True:
                    data, addr = self.sock.recvfrom(65536)
                    self.received.append((data, addr))
            except (BlockingIOError, OSError):
                pass

        self._read_cb = on_read
        loop.add_reader(self.sock.fileno(), on_read)

    async def stop(self):
        loop = asyncio.get_event_loop()
        try:
            loop.remove_reader(self.sock.fileno())
        except (OSError, RuntimeError):
            pass
        self._running = False
        self.sock.close()


class TestLANAdapterGate(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_codec_refuses_unknown_packets(self):
        """Real bytes must NOT be decoded before the codec is proven."""
        codec = MiniMilitiaCodec()
        with self.assertRaises(NotImplementedError):
            codec.parse(b"\x00" * 16, ("127.0.0.1", 1234))

    def test_codec_refuses_unknown_actions(self):
        codec = MiniMilitiaCodec()
        with self.assertRaises(NotImplementedError):
            codec.encode({"action": "move", "direction": "right"})

    def test_empty_discovery_payload(self):
        """Discovery must do nothing until a proven payload is set."""
        codec = MiniMilitiaCodec()
        self.assertEqual(codec.discovery_payload, b"")


class TestLANAdapterWiring(unittest.TestCase):
    """Wiring tests against a fake Mini Militia host."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.host = MiniUDPHost()
        self.loop.run_until_complete(self.host.run())

    def tearDown(self):
        self.loop.run_until_complete(self.host.stop())
        self.loop.close()

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    def test_connect_opens_socket_and_returns_hello_ack(self):
        adapter = LANAdapter("127.0.0.1", port=self.host.port)
        ack = self._run(adapter.connect(lambda m: None))
        self.assertTrue(adapter.is_connected)
        self.assertEqual(ack["type"], "hello_ack")
        self.assertEqual(ack["lan"]["port"], self.host.port)
        self._run(adapter.close())
        self.assertFalse(adapter.is_connected)

    def test_send_transmits_bytes_to_host(self):
        adapter = LANAdapter("127.0.0.1", port=self.host.port)
        self._run(adapter.connect(lambda m: None))
        # The codec refuses to encode unknown actions — the honest gate.
        with self.assertRaises(NotImplementedError):
            self._run(adapter.send({"action": "fire"}))
        self._run(adapter.close())

    def test_inbound_datagram_hits_honest_codec(self):
        """A datagram from the host reaches the codec, which refuses it."""
        frames = []
        adapter = LANAdapter("127.0.0.1", port=self.host.port)
        self._run(adapter.connect(lambda m: frames.append(m)))

        async def poke():
            await asyncio.sleep(0.1)
            loop = asyncio.get_running_loop()
            await loop.sock_sendto(self.host.sock, b"fake-mm-packet", ("127.0.0.1", 9999))

        self._run(poke())
        self._run(asyncio.sleep(0.3))
        # The codec must NOT pretend to understand the bytes.
        self.assertEqual(frames, [])
        self._run(adapter.close())

    def test_invalid_host_raises(self):
        with self.assertRaises(ValueError):
            LANAdapter("", port=1234)
        with self.assertRaises(ValueError):
            LANAdapter("127.0.0.1", port=99999)

    def test_broadcast_port_default(self):
        adapter = LANAdapter("127.0.0.1", port=1)
        self.assertEqual(adapter.broadcast_port, LAN_DISCOVERY_PORT_DEFAULT)


if __name__ == "__main__":
    unittest.main()
