"""Bridge service-lifecycle tests (v0.3.0).

The real bridge's WebSocket listener lives in an Android foreground service
(`MiliPyService`), which owns the bridge's lifetime independently of the
UI activity. This module exercises the SDK-visible half of that contract
— the `stop_bridge` action, its protocol spec, and the simulator's
matching teardown — entirely in-process, no Android device needed.

What these tests prove:
- `stop_bridge` is a first-class protocol action with a validation spec
  (no capability gate, no payload).
- The action builder exposes it.
- The simulator tears down its observation loop on `stop_bridge`, mirroring
  the real bridge's foreground-service teardown.
- The SDK's `stop_bridge_async()` dispatches it.

What they cannot prove (see docs/device-validation.md): that Android
actually keeps the service alive after the activity dies — that requires a
real device and is covered by the manual on-device procedure.
"""

import asyncio

import pytest

from milipy import Bot
from milipy.protocol_schema import ACTION_SPECS
from milipy.sim import SimAdapter, SimWorld
from milipy.transport import WebSocketAdapter


# ---------------------------------------------------------------------------
# Protocol spec
# ---------------------------------------------------------------------------


class TestStopBridgeSpec:
    def test_spec_exists_and_requires_no_capability(self):
        spec = ACTION_SPECS["stop_bridge"]
        assert spec.capability is None, "stop_bridge must never raise CapabilityError"
        assert not spec.required

    def test_builder_exposes_stop_bridge(self):
        builder_actions = dir(SimAdapter(SimWorld())._settings)  # noqa — no-op
        from milipy.actions import ActionBuilder

        name, payload = ActionBuilder({"screen_capture": True}).stop_bridge()
        assert name == "stop_bridge"
        assert payload == {}


# ---------------------------------------------------------------------------
# Simulator teardown mirrors the real bridge
# ---------------------------------------------------------------------------


class TestSimulatorTeardown:
    @pytest.mark.asyncio
    async def test_stop_bridge_stops_observation_loop(self):
        """After stop_bridge the sim stops pushing state frames."""
        world = SimWorld()
        adapter = SimAdapter(world)
        frames = []
        await adapter.connect(frames.append)
        await asyncio.sleep(0.45)
        count_before = len(frames)
        assert count_before > 0

        # Send stop_bridge with an id — the ack must come back accepted.
        await adapter.send({"type": "action", "action": "stop_bridge", "id": "action-9"})
        await asyncio.sleep(0.3)

        acks = [f for f in frames if f.get("type") == "ack" and f.get("id") == "action-9"]
        assert len(acks) == 1
        assert acks[0]["status"] == "accepted"
        # The observation loop must have died, exactly like the real
        # listener dying with its foreground service.
        count_after = len(frames)
        await asyncio.sleep(0.4)
        assert len(frames) == count_after
        assert not adapter.is_connected

    @pytest.mark.asyncio
    async def test_bot_stop_bridge_async_dispatches(self):
        """The Bot helper builds and sends the shutdown action."""
        world = SimWorld()
        adapter = SimAdapter(world)
        bot = Bot(adapter)
        await bot.connect_async()
        await bot.stop_bridge_async()
        await asyncio.sleep(0.3)
        assert adapter._bridge_shutting_down  # type: ignore[attr-defined]
        await bot.disconnect_async()


# ---------------------------------------------------------------------------
# Real WebSocket transport: explicit shutdown closes the listener
# ---------------------------------------------------------------------------


@pytest.fixture
async def shutdown_bridge_server():
    """Tiny WebSocket server that shuts down its listener on stop_bridge."""
    import json

    import websockets.asyncio.server

    from milipy.protocol import encode_message

    class State:
        def __init__(self):
            self.received = []
            self.shutdown = asyncio.Event()
            self.pairing = "TEST12"

        async def handler(self, ws):
            await ws.send(encode_message({
                "type": "hello_ack", "protocol": 1, "bridge_version": "0.3.0",
                "capabilities": {"screen_capture": True, "stop_bridge": True},
            }))
            try:
                async for raw in ws:
                    self.received.append(raw)
                    msg = json.loads(raw)
                    if msg.get("type") == "action" and msg.get("action") == "stop_bridge":
                        request_id = msg.get("request_id")
                        if request_id:
                            await ws.send(encode_message({
                                "type": "ack", "request_id": request_id,
                                "action": "stop_bridge", "status": "accepted",
                            }))
                        self.shutdown.set()
                        break
            except websockets.ConnectionClosed:
                pass

    state = State()
    async with websockets.asyncio.server.serve(state.handler, "127.0.0.1", 0) as server:
        host, port = server.sockets[0].getsockname()
        yield host, port, state


class TestWebSocketShutdown:
    @pytest.mark.asyncio
    async def test_stop_bridge_closes_remote_listener(self, shutdown_bridge_server):
        host, port, state = shutdown_bridge_server
        adapter = WebSocketAdapter(host, port)
        await adapter.connect(lambda m: asyncio.sleep(0))
        await adapter.send({
            "type": "action", "action": "stop_bridge", "request_id": "req-stop",
        })
        # Wait for the server-side shutdown to complete.
        await asyncio.wait_for(state.shutdown.wait(), timeout=2.0)
        # The bridge closed the connection from its side; the SDK transport
        # must end up disconnected without an exception.
        await asyncio.sleep(0.3)
        assert not adapter.is_connected
        assert any('"stop_bridge"' in raw or "stop_bridge" in raw for raw in state.received)
        await adapter.close()
