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
from enum import Enum
from typing import Any

from .protocol_schema import (
    CAP_AVAILABLE,
    CAP_NOT_VALIDATED,
    CAP_PERMISSION_REQUIRED,
    CAP_STATES,
    CAP_UNAVAILABLE,
    CAP_UNSUPPORTED,
)


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
    """Feature flags reported by the bridge during handshake.

    Backwards-compatible with the protocol v1 boolean flags while also
    accepting the richer v1.1 objects::

        {"screen_capture": true}                     # v1 boolean
        {"screen_capture": {"state": "available"}}    # v1.1 rich status

    The ergonomic boolean API stays: ``caps.screen_capture`` is still a
    ``bool``. Rich detail is reachable through ``caps.status("screen_capture")``.
    """

    screen_capture: bool = False
    gesture_input: bool = False
    player_tracking: bool = False
    chat: bool = False
    settings_read: bool = False
    settings_write: bool = False
    _extra: dict[str, bool] = field(default_factory=dict, repr=False)

    @staticmethod
    def _parse_flag(value: Any) -> tuple[bool, CapabilityStatus]:
        if isinstance(value, dict):
            state = value.get("state")
            if isinstance(state, str) and state in CAP_STATES:
                return (
                    state == CAP_AVAILABLE,
                    CapabilityStatus(
                        state=state,
                        validated_on_device=bool(value.get("validated_on_device", False)),
                    ),
                )
            return False, CapabilityStatus.unavailable()
        return bool(value), CapabilityStatus.from_bool(bool(value))

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
        kwargs: dict[str, bool] = {}
        extra: dict[str, bool] = {}
        for key, value in raw.items():
            flag, _status = cls._parse_flag(value)
            if key in known:
                kwargs[key] = flag
            else:
                extra[key] = flag
        return cls(**kwargs, _extra=extra)

    def supports(self, feature: str) -> bool:
        """Look up any capability flag, known or extra."""
        if feature in vars(self):
            return bool(getattr(self, feature))
        return bool(self._extra.get(feature))

    def status(self, feature: str) -> CapabilityStatus:
        """Rich status for a capability flag — never silently fake data.

        Unknown feature names return ``CapabilityStatus.unsupported()`` so
        callers can distinguish *not implemented* from *unavailable*.
        """
        if feature in vars(self):
            return CapabilityStatus.from_bool(bool(getattr(self, feature)))
        if feature in self._extra:
            return CapabilityStatus.from_bool(bool(self._extra[feature]))
        return CapabilityStatus.unsupported()

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


@dataclass(frozen=True)
class CapabilityStatus:
    """Rich capability state — more informative than a bare boolean.

    The five states express exactly what the bridge knows about each
    feature, so the SDK never confuses *implemented* with *available* with
    *validated against a real device*. A capability is only usable for
    actions when ``is_available`` is true; ``is_validated`` stays false
    until a real Mini Militia device test has proven it (see
    ``docs/device-validation.md``).
    """

    state: str
    """One of the ``CAP_*`` constants from :mod:`milipy.protocol_schema`."""

    def __post_init__(self) -> None:
        if self.state not in CAP_STATES:
            raise ValueError(f"unknown capability state: {self.state!r}")

    @property
    def is_available(self) -> bool:
        return self.state == CAP_AVAILABLE

    @property
    def needs_permission(self) -> bool:
        return self.state in (CAP_PERMISSION_REQUIRED,)

    @property
    def is_validated(self) -> bool:
        """True only when the capability has been proven on a real device."""
        return self.state == CAP_AVAILABLE and self.validated_on_device

    validated_on_device: bool = False

    @classmethod
    def available(cls, validated: bool = False) -> CapabilityStatus:
        return cls(state=CAP_AVAILABLE, validated_on_device=validated)

    @classmethod
    def unavailable(cls) -> CapabilityStatus:
        return cls(state=CAP_UNAVAILABLE)

    @classmethod
    def permission_required(cls) -> CapabilityStatus:
        return cls(state=CAP_PERMISSION_REQUIRED)

    @classmethod
    def unsupported(cls) -> CapabilityStatus:
        return cls(state=CAP_UNSUPPORTED)

    @classmethod
    def not_validated(cls) -> CapabilityStatus:
        return cls(state=CAP_NOT_VALIDATED)

    @classmethod
    def from_bool(cls, value: bool) -> CapabilityStatus:
        """Backwards-compatible mapping of the v1 boolean capability flag."""
        return cls.available(validated=False) if value else cls.unavailable()

    def __bool__(self) -> bool:
        return self.is_available

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CapabilityStatus):
            return self.state == other.state
        if isinstance(other, bool):
            return self.is_available == other
        return NotImplemented

    def __repr__(self) -> str:
        validated = " validated" if self.validated_on_device else ""
        return f"CapabilityStatus({self.state}{validated})"


class GameSession(str, Enum):
    """High-level game session state as observed by the bridge.

    The bridge derives this from what it can *legitimately* observe (the
    application's visible UI and screen content). Until the perception layer
    actually supports fine-grained detection, the bridge reports ``UNKNOWN``;
    ``NONE`` means Mini Militia is not running on the device at all.
    """

    NONE = "none"
    """Mini Militia is not running on the Android device."""
    UNKNOWN = "unknown"
    """Mini Militia may be running, but the bridge cannot determine the screen."""
    MAIN_MENU = "main_menu"
    LAN_MENU = "lan_menu"
    LOBBY_VISIBLE = "lobby_visible"
    """A LAN lobby is visible on screen but the device has not joined."""
    IN_LOBBY = "in_lobby"
    """The device has joined a LAN lobby (observed from the lobby UI)."""
    IN_GAME = "in_game"
    GAME_OVER = "game_over"


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
    game_session: GameSession | None = None
    """Current high-level game session state, if the bridge can observe it."""

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
