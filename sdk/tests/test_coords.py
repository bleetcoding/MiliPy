"""Tests for milipy.coords — coordinate transformations.

Covers: landscape and portrait orientations, multiple resolutions,
different aspect ratios, viewport offsets (letterboxing), capture
downscaling, rotation steps, round-trip consistency, and clamping.
"""
import pytest

from milipy.coords import (
    CalibrationSource,
    Orientation,
    SpaceConfig,
    ViewportRect,
)
from milipy.state import Position


def test_landscape_center():
    cfg = SpaceConfig(screen_width=1280, screen_height=720)
    assert cfg.screen_to_normalized(640, 360) == Position(nx=0.5, ny=0.5)
    assert cfg.normalized_to_screen(Position(nx=0.5, ny=0.5)) == (640.0, 360.0)


def test_normalized_corners():
    cfg = SpaceConfig(screen_width=800, screen_height=600)
    tl = cfg.normalized_to_screen(Position(nx=0.0, ny=0.0))
    br = cfg.normalized_to_screen(Position(nx=1.0, ny=1.0))
    assert tl == (0.0, 0.0)
    assert br == (800.0, 600.0)


def test_out_of_range_clamps():
    cfg = SpaceConfig(screen_width=100, screen_height=100)
    # Pixels outside the screen clamp to the nearest edge
    pos = cfg.screen_to_normalized(-50, 500)
    assert pos == Position(nx=0.0, ny=1.0)
    # Values outside [0, 1] in normalized space are clamped to the screen
    # bounds by normalized_to_screen (Position itself rejects them).
    assert cfg.normalized_to_screen(Position(nx=1.0, ny=0.0)) == (100.0, 0.0)
    assert cfg.screen_to_normalized(250, -10) == Position(nx=1.0, ny=0.0)


def test_round_trip_normalized_screen():
    cfg = SpaceConfig(screen_width=1920, screen_height=1080)
    for nx, ny in ((0.0, 0.0), (1.0, 1.0), (0.23, 0.87), (0.5, 0.5)):
        x, y = cfg.normalized_to_screen(Position(nx=nx, ny=ny))
        back = cfg.screen_to_normalized(x, y)
        assert back.nx == pytest.approx(nx, rel=1e-9)
        assert back.ny == pytest.approx(ny, rel=1e-9)


def test_portrait_orientation():
    cfg = SpaceConfig(screen_width=720, screen_height=1280,
                      orientation=Orientation.PORTRAIT)
    mid = cfg.screen_to_normalized(360, 640)
    assert mid == Position(nx=0.5, ny=0.5)
    # Bottom center should map to ny near 1
    bottom = cfg.screen_to_normalized(360, 1200)
    assert bottom.ny == pytest.approx(1200 / 1280)


def test_wide_aspect_ratio():
    cfg = SpaceConfig(screen_width=2560, screen_height=1440)
    pos = cfg.screen_to_normalized(256, 72)
    assert pos == Position(nx=0.1, ny=0.05)


def test_viewport_offset_letterbox():
    """Game fills only the central region of the screen."""
    cfg = SpaceConfig(
        screen_width=1080,
        screen_height=1920,
        orientation=Orientation.PORTRAIT,
        viewport=ViewportRect(x=140.0, y=100.0, width=800.0, height=1600.0,
                              source=CalibrationSource.CONFIGURED),
    )
    # Top-left of the viewport itself must normalize to (0, 0)
    assert cfg.screen_to_normalized(140.0, 100.0) == Position(nx=0.0, ny=0.0)
    # Bottom-right of viewport must normalize to (1, 1)
    assert cfg.screen_to_normalized(940.0, 1700.0) == Position(nx=1.0, ny=1.0)
    # A point outside the viewport clamps rather than extrapolating
    assert cfg.screen_to_normalized(50.0, 50.0) == Position(nx=0.0, ny=0.0)


def test_viewport_rejects_zero_size():
    with pytest.raises(ValueError):
        ViewportRect(x=0.0, y=0.0, width=0.0, height=100.0)


def test_capture_downscale():
    cfg = SpaceConfig(screen_width=1280, screen_height=720, capture_scale=0.5)
    assert cfg.screen_to_capture(640.0, 360.0) == (320.0, 180.0)
    assert cfg.capture_to_screen(320.0, 180.0) == (640.0, 360.0)


def test_capture_to_normalized_composition():
    cfg = SpaceConfig(screen_width=800, screen_height=600, capture_scale=0.25)
    pos = cfg.capture_to_normalized(100.0, 75.0)
    # 100/0.25=400 -> 0.5 ; 75/0.25=300 -> 0.5
    assert pos == Position(nx=0.5, ny=0.5)


def test_capture_scale_bounds():
    with pytest.raises(ValueError):
        SpaceConfig(screen_width=100, screen_height=100, capture_scale=0.0)
    with pytest.raises(ValueError):
        SpaceConfig(screen_width=100, screen_height=100, capture_scale=1.5)


def test_input_identity_without_rotation():
    cfg = SpaceConfig(screen_width=1280, screen_height=720)
    assert cfg.screen_to_input(100.0, 200.0) == (100.0, 200.0)
    assert cfg.input_to_screen(100.0, 200.0) == (100.0, 200.0)


def test_input_90_degree_rotation_round_trip():
    """Rotating 90° clockwise, then converting back, must be lossless."""
    cfg = SpaceConfig(screen_width=720, screen_height=1280, rotation_deg=90)
    x, y = cfg.screen_to_input(123.0, 456.0)
    back = cfg.input_to_screen(x, y)
    assert back == pytest.approx((123.0, 456.0))


def test_input_90_degree_rotation_mapping():
    """A 90° clockwise rotation maps (x, y) to (y, w-1-x)."""
    cfg = SpaceConfig(screen_width=720, screen_height=1280, rotation_deg=90)
    assert cfg.screen_to_input(0.0, 0.0) == (0.0, 719.0)


def test_input_180_degree_rotation():
    cfg = SpaceConfig(screen_width=800, screen_height=600, rotation_deg=180)
    x, y = cfg.screen_to_input(10.0, 20.0)
    assert x == pytest.approx(800 - 1 - 10)
    assert y == pytest.approx(600 - 1 - 20)


def test_game_to_screen_alias():
    cfg = SpaceConfig(screen_width=640, screen_height=480)
    assert cfg.game_to_screen(Position(nx=0.25, ny=0.75)) == (160.0, 360.0)


def test_normalized_to_capture_composition():
    cfg = SpaceConfig(screen_width=1000, screen_height=500, capture_scale=0.2)
    pt = cfg.normalized_to_capture(Position(nx=0.5, ny=0.4))
    assert pt == pytest.approx((100.0, 40.0))


def test_input_to_normalized_composition():
    cfg = SpaceConfig(screen_width=200, screen_height=100)
    pos = cfg.input_to_normalized(50.0, 25.0)
    assert pos == Position(nx=0.25, ny=0.25)


def test_screen_dimensions_must_be_positive():
    with pytest.raises(ValueError):
        SpaceConfig(screen_width=0, screen_height=100)
