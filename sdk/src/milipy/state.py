"""State models for the MiliPy SDK.

These are plain, typed data classes representing everything the SDK knows
about the observed world. The guiding rule is honesty: a field is ``None``
when the value cannot be observed, and the SDK never invents numbers that the
bridge did not supply. Models are deliberately immutable after creation so
that event handlers can rely on a stable snapshot.

Coordinate convention: positions are stored normalized (``nx``/``ny`` in
``[0.0, 1.0]``) with the origin at the top-left corner of the screen; ``x``
increases to the right and ``y`` increases downward. The simulator additionally
tracks absolute reference pixels (1280x720) for deterministic testing.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Position:
    """A point in normalized screen coordinates."""

    nx: float
    """Horizontal position, 0.0 (left edge) to 1.0 (right edge)."""

    ny: float
    """Vertical position, 0.0 (top edge) to 1.0 (bottom edge)."""

    def __post_init__(self) -> None:
        if not (0.0 <= self.nx <= 1.0) or not (0.0 <= self.ny <= 1.0):
            raise ValueError(f"Position must be normalized: ({self.nx}, {self.ny})")

    def distance_to(self, other: Position) -> float:
        """Euclidean distance between two normalized positions."""
        return ((self.nx - other.nx) ** 2 + (self.ny - other.ny) ** 2) ** 0.5


@dataclass(frozen=True)
class Vector:
    """A velocity or offset expressed in normalized units per tick."""

    vx: float
    vy: float

    @property
    def magnitude(self) -> float:
        return (self.vx**2 + self.vy**2) ** 0.5

    @property
    def is_zero(self) -> bool:
        return self.vx == 0.0 and self.vy == 0.0


@dataclass(frozen=True)
class Weapon:
    """A weapon observed or tracked by the SDK.

    Fields that the bridge cannot observe are left ``None``; they must never
    be guessed from weapon names or any other heuristic.
    """

    id: str
    name: str | None = None
    ammo: int | None = None
    max_ammo: int | None = None
    equipped: bool | None = None

    def __repr__(self) -> str:
        ammo = f"{self.ammo}/{self.max_ammo}" if self.ammo is not None and self.max_ammo is not None else "?"
        return f"Weapon(id={self.id!r}, name={self.name!r}, ammo={ammo}, equipped={self.equipped})"


@dataclass
class Player:
    """A player entity observed in the game world.

    The SDK's own bot player is distinguished by ``id == "self"``. Every other
    observed field is optional — unknown values are ``None`` rather than
    fabricated defaults.
    """

    id: str
    name: str | None = None
    position: Position | None = None
    velocity: Vector | None = None
    health: int | None = None
    max_health: int | None = None
    weapon: Weapon | None = None
    team: str | None = None
    alive: bool | None = None

    @property
    def is_self(self) -> bool:
        return self.id == "self"

    @property
    def is_alive(self) -> bool:
        """True only when liveness is actually observed as alive."""
        return self.alive is True

    def __repr__(self) -> str:
        return (
            f"Player(id={self.id!r}, name={self.name!r}, position={self.position!r}, "
            f"health={self.health}, alive={self.alive})"
        )


@dataclass(frozen=True)
class Capabilities:
    """Feature flags reported by the bridge during handshake."""

    screen_capture: bool = False
    gesture_input: bool = False
    player_tracking: bool = False
    chat: bool = False
    settings_read: bool = False
    settings_write: bool = False
    _extra: dict[str, bool] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Capabilities:
        known = {
            "screen_capture",
            "gesture_input",
            "player_tracking",
            "chat",
            "settings_read",
            "settings_write",
        }
        kwargs = {key: bool(value) for key, value in raw.items() if key in known}
        extra = {key: bool(value) for key, value in raw.items() if key not in known}
        return cls(**kwargs, _extra=extra)

    def supports(self, feature: str) -> bool:
        """Look up any capability flag, known or extra."""
        if feature in vars(self):
            return bool(getattr(self, feature))
        return bool(self._extra.get(feature))

    def to_dict(self) -> dict[str, bool]:
        """Serialize to the same shape the bridge uses."""
        out: dict[str, bool] = {
            "screen_capture": self.screen_capture,
            "gesture_input": self.gesture_input,
            "player_tracking": self.player_tracking,
            "chat": self.chat,
            "settings_read": self.settings_read,
            "settings_write": self.settings_write,
        }
        out.update(self._extra)
        return out


@dataclass
class GameState:
    """A single point-in-time observation of the world.

    ``players`` is a mapping from player id to the latest observed ``Player``.
    Handlers should treat a state object as immutable — the Bot produces a
    fresh copy for each emission.
    """

    tick: int
    timestamp_ms: int | None = None
    player: Player | None = None
    players: dict[str, Player] = field(default_factory=dict)
    frame: dict[str, Any] | None = None
    screen_width: int | None = None
    screen_height: int | None = None

    def snapshot(self) -> GameState:
        """Return a deep copy safe for handler mutation."""
        return copy.deepcopy(self)


def parse_player(payload: dict[str, Any], player_id: str) -> Player:
    """Convert a protocol ``player`` object into a ``Player``.

    Missing or ``null`` fields become ``None``. Unknown fields are ignored.
    Raises ``ValueError`` only for structurally invalid numbers.
    """
    if not isinstance(payload, dict):
        raise ValueError("player payload must be an object")

    def optional_pos(raw: Any) -> Position | None:
        if not isinstance(raw, dict):
            return None
        try:
            return Position(float(raw["nx"]), float(raw["ny"]))
        except (KeyError, TypeError, ValueError):
            return None

    def optional_vec(raw: Any) -> Vector | None:
        if not isinstance(raw, dict):
            return None
        try:
            return Vector(float(raw["vx"]), float(raw["vy"]))
        except (KeyError, TypeError, ValueError):
            return None

    weapon_payload = payload.get("weapon")
    weapon: Weapon | None = None
    if isinstance(weapon_payload, dict) and isinstance(weapon_payload.get("id"), str):
        weapon = Weapon(
            id=str(weapon_payload["id"]),
            name=weapon_payload.get("name"),
            ammo=int(weapon_payload["ammo"]) if isinstance(weapon_payload.get("ammo"), int) else None,
            max_ammo=(
                int(weapon_payload["max_ammo"])
                if isinstance(weapon_payload.get("max_ammo"), int)
                else None
            ),
            equipped=bool(weapon_payload["equipped"]) if isinstance(weapon_payload.get("equipped"), bool) else None,
        )

    health = payload.get("health")
    health = int(health) if isinstance(health, (int, float)) else None
    max_health = payload.get("max_health")
    max_health = int(max_health) if isinstance(max_health, (int, float)) else None

    return Player(
        id=player_id,
        name=payload.get("name") if isinstance(payload.get("name"), str) else None,
        position=optional_pos(payload.get("position")),
        velocity=optional_vec(payload.get("velocity")),
        health=health,
        max_health=max_health,
        weapon=weapon,
        team=payload.get("team") if isinstance(payload.get("team"), str) else None,
        alive=bool(payload["alive"]) if isinstance(payload.get("alive"), bool) else None,
    )
