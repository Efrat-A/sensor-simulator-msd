"""Realistic 2D motion generator: position ``(x, y)`` over time.

The sensor's "true" position walks towards a looping sequence of waypoints
on the (X, Y) plane, at a speed that oscillates around a configured average
(plus Gaussian jitter) rather than staying constant — the sort of pace a
real GPS track would show, not a clean constant-velocity sweep. Direction
is simply the unit vector towards the next waypoint; nothing here knows
about regions or distances — only ``sensor.py`` is allowed to turn
``(x, y)`` into a distance reading.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from sensor_sim.config import MotionConfig

logger = logging.getLogger(__name__)


class MotionSimulator:
    """Steps a point towards a looping list of 2D waypoints at a varying speed."""

    def __init__(self, config: MotionConfig) -> None:
        self._config = config
        self._rng = np.random.default_rng(config.seed)
        self.x, self.y = config.waypoints[0]
        self._waypoint_index = 1 % len(config.waypoints)
        self.speed = config.avg_speed
        self._speed_phase = 0.0

    @property
    def position(self) -> tuple[float, float]:
        return (self.x, self.y)

    def _current_target(self) -> tuple[float, float]:
        return self._config.waypoints[self._waypoint_index]

    def step(self, dt: float) -> tuple[float, float]:
        """Advance the walker by ``dt`` seconds and return the new position."""
        cfg = self._config

        # Speed: a slow sinusoidal "pace" variation plus sensor-level jitter,
        # clamped so the walker never stalls.
        self._speed_phase += 2 * math.pi * dt / cfg.speed_period
        oscillation = cfg.speed_variability * math.sin(self._speed_phase)
        jitter = self._rng.normal(0.0, cfg.speed_noise_std)
        self.speed = max(cfg.min_speed, cfg.avg_speed * (1 + oscillation) + jitter)

        target_x, target_y = self._current_target()
        dx, dy = target_x - self.x, target_y - self.y
        remaining = math.hypot(dx, dy)
        if remaining > 1e-9:
            ux, uy = dx / remaining, dy / remaining
        else:
            ux, uy = 0.0, 0.0
        self.x += ux * self.speed * dt
        self.y += uy * self.speed * dt

        if math.hypot(target_x - self.x, target_y - self.y) <= cfg.waypoint_tolerance:
            logger.debug(
                "reached waypoint %d at (%.3f, %.3f), advancing to waypoint %d",
                self._waypoint_index,
                target_x,
                target_y,
                (self._waypoint_index + 1) % len(cfg.waypoints),
            )
            self._waypoint_index = (self._waypoint_index + 1) % len(cfg.waypoints)

        return self.position
