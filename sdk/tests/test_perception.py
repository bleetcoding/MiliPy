"""Tests for the perception architecture interfaces.

The contract under test: frames flow FrameSource -> PerceptionProvider
-> GameStateProvider; detections carry provenance; the honest baseline
sees nothing; unknown player fields stay None.
"""
import pytest

from milipy.perception import (
    BaselineDetector,
    BaselinePerceptionProvider,
    BaselineTracker,
    Detection,
    Frame,
    GameStateProvider,
)
from milipy.state import GameSession, GameState, Player, Position


def make_frame(width=1280, height=720, timestamp_ms=1000) -> Frame:
    return Frame(data=b"\xff\xd8\xff\xe0" + b"0" * 100, timestamp_ms=timestamp_ms,
                 width=width, height=height)


def test_frame_rejects_bad_dimensions():
    with pytest.raises(ValueError):
        Frame(data=b"x", timestamp_ms=0, width=0, height=720)
    with pytest.raises(ValueError):
        Frame(data=b"x", timestamp_ms=-1, width=10, height=10)


def test_baseline_provider_sees_nothing():
    """The honest baseline must never fabricate detections."""
    provider = BaselinePerceptionProvider()
    provider.observe(make_frame())
    provider.observe(make_frame(timestamp_ms=2000))
    assert provider.detections() == []


def test_baseline_detector_returns_empty():
    assert BaselineDetector().detect(make_frame()) == []


def test_baseline_tracker_tracks_no_one():
    tracker = BaselineTracker()
    tracker.update([], make_frame())
    assert tracker.tracked() == []


def test_detection_validation():
    with pytest.raises(ValueError):
        Detection(category="", nx=0.5, ny=0.5)
    with pytest.raises(ValueError):
        Detection(category="player", nx=1.5, ny=0.5)
    with pytest.raises(ValueError):
        Detection(category="player", nx=0.5, ny=0.5, confidence=2.0)


def test_detection_carries_provenance():
    det = Detection(category="player", nx=0.3, ny=0.4, confidence=0.9,
                    source="color-histogram", frame_timestamp_ms=5000)
    assert det.source == "color-histogram"
    assert det.frame_timestamp_ms == 5000
    assert det.confidence == 0.9


def test_custom_detector_wires_into_provider():
    """A (stub) detector + tracker can be composed into the provider."""

    class SpyDetector(BaselineDetector):
        def detect(self, frame, previous=()):
            return [Detection("player", 0.25, 0.25, source="spy")]

    class SpyTracker(BaselineTracker):
        def update(self, detections, frame):
            self._detections = list(detections)

        def tracked(self):
            return ["p1"]

        def player_state(self, player_id):
            det = next((d for d in self._detections if d.category == "player"), None)
            if det is None:
                return Player(id=player_id)
            return Player(id=player_id, position=Position(det.nx, det.ny))

    provider = BaselinePerceptionProvider()
    provider._detector = SpyDetector()
    provider._tracker = SpyTracker()
    provider.observe(make_frame())
    assert len(provider.detections()) == 1
    assert provider.tracker.player_state("p1").position == Position(0.25, 0.25)


def test_tracked_player_unknown_fields_stay_none():
    """Player fields without observed provenance must never be invented."""
    tracker = BaselineTracker()
    player = tracker.player_state("ghost")
    assert player.id == "ghost"
    assert player.position is None
    assert player.health is None
    assert player.alive is None


def test_game_state_provider_contract():
    """A minimal provider implementation must produce honest states."""

    class MinimalProvider(GameStateProvider):
        def __init__(self):
            self._tick = 0

        def tick(self):
            self._tick += 1
            return GameState(tick=self._tick, game_session=GameSession.UNKNOWN)

    provider = MinimalProvider()
    state = provider.tick()
    assert state.tick == 1
    # UNKNOWN is the honest default: connection does not imply IN_GAME
    assert state.game_session == GameSession.UNKNOWN
    assert state.player is None
