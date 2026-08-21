"""High-level action helpers shared by the Bot and the simulator.

This module keeps the action catalogue in one place: every public action
method validates its inputs and builds a protocol-compliant action payload
using :mod:`milipy.protocol`. Nothing here performs I/O — the transport layer
is injected by the caller, which is also what makes the simulator testable.
"""

from __future__ import annotations

from typing import Any

from .protocol import action_message, CapabilityError
from .protocol_schema import (
    CAPTURE_MAX_FPS,
    CAPTURE_MAX_JPEG_QUALITY,
    CAPTURE_MIN_JPEG_QUALITY,
    VALID_DIRECTIONS,
)
from .state import Player


class ActionBuilder:
    """Pure, transport-agnostic builder for all protocol actions.

    Each method returns ``(action_name, payload_dict)``. The ``check`` flag
    toggles capability pre-validation so the simulator can skip it while the
    real client enforces it against the negotiated capabilities.
    """

    def __init__(self, capabilities: dict[str, bool]) -> None:
        self.capabilities = capabilities

    # -- movement -----------------------------------------------------------

    def move(self, direction: str) -> tuple[str, dict[str, Any]]:
        """Sustain movement in one of the four cardinal directions."""
        if direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {VALID_DIRECTIONS}, got {direction!r}"
            )
        return ("move", {"direction": direction})

    def stop(self) -> tuple[str, dict[str, Any]]:
        """Release all sustained movement and aim inputs."""
        return ("stop", {})

    def set_control(self, **controls: bool) -> tuple[str, dict[str, Any]]:
        """Low-level sustained-press control state.

        Accepted keys: ``left``, ``right``, ``up``, ``down``, ``jump``,
        ``jetpack``. Only provided keys are changed; omitted keys keep their
        previous state on the bridge.
        """
        allowed = {"left", "right", "up", "down", "jump", "jetpack"}
        invalid = set(controls) - allowed
        if invalid:
            raise ValueError(f"unknown control keys: {sorted(invalid)}")
        for value in controls.values():
            if not isinstance(value, bool):
                raise ValueError("control values must be booleans")
        return ("set_control", dict(controls))

    def jump(self) -> tuple[str, dict[str, Any]]:
        return ("jump", {})

    def crouch(self) -> tuple[str, dict[str, Any]]:
        return ("crouch", {})

    # -- capture ------------------------------------------------------------

    def set_capture(
        self,
        enabled: bool,
        frame_rate: int | None = None,
        include_frame: bool | None = None,
        jpeg_quality: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Configure the capture pipeline.

        ``frame_rate`` and ``jpeg_quality`` are clamped to the bridge's
        published bounds; values above ``CAPTURE_MAX_FPS`` are rejected
        rather than silently downgraded so the caller's intent is never
        silently altered.
        """
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        payload: dict[str, Any] = {"enabled": enabled}
        if frame_rate is not None:
            if not isinstance(frame_rate, int) or not (0 <= frame_rate <= CAPTURE_MAX_FPS):
                raise ValueError(
                    f"frame_rate must be an integer in [0, {CAPTURE_MAX_FPS}], "
                    f"got {frame_rate!r}"
                )
            payload["frame_rate"] = frame_rate
        if include_frame is not None:
            if not isinstance(include_frame, bool):
                raise ValueError("include_frame must be a boolean")
            payload["include_frame"] = include_frame
        if jpeg_quality is not None:
            if not isinstance(jpeg_quality, int) or not (
                CAPTURE_MIN_JPEG_QUALITY <= jpeg_quality <= CAPTURE_MAX_JPEG_QUALITY
            ):
                raise ValueError(
                    f"jpeg_quality must be an integer in "
                    f"[{CAPTURE_MIN_JPEG_QUALITY}, {CAPTURE_MAX_JPEG_QUALITY}], "
                    f"got {jpeg_quality!r}"
                )
            payload["jpeg_quality"] = jpeg_quality
        return ("set_capture", payload)

    def request_state(self) -> tuple[str, dict[str, Any]]:
        return ("request_state", {})

    # -- aim ----------------------------------------------------------------

    def aim(self, nx: float, ny: float) -> tuple[str, dict[str, Any]]:
        """Sustain aim at a normalized screen point (top-left origin)."""
        for name, value in (("nx", nx), ("ny", ny)):
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise ValueError(f"aim {name} must be a number in [0.0, 1.0], got {value!r}")
        return ("aim", {"nx": float(nx), "ny": float(ny)})

    def aim_at(self, player: Player) -> tuple[str, dict[str, Any]]:
        """Sustain aim at a tracked player.

        Requires the player to have an observable position; otherwise aiming
        at them would be fabrication, which the SDK refuses to do.
        """
        if player.position is None:
            raise ValueError(
                f"cannot aim at player {player.id!r}: position not observed"
            )
        return self.aim(player.position.nx, player.position.ny)

    # -- combat -------------------------------------------------------------

    def fire(self) -> tuple[str, dict[str, Any]]:
        return ("fire", {})

    def stop_fire(self) -> tuple[str, dict[str, Any]]:
        return ("stop_fire", {})

    def punch(self) -> tuple[str, dict[str, Any]]:
        return ("punch", {})

    def throw_grenade(self) -> tuple[str, dict[str, Any]]:
        return ("throw_grenade", {})

    # -- weapons ------------------------------------------------------------

    def pickup(self) -> tuple[str, dict[str, Any]]:
        return ("pickup", {})

    def switch_weapon(self, index: int) -> tuple[str, dict[str, Any]]:
        if not isinstance(index, int):
            raise ValueError("weapon index must be an integer")
        return ("switch_weapon", {"index": index})

    # -- chat ---------------------------------------------------------------

    def chat_send(self, text: str) -> tuple[str, dict[str, Any]]:
        if not isinstance(text, str) or not text:
            raise ValueError("chat text must be a non-empty string")
        return ("chat_send", {"text": text})

    # -- settings -----------------------------------------------------------

    def get_settings(self) -> tuple[str, dict[str, Any]]:
        return ("get_settings", {})

    def set_setting(self, key: str, value: Any) -> tuple[str, dict[str, Any]]:
        if not isinstance(key, str) or not key:
            raise ValueError("setting key must be a non-empty string")
        return ("set_setting", {"key": key, "value": value})

    # -- session ------------------------------------------------------------

    def ping(self) -> tuple[str, dict[str, Any]]:
        return ("ping", {})

    def disconnect(self, reason: str | None = None) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {}
        if isinstance(reason, str):
            payload["reason"] = reason
        return ("disconnect", payload)

    # -- bridge lifetime (v0.3.0) -------------------------------------------

    def stop_bridge(self) -> tuple[str, dict[str, Any]]:
        """Explicit remote shutdown: stops the bridge foreground service.

        The WebSocket listener dies with the service and the Android UI /
        notification reflect the new state. Authorization is the pairing
        token — no capability gate.
        """
        return ("stop_bridge", {})
