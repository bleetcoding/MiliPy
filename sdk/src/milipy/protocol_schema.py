"""MiliPy Bridge Protocol — schema and constants.

This module is the single source of truth for every protocol string, message
type name, capability flag, and validation rule used by the MiliPy Bridge
Protocol (see ``protocol/protocol.md``). Neither the SDK, the bridge, nor the
simulator may invent protocol strings — they must import from here.

Protocol version 1 covers all types defined below. Adding optional fields or
message types is backwards-compatible; anything else requires a new major
protocol version.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The major protocol version this SDK speaks.
PROTOCOL_VERSION: int = 1

#: SDK identifier sent in the ``hello`` handshake.
CLIENT_ID: str = "milipy"

#: SDK version sent in the ``hello`` handshake. Bumped with releases.
CLIENT_VERSION: str = "0.1.0"

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------

# Client → Bridge
MSG_HELLO: str = "hello"
MSG_AUTH: str = "auth"
MSG_ACTION: str = "action"

# Bridge → Client
MSG_HELLO_ACK: str = "hello_ack"
MSG_AUTH_REQUIRED: str = "auth_required"
MSG_AUTH_ERROR: str = "auth_error"
MSG_PROTOCOL_ERROR: str = "protocol_error"
MSG_STATE: str = "state"
MSG_EVENT: str = "event"
MSG_ERROR: str = "error"
MSG_ACK: str = "ack"
MSG_RESULT: str = "result"

# ---------------------------------------------------------------------------
# Auth error reasons
# ---------------------------------------------------------------------------

AUTH_INVALID_TOKEN: str = "invalid_token"
AUTH_TOO_MANY_ATTEMPTS: str = "too_many_attempts"
AUTH_PROTOCOL_MISMATCH: str = "protocol_mismatch"

# ---------------------------------------------------------------------------
# Protocol error reasons
# ---------------------------------------------------------------------------

PROTOCOL_UNSUPPORTED_VERSION: str = "unsupported_version"

# ---------------------------------------------------------------------------
# Async error codes
# ---------------------------------------------------------------------------

ERR_MALFORMED_MESSAGE: str = "malformed_message"
ERR_UNSUPPORTED_CAPABILITY: str = "unsupported_capability"
ERR_CAPTURE_UNAVAILABLE: str = "capture_unavailable"
ERR_INTERNAL: str = "internal_error"

# ---------------------------------------------------------------------------
# Capability flags
# ---------------------------------------------------------------------------

#: Boolean feature flags the bridge reports during handshake.
ALL_CAPABILITIES: tuple[str, ...] = (
    "screen_capture",
    "gesture_input",
    "player_tracking",
    "chat",
    "settings_read",
    "settings_write",
)

# ---------------------------------------------------------------------------
# Action names and their validation rules
# ---------------------------------------------------------------------------

VALID_DIRECTIONS: tuple[str, ...] = ("left", "right", "up", "down")

#: Capability required (if any) to execute an action, and the payload fields
#: it accepts. ``None`` means the action is always supported by a compliant
#: bridge. An action not listed here is unknown and must be rejected.
@dataclass(frozen=True)
class ActionSpec:
    """Validation specification for a protocol action."""

    capability: str | None
    """Capability flag that must be ``True`` for this action to be available.

    ``None`` means the action is unconditionally supported by protocol 1."""

    fields: tuple[str, ...]
    """Payload field names the action may carry."""

    required: tuple[str, ...] = ()
    """Payload field names that must be present."""

    enum_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Fields whose value must be one of the listed strings."""

    numeric_fields: tuple[str, ...] = ()
    """Fields whose value must be a number in [0.0, 1.0] (normalized coords)."""

    int_fields: tuple[str, ...] = ()
    """Fields whose value must be an integer."""


#: Every action defined by protocol version 1.
ACTION_SPECS: dict[str, ActionSpec] = {
    # Movement
    "move": ActionSpec(None, ("direction",), ("direction",), {"direction": VALID_DIRECTIONS}),
    "stop": ActionSpec(None, (), (), {}),
    "set_control": ActionSpec(
        None,
        ("left", "right", "up", "down", "jump", "jetpack"),
        (),
        {},
    ),
    "jump": ActionSpec(None, (), (), {}),
    "crouch": ActionSpec(None, (), (), {}),
    # Capture
    "set_capture": ActionSpec(
        "screen_capture",
        ("enabled", "frame_rate", "include_frame"),
        ("enabled",),
        {},
    ),
    "request_state": ActionSpec(None, (), (), {}),
    # Aim
    "aim": ActionSpec("gesture_input", ("nx", "ny"), ("nx", "ny"), {}, numeric_fields=("nx", "ny")),
    "aim_at": ActionSpec(
        "gesture_input", ("target",), ("target",), {}
    ),
    # Combat
    "fire": ActionSpec("gesture_input", (), (), {}),
    "stop_fire": ActionSpec("gesture_input", (), (), {}),
    "punch": ActionSpec("gesture_input", (), (), {}),
    "throw_grenade": ActionSpec("grenades", (), (), {}),
    # Weapons
    "pickup": ActionSpec("weapons", (), (), {}),
    "switch_weapon": ActionSpec("weapons", ("index",), ("index",), {}, int_fields=("index",)),
    # Chat
    "chat_send": ActionSpec("chat", ("text",), ("text",), {}),
    # Settings
    "get_settings": ActionSpec(None, (), (), {}),
    "set_setting": ActionSpec(None, ("key", "value"), ("key", "value"), {}),
    # Session
    "ping": ActionSpec(None, (), (), {}),
    "disconnect": ActionSpec(None, ("reason",), (), {}),
}

# ---------------------------------------------------------------------------
# Event names
# ---------------------------------------------------------------------------

EVENT_CAPTURE_STARTED: str = "capture_started"
EVENT_CAPTURE_STOPPED: str = "capture_stopped"
EVENT_PLAYER_SEEN: str = "player_seen"
EVENT_PLAYER_LOST: str = "player_lost"
EVENT_FRAME: str = "frame"

KNOWN_EVENTS: tuple[str, ...] = (
    EVENT_CAPTURE_STARTED,
    EVENT_CAPTURE_STOPPED,
    EVENT_PLAYER_SEEN,
    EVENT_PLAYER_LOST,
    EVENT_FRAME,
)

# ---------------------------------------------------------------------------
# SDK-level events (mirror bridge events + connection lifecycle)
# ---------------------------------------------------------------------------

SDK_CONNECTED: str = "connected"
SDK_DISCONNECTED: str = "disconnected"
SDK_READY: str = "ready"
SDK_TICK: str = "tick"
SDK_STATE_UPDATE: str = "state_update"
SDK_DAMAGE: str = "damage"
SDK_DEATH: str = "death"
SDK_SPAWN: str = "spawn"
SDK_WEAPON_CHANGED: str = "weapon_changed"

# ---------------------------------------------------------------------------
# Screen / coordinate helpers
# ---------------------------------------------------------------------------

DEFAULT_PORT: int = 8765

SCREEN_REF_WIDTH: int = 1280
SCREEN_REF_HEIGHT: int = 720

#: Pairing code length and character set.
PAIRING_LENGTH: int = 6
PAIRING_ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # unambiguous chars
