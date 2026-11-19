"""Configuration model.

Everything a user might want to change — region box corners, how the
sensor moves, how noisy it is, how twitchy the classifier is — lives here as
data, loaded from a YAML file (see ``src/sensor_sim/data/default.yaml`` and
``configs/*.yaml``). Nothing in the simulation, sensor, or classifier code
hard-codes a region corner or a speed: they only ever see an :class:`AppConfig`
built by this module, so reconfiguring the demo never means editing Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

from sensor_sim.regions import Rectangle

#: Region names the rest of the system is built around. Exactly these two.
REGION_A = "A"
REGION_B = "B"


@dataclass(frozen=True)
class MotionConfig:
    """Parameters of the waypoint-seeking, variable-speed 2D motion model."""

    waypoints: list[tuple[float, float]]
    avg_speed: float = 2.0
    speed_variability: float = 0.5
    speed_noise_std: float = 0.15
    speed_period: float = 15.0
    min_speed: float = 0.2
    waypoint_tolerance: float = 0.5
    seed: int | None = 42

    def __post_init__(self) -> None:
        if len(self.waypoints) < 2:
            raise ValueError("motion.waypoints needs at least 2 points to move between")
        if self.avg_speed <= 0:
            raise ValueError("motion.avg_speed must be positive")
        if self.speed_period <= 0:
            raise ValueError("motion.speed_period must be positive (it divides a step's phase)")


@dataclass(frozen=True)
class SensorConfig:
    """Measurement noise added on top of the true geometric distance."""

    noise_std: float = 0.15

    def __post_init__(self) -> None:
        if self.noise_std < 0:
            raise ValueError("sensor.noise_std must be >= 0")


@dataclass(frozen=True)
class ClassifierConfig:
    """Schmitt-trigger thresholds for the crossing-detecting classifier.

    ``crossing_threshold`` is how close (in distance units) a reading must
    get to an edge to register as a crossing. ``rearm_threshold`` is how far
    the reading must then recede before the *next* crossing can register —
    it exists so sensor noise dithering near one edge can't be counted as
    several crossings. It must be strictly larger than ``crossing_threshold``,
    and (checked in :class:`AppConfig`) smaller than either region's
    half-width, or the detector could never re-arm after entering a narrow
    region and would miss that region's exit crossing entirely.
    """

    crossing_threshold: float = 0.3
    rearm_threshold: float = 1.0

    def __post_init__(self) -> None:
        if self.crossing_threshold < 0:
            raise ValueError("classifier.crossing_threshold must be >= 0")
        if self.rearm_threshold <= self.crossing_threshold:
            raise ValueError(
                "classifier.rearm_threshold must be strictly greater than "
                "crossing_threshold, or the detector can never re-arm"
            )


@dataclass(frozen=True)
class SimulationConfig:
    dt: float = 0.1
    duration: float | None = 120.0
    realtime_factor: float = 6.0

    def __post_init__(self) -> None:
        if self.dt <= 0:
            raise ValueError("simulation.dt must be positive, or simulate_ticks never advances")
        if self.duration is not None and self.duration < 0:
            raise ValueError("simulation.duration must be >= 0, or null to run unbounded")
        if self.realtime_factor <= 0:
            raise ValueError("simulation.realtime_factor must be positive")


@dataclass(frozen=True)
class AppConfig:
    regions: dict[str, Rectangle]
    motion: MotionConfig
    sensor: SensorConfig = field(default_factory=SensorConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    def __post_init__(self) -> None:
        missing = {REGION_A, REGION_B} - self.regions.keys()
        if missing:
            raise ValueError(f"config.regions is missing required region(s): {sorted(missing)}")
        for name, region in self.regions.items():
            if self.classifier.rearm_threshold >= region.half_width:
                raise ValueError(
                    f"classifier.rearm_threshold ({self.classifier.rearm_threshold}) must be "
                    f"less than region {name}'s half-width ({region.half_width}); otherwise "
                    f"the crossing detector can never re-arm once inside it and will miss "
                    f"its exit crossing."
                )

    @property
    def region_a(self) -> Rectangle:
        return self.regions[REGION_A]

    @property
    def region_b(self) -> Rectangle:
        return self.regions[REGION_B]

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return cls.from_dict(raw)

    @classmethod
    def default(cls) -> AppConfig:
        """Load the package's built-in default configuration."""
        data = resources.files("sensor_sim.data").joinpath("default.yaml").read_text()
        return cls.from_dict(yaml.safe_load(data))

    @classmethod
    def from_dict(cls, raw: dict) -> AppConfig:
        regions = {
            name: Rectangle(
                x_low=spec["low"][0],
                y_low=spec["low"][1],
                x_high=spec["high"][0],
                y_high=spec["high"][1],
            )
            for name, spec in raw["regions"].items()
        }
        motion_raw = dict(raw["motion"])
        motion_raw["waypoints"] = [(float(p[0]), float(p[1])) for p in motion_raw["waypoints"]]
        return cls(
            regions=regions,
            motion=MotionConfig(**motion_raw),
            sensor=SensorConfig(**raw.get("sensor", {})),
            classifier=ClassifierConfig(**raw.get("classifier", {})),
            simulation=SimulationConfig(**raw.get("simulation", {})),
        )
