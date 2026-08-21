"""Tests for state models, parsing, and the event system."""

import pytest

from milipy.events import EventEmitter
from milipy.state import (
    Capabilities,
    GameState,
    Player,
    Position,
    Vector,
    Weapon,
    parse_player,
)


# ---------------------------------------------------------------------------
# Position / Vector
# ---------------------------------------------------------------------------


class TestPosition:
    def test_valid(self):
        pos = Position(0.5, 0.25)
        assert pos.nx == 0.5 and pos.ny == 0.25

    def test_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            Position(1.5, 0.5)
        with pytest.raises(ValueError):
            Position(-0.1, 0.0)

    def test_distance(self):
        a = Position(0.0, 0.0)
        b = Position(0.3, 0.4)
        assert abs(a.distance_to(b) - 0.5) < 1e-9

    def test_immutable(self):
        pos = Position(0.1, 0.1)
        with pytest.raises(AttributeError):
            pos.nx = 0.2  # type: ignore[misc]


class TestVector:
    def test_magnitude(self):
        assert abs(Vector(3.0, 4.0).magnitude - 5.0) < 1e-9

    def test_is_zero(self):
        assert Vector(0.0, 0.0).is_zero
        assert not Vector(0.0, 1.0).is_zero


# ---------------------------------------------------------------------------
# Player / Weapon / parsing
# ---------------------------------------------------------------------------


class TestPlayerParsing:
    def test_full_payload(self):
        player = parse_player(
            {
                "id": "p1",
                "name": "Alice",
                "position": {"nx": 0.3, "ny": 0.6},
                "velocity": {"vx": 0.01, "vy": 0.0},
                "health": 80,
                "max_health": 100,
                "weapon": {"id": "w1", "name": "Uzi", "ammo": 20, "max_ammo": 30, "equipped": True},
                "team": "red",
                "alive": True,
            },
            "p1",
        )
        assert player.name == "Alice"
        assert player.position == Position(0.3, 0.6)
        assert player.velocity == Vector(0.01, 0.0)
        assert player.health == 80
        assert player.weapon.name == "Uzi"
        assert player.team == "red"
        assert player.is_alive

    def test_unknown_fields_ignored(self):
        player = parse_player({"id": "x", "unknown_field": 42, "alive": False}, "x")
        assert player.id == "x"
        assert not player.is_alive

    def test_nulls_become_none(self):
        player = parse_player({"id": "ghost", "name": None, "health": None}, "ghost")
        assert player.name is None
        assert player.health is None
        assert player.weapon is None

    def test_bad_position_ignored(self):
        player = parse_player({"id": "y", "position": "bad"}, "y")
        assert player.position is None

    def test_non_dict_raises(self):
        with pytest.raises(ValueError):
            parse_player("not a dict", "z")  # type: ignore[arg-type]

    def test_self_player(self):
        assert Player(id="self").is_self
        assert not Player(id="other").is_self


class TestWeapon:
    def test_repr_partial_ammo(self):
        weapon = Weapon(id="w2", name="Shotgun", ammo=4)
        assert "ammo=?" in repr(weapon)


class TestGameState:
    def test_snapshot_is_deep_copy(self):
        state = GameState(tick=1)
        state.players["p1"] = Player(id="p1", health=10)
        snap = state.snapshot()
        snap.players["p1"].health = 99
        assert state.players["p1"].health == 10


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_from_dict(self):
        caps = Capabilities.from_dict({"screen_capture": True, "chat": 1})
        assert caps.screen_capture
        assert caps.chat

    def test_supports_known_and_extra(self):
        caps = Capabilities.from_dict({"grenades": True})
        assert caps.supports("grenades")
        assert not caps.supports("chat")

    def test_to_dict_round_trip(self):
        raw = {"screen_capture": True, "player_tracking": False}
        caps = Capabilities.from_dict(raw)
        back = caps.to_dict()
        assert back["screen_capture"] is True
        assert back["player_tracking"] is False


# ---------------------------------------------------------------------------
# EventEmitter
# ---------------------------------------------------------------------------


class TestEventEmitter:
    def test_on_and_emit(self):
        emitter = EventEmitter()
        results = []

        @emitter.on("tick")
        def handle(value=0):
            results.append(value)

        emitter.emit("tick", value=1)
        emitter.emit("tick", value=2)
        assert results == [1, 2]

    def test_once_fires_once(self):
        emitter = EventEmitter()
        results = []

        @emitter.once("x")
        def handle():
            results.append(1)

        emitter.emit("x")
        emitter.emit("x")
        assert results == [1]

    def test_off(self):
        emitter = EventEmitter()
        results = []

        def handle():
            results.append(1)

        emitter.on("y")(handle)
        emitter.emit("y")
        emitter.off("y", handle)
        emitter.emit("y")
        assert results == [1]

    def test_listener_exception_swallowed(self, caplog):
        emitter = EventEmitter()
        called = []

        @emitter.on("z")
        def bad():
            raise RuntimeError("boom")

        @emitter.on("z")
        def good():
            called.append(1)

        count = emitter.emit("z")
        # The failing listener is not counted; the working one is.
        assert count == 1
        assert called == [1]
        assert "boom" in caplog.text

    def test_remove_all(self):
        emitter = EventEmitter()
        emitter.on("a")(lambda: None)
        emitter.on("b")(lambda: None)
        emitter.remove_all_listeners("a")
        assert emitter.listeners("a") == []
        assert len(emitter.listeners("b")) == 1
        emitter.remove_all_listeners()
        assert emitter.listeners("b") == []
