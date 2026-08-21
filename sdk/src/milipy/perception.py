"""Perception architecture interfaces for MiliPy.

This module defines the *real* abstractions the future perception pipeline is
built on. It deliberately contains **no Mini Militia game knowledge and no
machine learning** — those belong one layer deeper, in concrete adapters.

The pipeline the interfaces describe::

    Android Bridge
          ↓  JPEG frame (bytes)
    FrameSource            — supplies raw captured frames
          ↓
    Observation Pipeline
          ↓  raw detections
    PerceptionProvider     — converts frames into observations
          ↓
    Mini Militia Adapter   — game-specific interpretation
          ↓
    GameStateProvider      — publishes a GameState the Bot consumes

Concrete implementations are optional today: :class:`BaselinePerceptionProvider`
is a real, deliberately boring implementation that passes frames through
unchanged and emits no detections. That is the honest starting point — a
perception provider that never pretends to see players it has not detected.

Field provenance rule: every :class:`milipy.state.Player` field must either
come from a concrete detector or remain ``None``. An unknown value is never
invented. See ``docs/device-validation.md`` for the validation-level
discipline every detector must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from .state import GameState, Player


@dataclass(frozen=True)
class Frame:
    """A raw captured screen frame with its metadata.

    ``data`` is intentionally opaque bytes — perception providers decode it
    however they need (JPEG, PNG, raw pixels). ``timestamp_ms`` is the bridge's
    capture timestamp and is the reference clock for all derived observations.
    """

    data: bytes
    timestamp_ms: int
    width: int
    height: int
    jpeg_quality: int | None = None

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("frame dimensions must be positive")
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")


class FrameSource(ABC):
    """Supplies captured frames to the observation pipeline.

    The :mod:`milipy.sim` module already implements this contract with
    :class:`SimFrameSource`; a real adapter will read frames off the
    WebSocket and forward them here. Implementations decide buffering,
    throttling, and latest-frame semantics — see ``docs/architecture.md``.
    """

    @abstractmethod
    def latest(self) -> Frame | None:
        """The most recent captured frame, or ``None`` if nothing arrived."""

    @abstractmethod
    def frames_since(self, timestamp_ms: int) -> Iterable[Frame]:
        """Frames captured at or after ``timestamp_ms``."""


class Detection:
    """A raw observation of *something* on screen.

    Detections carry a category string and normalized coordinates — they are
    deliberately not typed as :class:`Player` because a detector may observe
    other entities (pickups, projectiles, UI) that future adapters could use.
    Confidence and provenance are required so downstream code can decide
    what to trust.
    """

    __slots__ = ("category", "nx", "ny", "confidence", "source", "frame_timestamp_ms")

    def __init__(
        self,
        category: str,
        nx: float,
        ny: float,
        confidence: float = 1.0,
        source: str = "unknown",
        frame_timestamp_ms: int = 0,
    ) -> None:
        if not isinstance(category, str) or not category:
            raise ValueError("detection category must be a non-empty string")
        if not (0.0 <= nx <= 1.0) or not (0.0 <= ny <= 1.0):
            raise ValueError(f"detection position must be normalized: ({nx}, {ny})")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be in [0.0, 1.0]")
        self.category = category
        self.nx = nx
        self.ny = ny
        self.confidence = confidence
        self.source = source
        self.frame_timestamp_ms = frame_timestamp_ms


class PlayerDetector(ABC):
    """Turns frames (and optionally past detections) into player detections.

    Implementations range from color-histogram baselines to full ML models.
    The contract only cares about the outputs. ``detect`` may return zero
    detections — *not seeing anything* is a valid, honest result.
    """

    @abstractmethod
    def detect(self, frame: Frame, previous: Iterable[Detection] = ()) -> list[Detection]:
        """Detect player-like entities in ``frame``."""


class PlayerTracker(ABC):
    """Associates detections across frames into stable player identities.

    Trackers assign each detected player a persistent ``id`` (arbitrary
    strings; the simulator uses ``"sim-0"``, ``"sim-1"``) and may estimate
    velocity from frame-to-frame motion. A tracker that loses a player
    must let it fall out of :meth:`tracked` rather than keeping a stale one.
    """

    @abstractmethod
    def update(self, detections: Iterable[Detection], frame: Frame) -> None:
        """Incorporate new detections from ``frame``."""

    @abstractmethod
    def tracked(self) -> list[str]:
        """Currently tracked player ids, most-recently-seen first."""

    @abstractmethod
    def player_state(self, player_id: str) -> Player:
        """Latest observation of a tracked player.

        Every unknown field must be ``None`` — the returned :class:`Player`
        must never contain fabricated values.
        """


class PerceptionProvider(ABC):
    """The entry point of the observation pipeline.

    A provider consumes frames, runs a detector and a tracker, and publishes
    observations. The default implementation is
    :class:`BaselinePerceptionProvider`, which emits no detections at all:
    that is the correct behavior until a real detector exists.
    """

    @abstractmethod
    def observe(self, frame: Frame) -> None:
        """Process one captured frame."""

    @abstractmethod
    def detections(self) -> list[Detection]:
        """All active detections."""


class GameStateProvider(ABC):
    """Publishes the world state the Bot consumes.

    A :class:`GameStateProvider` combines perception output with anything the
    bridge itself observes (the self-player position, the game session flag)
    and updates a :class:`GameState` on each tick. This keeps the Bot's state
    object single-sourced.
    """

    @abstractmethod
    def tick(self) -> GameState:
        """The latest world state, refreshed since the previous call."""


class BaselineDetector(PlayerDetector):
    """Detector that sees nothing.

    The honest baseline: without a validated Mini Militia perception model,
    claiming detections would be fabrication. Subclass or replace this once
    a real detector has been built and validated (see
    ``docs/device-validation.md``).
    """

    def detect(self, frame: Frame, previous: Iterable[Detection] = ()) -> list[Detection]:
        return []


class BaselineTracker(PlayerTracker):
    """Tracker that holds no players."""

    def update(self, detections: Iterable[Detection], frame: Frame) -> None:
        return None

    def tracked(self) -> list[str]:
        return []

    def player_state(self, player_id: str) -> Player:
        return Player(id=player_id)


class BaselinePerceptionProvider(PerceptionProvider):
    """Perception provider with the honest empty baseline."""

    def __init__(self) -> None:
        self._detector = BaselineDetector()
        self._tracker = BaselineTracker()
        self._detections: list[Detection] = []

    @property
    def detector(self) -> PlayerDetector:
        return self._detector

    @property
    def tracker(self) -> PlayerTracker:
        return self._tracker

    def observe(self, frame: Frame) -> None:
        detections = self._detector.detect(frame, self._detections)
        self._tracker.update(detections, frame)
        self._detections = detections

    def detections(self) -> list[Detection]:
        return list(self._detections)
