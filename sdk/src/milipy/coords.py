"""Coordinate spaces and transformations for MiliPy.

MiliPy works across several distinct coordinate spaces that must never be
mixed accidentally:

- **Screen space**      — absolute pixels on the device screen, origin
                          top-left, y grows downward.
- **Capture space**     — pixels of the screen-capture image. May differ
                          from screen space when capture resolution is
                          downscaled (the bridge's ``jpeg_width``).
- **Game viewport space** — the region of the screen Mini Militia actually
                          renders into. In landscape play the game fills the
                          screen; portrait play or system overlays can leave
                          letterbox offsets. Unknown by default.
- **Normalized space**  — the protocol's device-independent ``Position``
                          coordinates, both axes in ``[0.0, 1.0]``, origin
                          top-left, y grows downward.
- **Input space**       — touch coordinates the accessibility layer receives.
                          On current Android versions input dispatches use
                          the display's current orientation, so input space
                          equals screen space after the accessibility
                          service adjusts for rotation.

Every transformation is expressed through :class:`SpaceConfig`, a single
configurable object. Mini Militia-specific viewport offsets are deliberately
**configurable rather than invented**: the defaults represent "game fills
the whole screen", which is the documented behavior for landscape gameplay,
and per-device calibration can override them.

Example::

    from milipy.coords import SpaceConfig, Orientation

    cfg = SpaceConfig(screen_width=1280, screen_height=720,
                      orientation=Orientation.LANDSCAPE)

    pos = cfg.screen_to_normalized(x=640, y=360)   # Position(0.5, 0.5)
    pt  = cfg.normalized_to_screen(pos)            # (640, 360)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .state import Position


class Orientation(Enum):
    """Screen orientation for coordinate math."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class CalibrationSource(Enum):
    """Provenance of a calibration value."""

    DEFAULT = "default"          # Built-in assumption (game fills screen)
    CONFIGURED = "configured"    # Set by the user/operator
    MEASURED = "measured"        # Derived from a capture/observation


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class ViewportRect:
    """The game viewport inside screen space, in pixels.

    ``(0, 0, w, h)`` means the game fills the whole screen, which is the
    default assumption. Non-zero offsets model letterboxing or notch
    cutouts. Provenance is tracked so nothing silently becomes fake data.
    """

    x: float
    y: float
    width: float
    height: float
    source: CalibrationSource = CalibrationSource.DEFAULT

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("viewport width and height must be positive")


@dataclass
class SpaceConfig:
    """All parameters needed to move between MiliPy coordinate spaces.

    Capture-space downscaling is modeled with ``capture_scale``: if the
    bridge delivers JPEGs at half the screen width, set it to ``0.5`` and
    :meth:`capture_to_screen` / :meth:`screen_to_capture` convert between
    the two.
    """

    screen_width: int
    screen_height: int
    orientation: Orientation = Orientation.LANDSCAPE
    viewport: ViewportRect | None = None
    capture_scale: float = 1.0
    rotation_deg: int = 0

    def __post_init__(self) -> None:
        if self.screen_width <= 0 or self.screen_height <= 0:
            raise ValueError("screen dimensions must be positive")
        if not (0.0 < self.capture_scale <= 1.0):
            raise ValueError("capture_scale must be in (0.0, 1.0]")
        if self.viewport is None:
            self.viewport = ViewportRect(
                x=0.0, y=0.0,
                width=float(self.screen_width),
                height=float(self.screen_height),
            )

    # ------------------------------------------------------------------
    # Normalized <-> screen (through the viewport)
    # ------------------------------------------------------------------

    def screen_to_normalized(self, x: float, y: float) -> Position:
        """Screen pixels to protocol normalized coordinates."""
        vp = self.viewport
        nx = _clamp((x - vp.x) / vp.width, 0.0, 1.0)
        ny = _clamp((y - vp.y) / vp.height, 0.0, 1.0)
        return Position(nx=nx, ny=ny)

    def normalized_to_screen(self, pos: Position) -> tuple[float, float]:
        """Protocol normalized coordinates to screen pixels."""
        vp = self.viewport
        x = _clamp(pos.nx, 0.0, 1.0) * vp.width + vp.x
        y = _clamp(pos.ny, 0.0, 1.0) * vp.height + vp.y
        return x, y

    # ------------------------------------------------------------------
    # Screen <-> capture
    # ------------------------------------------------------------------

    def screen_to_capture(self, x: float, y: float) -> tuple[float, float]:
        """Screen pixels to captured-image pixels."""
        return x * self.capture_scale, y * self.capture_scale

    def capture_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Captured-image pixels to screen pixels."""
        if self.capture_scale <= 0:
            raise ValueError("capture_scale must be positive")
        return x / self.capture_scale, y / self.capture_scale

    # ------------------------------------------------------------------
    # Screen <-> input
    # ------------------------------------------------------------------

    def screen_to_input(self, x: float, y: float) -> tuple[float, float]:
        """Screen pixels to accessibility touch dispatch coordinates.

        Input dispatch uses the current screen orientation, so with no
        rotation this is the identity. When a rotation offset is known
        (e.g., the device is locked to a different rotation than the
        capture), apply the 90-degree step transformation around the
        screen center.
        """
        steps = ((self.rotation_deg % 360) // 90) % 4
        w, h = float(self.screen_width), float(self.screen_height)
        for _ in range(steps):
            x, y = y, w - 1 - x
            w, h = h, w
        return x, y

    def input_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Inverse of :meth:`screen_to_input` (counter-clockwise steps)."""
        steps = ((self.rotation_deg % 360) // 90) % 4
        w, h = float(self.screen_width), float(self.screen_height)
        # Counter-clockwise: (x, y) -> (h - 1 - y, x)
        for _ in range(steps):
            x, y = w - 1 - y, x
            w, h = h, w
        return x, y

    # ------------------------------------------------------------------
    # Game viewport <-> screen
    # ------------------------------------------------------------------

    def game_to_screen(self, pos: Position) -> tuple[float, float]:
        """Alias kept explicit for the documented ``game_to_screen``
        transformation: the game renders in viewport space, which *is*
        normalized screen space within the viewport rectangle."""
        return self.normalized_to_screen(pos)

    # ------------------------------------------------------------------
    # Convenience compositions
    # ------------------------------------------------------------------

    def capture_to_normalized(self, x: float, y: float) -> Position:
        """Captured-image pixels to protocol normalized coordinates."""
        sx, sy = self.capture_to_screen(x, y)
        return self.screen_to_normalized(sx, sy)

    def normalized_to_capture(self, pos: Position) -> tuple[float, float]:
        """Protocol normalized coordinates to captured-image pixels."""
        sx, sy = self.normalized_to_screen(pos)
        return self.screen_to_capture(sx, sy)

    def input_to_normalized(self, x: float, y: float) -> Position:
        sx, sy = self.input_to_screen(x, y)
        return self.screen_to_normalized(sx, sy)
