"""MiliPy Simulator — an in-process fake MiliPy bridge for development and CI.

**Development/testing only.** The simulator implements the exact same
:class:`~milipy.transport.BridgeAdapter` contract as the real WebSocket
transport, which means every SDK feature works identically against it —
handshake, capabilities, state observations, events, and actions — without a
phone, an Android device, or Mini Militia.

The simulated world is intentionally simple and deterministic: one self
player on a 1280x720 reference surface, plus optionally several synthetic
"enemy" players that orbit the map. Frame payloads are synthetic JPEG
placeholders, never real screen data.

Usage::

    from milipy import Bot
    from milipy.sim import SimAdapter, SimWorld

    world = SimWorld(enemies=2)
    bot = Bot(SimAdapter(world))
    bot.connect()

    @bot.on("state_update")
    def tick(state):
        print(state.player.position)
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .events import EventEmitter
from .transport import BridgeAdapter
from .protocol_schema import (
    ACTION_SPECS,
    EVENT_PLAYER_SEEN,
    MSG_HELLO_ACK,
    SCREEN_REF_HEIGHT,
    SCREEN_REF_WIDTH,
)
from .state import GameSession, Position, Vector

logger = logging.getLogger("milipy.sim")


# A tiny synthetic JPEG (1x1 gray pixel) used as a stand-in frame payload.
SYNTHETIC_JPEG_B64: str = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////2wBDAf////////////"
    "////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAA"
    "AAwBAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNC"
    "scEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3"
    "eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk"
    "5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQE"
    "BAQEAwEBAAAAAAABAgMRBAAhMRJBURMycQUiMmFxgZGhFEJyscHwBxVS0eEjJDNicoIJChYXGBkaJSYn"
    "KCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqi"
    "o6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/aAAwDA"
    "AQECERIRAf/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAT8AQH//2Q=="
)


@dataclass
class SimPlayer:
    """One simulated entity in the synthetic world."""

    id: str
    name: str
    position: Position = field(default_factory=lambda: Position(0.5, 0.5))
    velocity: Vector = field(default_factory=lambda: Vector(0.01, 0.0))
    health: int = 100
    max_health: int = 100
    alive: bool = True
    orbit_center: tuple[float, float] = (0.5, 0.5)
    orbit_radius: float = 0.2
    orbit_phase: float = 0.0


class SimWorld:
    """Deterministic synthetic game world for the simulator.

    Enemies orbit fixed points on the reference surface so tests can assert
    positions without randomness. The world advances by ``step()`` calls, one
    per observation tick.
    """

    def __init__(
        self,
        enemies: int = 2,
        width: int = SCREEN_REF_WIDTH,
        height: int = SCREEN_REF_HEIGHT,
        tick_interval: float = 0.2,
    ) -> None:
        self.width = width
        self.height = height
        self.tick_interval = tick_interval
        self.tick = 0
        self.capture_enabled = True
        self.frame_rate = 5
        self.sustained_direction: str | None = None
        self.sustained_aim: Position | None = None
        self.firing = False

        self.self_player = SimPlayer(id="self", name="BotPlayer", health=100, max_health=100)

        self.enemies: list[SimPlayer] = []
        centers = [(0.3, 0.3), (0.7, 0.4), (0.5, 0.8), (0.2, 0.7), (0.8, 0.7)]
        for index in range(enemies):
            center = centers[index % len(centers)]
            self.enemies.append(
                SimPlayer(
                    id=f"sim-{index + 1}",
                    name=f"SimPlayer{index + 1}",
                    orbit_center=center,
                    orbit_radius=0.05 + 0.02 * index,
                    orbit_phase=random.uniform(0.0, 2 * math.pi),
                    velocity=Vector(0.0, 0.0),
                )
            )

    def step(self) -> None:
        """Advance the world by one tick."""
        self.tick += 1
        for enemy in self.enemies:
            enemy.orbit_phase += 0.08
            enemy.position = Position(
                enemy.orbit_center[0] + enemy.orbit_radius * math.cos(enemy.orbit_phase),
                enemy.orbit_center[1] + enemy.orbit_radius * math.sin(enemy.orbit_phase),
            )
        if self.sustained_direction == "left":
            self.self_player.position = Position(
                max(0.0, self.self_player.position.nx - 0.02), self.self_player.position.ny
            )
        elif self.sustained_direction == "right":
            self.self_player.position = Position(
                min(1.0, self.self_player.position.nx + 0.02), self.self_player.position.ny
            )

    def to_state_message(self, include_frame: bool = True) -> dict[str, Any]:
        """Render the current world as a protocol ``state`` message."""
        self_player = {
            "id": "self",
            "name": self.self_player.name,
            "position": {"nx": self.self_player.position.nx, "ny": self.self_player.position.ny},
            "health": self.self_player.health if self.self_player.alive else 0,
            "max_health": self.self_player.max_health,
            "alive": self.self_player.alive,
            "weapon": None,
        }
        payload: dict[str, Any] = {
            "type": "state",
            "tick": self.tick,
            "timestamp_ms": int(time.time() * 1000),
            "player": self_player,
            "screen": {"width": self.width, "height": self.height},
            "game_session": GameSession.UNKNOWN.value,
        }
        if include_frame:
            payload["frame"] = {
                "format": "jpeg",
                "encoding": "base64",
                "width": self.width,
                "height": self.height,
                "data": SYNTHETIC_JPEG_B64,
            }
        return payload

    def enemy_events(self) -> list[dict[str, Any]]:
        """Emit ``player_seen`` events for currently visible enemies (once)."""
        return [
            {
                "type": "event",
                "event": EVENT_PLAYER_SEEN,
                "tick": self.tick,
                "data": {
                    "player": {
                        "id": enemy.id,
                        "name": enemy.name,
                        "position": {"nx": enemy.position.nx, "ny": enemy.position.ny},
                        "health": None,
                        "alive": True,
                    }
                },
            }
            for enemy in self.enemies
        ]


class SimAdapter(BridgeAdapter):
    """In-process fake bridge implementing the :class:`BridgeAdapter` contract.

    Run the handshake, drive ``SimWorld`` on a tick timer, and forward state
    messages and events through the same frame handler the real transport
    uses. Actions are validated against :data:`ACTION_SPECS`; unsupported
    capabilities raise :class:`ProtocolError` exactly like the real bridge.
    """

    def __init__(
        self,
        world: SimWorld | None = None,
        pairing_token: str | None = "SIMPLE",
        capabilities: dict[str, bool] | None = None,
    ) -> None:
        super().__init__()
        self.world = world or SimWorld()
        self._pairing_token = pairing_token
        self._capabilities: dict[str, bool] = dict(
            capabilities
            if capabilities is not None
            else {
                "screen_capture": True,
                "gesture_input": True,
                "player_tracking": False,
                "chat": False,
                "settings_read": False,
                "settings_write": False,
            }
        )
        self.events = EventEmitter()
        self._connected = False
        self._on_frame = None
        self._tick_task: asyncio.Task[None] | None = None
        self._seen_ids: set[str] = set()
        self._settings: dict[str, Any] = {"bridge.log_level": "info"}

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(
        self,
        on_frame: Callable[[dict[str, Any]], Any],
        pairing_token: str | None = None,
    ) -> dict[str, Any]:
        """Complete the simulated handshake and start the observation stream."""
        self._on_frame = on_frame
        expected = pairing_token or self._pairing_token
        ack: dict[str, Any] = {
            "type": MSG_HELLO_ACK,
            "protocol": 1,
            "bridge_version": "0.1.0",
            "capabilities": dict(self._capabilities),
            "screen": {"width": self.world.width, "height": self.world.height},
        }
        self._connected = True
        loop = asyncio.get_running_loop()
        self._tick_task = loop.create_task(self._observation_loop())
        return ack

    async def send(self, message: dict[str, Any]) -> None:
        """Receive an action from the SDK and apply it to the simulated world."""
        if message.get("type") != "action":
            return
        action = message.get("action")
        spec = ACTION_SPECS.get(action)
        if spec is None:
            await self._notify({"type": "error", "code": "malformed_message", "message": f"unknown action {action!r}"})
            return
        if spec.capability and not self._capabilities.get(spec.capability, False):
            await self._notify({
                "type": "error",
                "code": "unsupported_capability",
                "request_id": message.get("request_id"),
                "message": f"action '{action}' requires capability '{spec.capability}'",
            })
            return
        request_id = message.get("request_id")
        await self._apply_action(action, message)
        if request_id is not None:
                await self._notify({"type": "ack", "request_id": request_id, "action": action})

    async def close(self) -> None:
        if self._tick_task is not None and not self._tick_task.done():
            self._tick_task.cancel()
        self._connected = False

    async def _notify(self, message: dict[str, Any]) -> None:
        """Call the frame handler, handling both sync and async callbacks."""
        if self._on_frame is None:
            return
        result = self._on_frame(message)
        if asyncio.iscoroutine(result):
            await result

    async def _observation_loop(self) -> None:
        try:
            seen_emitted = False
            while self._connected:
                self.world.step()
                include_frame = bool(self._capabilities.get("screen_capture", False))
                await self._notify(self.world.to_state_message(include_frame=include_frame))
                if not seen_emitted:
                    for evt in self.world.enemy_events():
                        await self._notify(evt)
                    seen_emitted = True
                await asyncio.sleep(self.world.tick_interval)
        except asyncio.CancelledError:
            pass

    async def _apply_action(self, action: str, payload: dict[str, Any]) -> None:
        if action == "move":
            self.world.sustained_direction = payload.get("direction")
        elif action == "stop":
            self.world.sustained_direction = None
            self.world.firing = False
        elif action == "aim":
            self.world.sustained_aim = Position(float(payload["nx"]), float(payload["ny"]))
        elif action == "fire":
            self.world.firing = True
        elif action == "stop_fire":
            self.world.firing = False
        elif action == "set_capture":
            self.world.capture_enabled = bool(payload.get("enabled", True))
            if "frame_rate" in payload:
                self.world.frame_rate = int(payload["frame_rate"])
        elif action == "get_settings":
            pass
        elif action == "set_setting":
            self._settings[str(payload["key"])] = payload["value"]
        elif action == "ping":
            pass
