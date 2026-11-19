"""Wires motion -> sensor -> classifier into one tick stream.

:func:`simulate_ticks` is a plain generator with no wall-clock sleeping, so
it is cheap and deterministic to unit test. :func:`pace` is the thin,
separate layer that makes a live demo feel real-time; keeping it apart from
the generator means "run fast for tests" and "run live for the demo" are the
same simulation, just consumed differently.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TypeVar

from sensor_sim import sensor
from sensor_sim.classifier import RealTimeClassifier, RegionState
from sensor_sim.config import AppConfig
from sensor_sim.motion import MotionSimulator
from sensor_sim.sensor import SensorSimulator


@dataclass(frozen=True)
class Tick:
    """One simulation step. ``x``/``y`` are carried only for display — the
    classifier below never sees them, only ``dist_a``/``dist_b``."""

    t: float
    x: float
    y: float
    dist_a: float
    dist_b: float
    state: RegionState


def simulate_ticks(config: AppConfig) -> Iterator[Tick]:
    """Yield an unbounded (or ``config.simulation.duration``-bounded) stream of ticks."""
    motion = MotionSimulator(config.motion)
    active_sensor = SensorSimulator(
        motion=motion,
        region_a=config.region_a,
        region_b=config.region_b,
        config=config.sensor,
        seed=config.motion.seed,
    )
    sensor.configure(active_sensor)
    classifier = RealTimeClassifier(config.classifier)

    dt = config.simulation.dt
    duration = config.simulation.duration
    t = 0.0
    while duration is None or t <= duration:
        x, y = motion.position
        dist_a, dist_b = sensor.get_dist_a(), sensor.get_dist_b()
        state = classifier.classify(dist_a, dist_b)
        yield Tick(t=t, x=x, y=y, dist_a=dist_a, dist_b=dist_b, state=state)
        motion.step(dt)
        t += dt


T = TypeVar("T")


def pace(ticks: Iterator[T], dt: float, realtime_factor: float) -> Iterator[T]:
    """Replay ``ticks`` sleeping just enough to match wall-clock time.

    Uses the gap between a monotonic clock and the expected schedule rather
    than a flat ``sleep(dt)`` per tick, so per-tick display/processing cost
    doesn't accumulate into drift over a long run.
    """
    period = dt / realtime_factor
    start = time.monotonic()
    for i, tick in enumerate(ticks):
        target = start + i * period
        remaining = target - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        yield tick
