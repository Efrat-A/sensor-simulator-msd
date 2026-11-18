"""The simulated sensor API: ``get_dist_a()`` / ``get_dist_b()``.

Per the assignment, these are no-argument functions — a stand-in for a real
GPS unit's firmware call, which would not take "current position" as a
parameter because the whole point is that the caller doesn't have it. All
state (where the sensor "truly" is, how noisy it is) lives behind a module
level sensor instance that :func:`configure` installs; everything downstream
(the classifier, the simulation loop) only ever calls the two bare functions,
never reaches past them to read true position or region objects directly.

Readings are the *unsigned* distance to the nearer bar of each region, plus
Gaussian measurement noise, clamped at 0 — a real distance sensor cannot
report a negative reading, and the sign is exactly the information this
sensor does not have (see ``classifier.py``).
"""

from __future__ import annotations

import numpy as np

from sensor_sim.config import SensorConfig
from sensor_sim.motion import MotionSimulator
from sensor_sim.regions import Interval


class SensorSimulator:
    """Produces noisy unsigned-distance-to-nearest-bar readings for one moving point."""

    def __init__(
        self,
        motion: MotionSimulator,
        region_a: Interval,
        region_b: Interval,
        config: SensorConfig,
        seed: int | None = None,
    ) -> None:
        self._motion = motion
        self._region_a = region_a
        self._region_b = region_b
        self._noise_std = config.noise_std
        self._rng = np.random.default_rng(seed)

    def _noisy_distance(self, region: Interval) -> float:
        true_distance = region.unsigned_distance(self._motion.position)
        noisy = true_distance + self._rng.normal(0.0, self._noise_std)
        return max(0.0, noisy)

    def read_dist_a(self) -> float:
        return self._noisy_distance(self._region_a)

    def read_dist_b(self) -> float:
        return self._noisy_distance(self._region_b)


_active_sensor: SensorSimulator | None = None


def configure(sensor: SensorSimulator) -> None:
    """Install the sensor instance that ``get_dist_a``/``get_dist_b`` delegate to."""
    global _active_sensor
    _active_sensor = sensor


def _require_sensor() -> SensorSimulator:
    if _active_sensor is None:
        raise RuntimeError("sensor_sim.sensor.configure(...) must be called before use")
    return _active_sensor


def get_dist_a() -> float:
    """Simulated unsigned distance from the sensor to Region A's nearer bar."""
    return _require_sensor().read_dist_a()


def get_dist_b() -> float:
    """Simulated unsigned distance from the sensor to Region B's nearer bar."""
    return _require_sensor().read_dist_b()
