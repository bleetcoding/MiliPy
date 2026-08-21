"""Tests for the simulator adapter and Bot integration.

All tests run in-process with no network, no Android device, and no
Mini Militia installation — exactly what CI requires.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from milipy import Bot
from milipy.protocol import CapabilityError
from milipy.protocol_schema import ACTION_SPECS
from milipy.sim import SimAdapter, SimWorld
from milipy.state import Player, Position
from milipy.transport import WebSocketAdapter


# ---------------------------------------------------------------------------
# SimWorld
# ---------------------------------------------------------------------------


class TestSimWorld:
    def test_step_advances_tick(self):
        world = SimWorld(enemies=2)
        world.step()
        world.step()
        assert world.tick == 2

    def test_state_message_shape(self):
        world = SimWorld(enemies=1)
        world.step()
        msg = world.to_state_message()
        assert msg["type"] == "state"
        assert msg["tick"] == 1
        assert msg["player"]["id"] == "self"
        assert "frame" in msg
        assert 0.0 <= msg["player"]["position"]["nx"] <= 1.0

    def test_frame_excluded_when_disabled(self):
        world = SimWorld()
        msg = world.to_state_message(include_frame=False)
        assert "frame" not in msg

    def test_move_right_clamped(self):
        world = SimWorld()
        world.sustained_direction = "right"
        for _ in range(100):
            world.step()
        assert world.self_player.position.nx <= 1.0

    def test_move_left_clamped(self):
        world = SimWorld()
        world.sustained_direction = "left"
        for _ in range(100):
            world.step()
        assert world.self_player.position.nx >= 0.0

    def test_enemies_orbit(self):
        world = SimWorld(enemies=3)
        positions = []
        for _ in range(10):
            world.step()
            positions.append(world.enemies[0].position.nx)
        # Orbiting means the x coordinate changes over time.
        assert len(set(round(p, 4) for p in positions)) > 1


# ---------------------------------------------------------------------------
# SimAdapter contract
# ---------------------------------------------------------------------------


@pytest.fixture
def sim():
    return SimAdapter(SimWorld(enemies=2))


class TestSimAdapter:
    @pytest.mark.asyncio
    async def test_handshake_shape(self, sim):
        ack = await sim.connect(lambda msg: asyncio.sleep(0))
        assert ack["protocol"] == 1
        assert ack["capabilities"]["screen_capture"] is True
        assert ack["capabilities"]["chat"] is False

    @pytest.mark.asyncio
    async def test_frames_flow(self, sim):
        frames = []
        await sim.connect(frames.append)
        await asyncio.sleep(0.5)
        await sim.close()
        types = [f["type"] for f in frames]
        assert "state" in types
        assert "event" in types

    @pytest.mark.asyncio
    async def test_move_action_applied(self, sim):
        frames = []
        await sim.connect(frames.append)
        await sim.send({"type": "action", "action": "move", "direction": "right"})
        await asyncio.sleep(0.3)
        await sim.close()
        x_positions = [f["player"]["position"]["nx"] for f in frames if f["type"] == "state"]
        assert x_positions[-1] > x_positions[0]

    @pytest.mark.asyncio
    async def test_unsupported_action_errors(self, sim):
        errors = []
        await sim.connect(errors.append)
        await sim.send({"type": "action", "action": "throw_grenade"})
        await asyncio.sleep(0.1)
        await sim.close()
        assert any(e.get("code") == "unsupported_capability" for e in errors)

    @pytest.mark.asyncio
    async def test_ack_with_request_id(self, sim):
        replies = []
        await sim.connect(replies.append)
        await sim.send({"type": "action", "action": "ping", "request_id": "req-1"})
        await asyncio.sleep(0.1)
        await sim.close()
        assert any(r.get("type") == "ack" and r.get("request_id") == "req-1" for r in replies)

    @pytest.mark.asyncio
    async def test_unknown_action_malformed(self, sim):
        replies = []
        await sim.connect(replies.append)
        await sim.send({"type": "action", "action": "teleport"})
        await asyncio.sleep(0.1)
        await sim.close()
        assert any(r.get("code") == "malformed_message" for r in replies)

    @pytest.mark.asyncio
    async def test_custom_capabilities(self):
        adapter = SimAdapter(capabilities={"screen_capture": False})
        ack = await adapter.connect(lambda m: asyncio.sleep(0))
        assert ack["capabilities"]["screen_capture"] is False


# ---------------------------------------------------------------------------
# Bot + SimAdapter end-to-end
# ---------------------------------------------------------------------------


@pytest.fixture
def bot():
    world = SimWorld(enemies=2)
    adapter = SimAdapter(world)
    bot = Bot(adapter)
    return bot, world, adapter


class TestBotSimulator:
    @pytest.mark.asyncio
    async def test_connect_negotiates_capabilities(self, bot):
        bot, _, _ = bot
        await bot.connect_async()
        assert bot.capabilities.screen_capture
        assert not bot.capabilities.chat
        assert bot.is_connected
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_state_stream_populates_player(self, bot):
        bot, _, _ = bot
        await bot.connect_async()
        await asyncio.sleep(0.5)
        assert bot.player is not None
        assert bot.player.health == 100
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_player_seen_events(self, bot):
        bot, _, _ = bot
        seen = []
        bot.on("player_seen")(lambda player: seen.append(player))
        await bot.connect_async()
        await asyncio.sleep(0.5)
        assert len(seen) == 2
        assert all(p.id.startswith("sim-") for p in seen)
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_movement_updates_self_position(self, bot):
        bot, world, _ = bot
        await bot.connect_async()
        await asyncio.sleep(0.25)
        start = bot.player.position.nx
        bot.move("right")
        await asyncio.sleep(0.6)
        bot.stop_movement()
        await asyncio.sleep(0.25)
        assert bot.player.position.nx > start
        assert world.sustained_direction is None
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_nearest_enemy_uses_observed_state(self, bot):
        bot, _, _ = bot
        await bot.connect_async()
        await asyncio.sleep(0.5)
        enemy = bot.nearest_enemy()
        assert enemy is not None
        assert not enemy.is_self
        # The nearest enemy must be one of the tracked sim players.
        assert enemy.id in bot.players
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_nearest_player_with_no_positions(self, bot):
        bot, _, _ = bot
        bot._state.player = Player(id="self")  # no position
        assert bot.nearest_player() is None

    @pytest.mark.asyncio
    async def test_unsupported_action_raises(self, bot):
        bot, _, _ = bot
        await bot.connect_async()
        with pytest.raises(CapabilityError):
            bot.throw_grenade()
        with pytest.raises(CapabilityError):
            bot.punch()
        with pytest.raises(CapabilityError):
            bot.chat.send("hi")
        with pytest.raises(CapabilityError):
            bot.pickup()
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_aim_validation(self, bot):
        bot, _, _ = bot
        await bot.connect_async()
        with pytest.raises(ValueError):
            bot.aim(1.5, 0.5)
        # Aim at player without position must refuse to fabricate.
        with pytest.raises(ValueError):
            bot.aim_at(Player(id="ghost"))
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_state_snapshot_immutable(self, bot):
        bot, _, _ = bot
        await bot.connect_async()
        await asyncio.sleep(0.3)
        snapshot = bot.state
        snapshot.tick = 99999
        assert bot.state.tick != 99999
        await bot.disconnect_async()

    @pytest.mark.asyncio
    async def test_once_listener(self, bot):
        bot, _, _ = bot
        hits = []
        bot.once("ready")(lambda: hits.append(1))
        await bot.connect_async()
        await asyncio.sleep(0.2)
        await bot.connect_async()  # second handshake
        assert len(hits) == 1
        await bot.disconnect_async()


# ---------------------------------------------------------------------------
# Real WebSocket adapter handshake against a local fake bridge server
# ---------------------------------------------------------------------------


@pytest.fixture
async def fake_bridge_server():
    """Spin up a tiny WebSocket server speaking the bridge protocol."""
    import websockets.asyncio.server

    from milipy.protocol import encode_message, hello_message

    class Server:
        def __init__(self):
            self.received = []
            self.pairing = "TEST12"

        async def handler(self, ws):
            await ws.send(encode_message({"type": "hello_ack", "protocol": 1, "bridge_version": "0.1.0", "capabilities": {"screen_capture": True}}))
            async for raw in ws:
                self.received.append(raw)
                msg = __import__("json").loads(raw)
                if msg.get("type") == "action" and msg.get("action") == "disconnect":
                    break

    server_state = Server()

    async with websockets.asyncio.server.serve(server_state.handler, "127.0.0.1", 0) as server:
        host, port = server.sockets[0].getsockname()
        yield host, port, server_state


class TestRealWebSocketHandshake:
    @pytest.mark.asyncio
    async def test_connect_completes_handshake(self, fake_bridge_server):
        host, port, state = fake_bridge_server
        adapter = WebSocketAdapter(host, port)
        ack = await adapter.connect(lambda m: asyncio.sleep(0))
        assert ack["protocol"] == 1
        assert state.received
        first = __import__("json").loads(state.received[0])
        assert first["type"] == "hello"
        assert first["client"] == "milipy"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_unreachable_host_raises(self):
        adapter = WebSocketAdapter("127.0.0.1", 1, )
        with pytest.raises(Exception):  # noqa: BLE001
            await adapter.connect(lambda m: asyncio.sleep(0), max_reconnect_attempts=1, timeout=1.0)

    @pytest.mark.asyncio
    async def test_invalid_host_rejected(self):
        with pytest.raises(ValueError):
            WebSocketAdapter("", 8765)
        with pytest.raises(ValueError):
            WebSocketAdapter("host", 0)
        with pytest.raises(ValueError):
            WebSocketAdapter("host", 70000)

    @pytest.mark.asyncio
    async def test_malformed_server_frame_handled(self, fake_bridge_server):
        import websockets.asyncio.server

        from milipy.protocol import encode_message

        async def bad_handler(ws):
            await ws.send("this is not json at all")

        host, port, _ = fake_bridge_server

        async with websockets.asyncio.server.serve(bad_handler, "127.0.0.1", 0) as server:
            h, p = server.sockets[0].getsockname()
            adapter = WebSocketAdapter(h, p)
            with pytest.raises(Exception):  # noqa: BLE001
                await adapter.connect(lambda m: asyncio.sleep(0), max_reconnect_attempts=1, timeout=2.0)
