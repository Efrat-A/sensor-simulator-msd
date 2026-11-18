"""Realistic 1D motion generator: position ``x`` over time.

The sensor's "true" position walks towards a looping sequence of waypoints
on a single axis, at a speed that oscillates around a configured average
(plus Gaussian jitter) rather than staying constant — the sort of pace a
real GPS track would show, not a clean constant-velocity sweep. Direction
is simply the sign of (next waypoint - current position); nothing here
knows about regions or distances — only ``sensor.py`` is allowed to turn
``x`` into a distance reading.
"""

from __future__ import annotations

import math

import numpy as np

from sensor_sim.config import MotionConfig


class MotionSimulator:
    """Steps a point towards a looping list of waypoints at a varying speed."""

    def __init__(self, config: MotionConfig) -> None:
        self._config = config
        self._rng = np.random.default_rng(config.seed)
        self.x = float(config.waypoints[0])
        self._waypoint_index = 1 % len(config.waypoints)
        self.speed = config.avg_speed
        self._speed_phase = 0.0

    @property
    def position(self) -> float:
        return self.x

    def _current_target(self) -> float:
        return self._config.waypoints[self._waypoint_index]

    def step(self, dt: float) -> float:
        """Advance the walker by ``dt`` seconds and return the new position."""
        cfg = self._config

        # Speed: a slow sinusoidal "pace" variation plus sensor-level jitter,
        # clamped so the walker never stalls.
        self._speed_phase += 2 * math.pi * dt / cfg.speed_period
        oscillation = cfg.speed_variability * math.sin(self._speed_phase)
        jitter = self._rng.normal(0.0, cfg.speed_noise_std)
        self.speed = max(cfg.min_speed, cfg.avg_speed * (1 + oscillation) + jitter)

        target = self._current_target()
        direction = 1.0 if target >= self.x else -1.0
        self.x += direction * self.speed * dt

        if abs(target - self.x) <= cfg.waypoint_tolerance:
            self._waypoint_index = (self._waypoint_index + 1) % len(cfg.waypoints)

        return self.x
