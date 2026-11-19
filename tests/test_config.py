import pytest

from sensor_sim.config import (
    AppConfig,
    ClassifierConfig,
    MotionConfig,
    SensorConfig,
    SimulationConfig,
)


def _base_raw(region_a=None, region_b=None, classifier=None) -> dict:
    return {
        "regions": {
            "A": region_a or {"low": [0.0, 0.0], "high": [10.0, 10.0]},
            "B": region_b or {"low": [20.0, 0.0], "high": [30.0, 10.0]},
        },
        "motion": {
            "waypoints": [[-10.0, 0.0], [40.0, 0.0]],
            "seed": 1,
        },
        "classifier": classifier or {"crossing_threshold": 0.3, "rearm_threshold": 1.0},
    }


def test_default_config_loads():
    config = AppConfig.default()
    assert set(config.regions) >= {"A", "B"}
    assert config.simulation.dt > 0


def test_from_dict_builds_regions():
    config = AppConfig.from_dict(_base_raw())
    assert config.region_a.x_low == 0.0
    assert config.region_a.x_high == 10.0
    assert config.region_b.x_low == 20.0


def test_missing_region_raises():
    raw = _base_raw()
    del raw["regions"]["B"]
    with pytest.raises(ValueError, match="missing required region"):
        AppConfig.from_dict(raw)


def test_overlapping_regions_are_allowed():
    raw = _base_raw(
        region_a={"low": [0.0, 0.0], "high": [10.0, 10.0]},
        region_b={"low": [5.0, 5.0], "high": [15.0, 15.0]},
    )
    config = AppConfig.from_dict(raw)  # must not raise
    assert config.region_a.x_high > config.region_b.x_low


def test_touching_regions_are_not_overlapping():
    raw = _base_raw(
        region_a={"low": [0.0, 0.0], "high": [10.0, 10.0]},
        region_b={"low": [10.0, 0.0], "high": [20.0, 10.0]},
    )
    AppConfig.from_dict(raw)  # must not raise


def test_rearm_threshold_must_be_smaller_than_region_half_width():
    # Region A has half-width 2.0 (the shorter side, 4.0, halved);
    # rearm_threshold of 3.0 would strand the detector "inside" forever,
    # since distance can never exceed 2.0 there.
    raw = _base_raw(
        region_a={"low": [0.0, 0.0], "high": [4.0, 10.0]},
        classifier={"crossing_threshold": 0.3, "rearm_threshold": 3.0},
    )
    with pytest.raises(ValueError, match="half-width"):
        AppConfig.from_dict(raw)


def test_rearm_threshold_exactly_equal_to_half_width_is_also_rejected():
    # The boundary case: distance can approach but never exceed the
    # half-width at the region's exact center, so it must never re-arm.
    raw = _base_raw(
        region_a={"low": [0.0, 0.0], "high": [4.0, 10.0]},
        classifier={"crossing_threshold": 0.3, "rearm_threshold": 2.0},
    )
    with pytest.raises(ValueError, match="half-width"):
        AppConfig.from_dict(raw)


class TestClassifierConfig:
    def test_negative_crossing_threshold_rejected(self):
        with pytest.raises(ValueError):
            ClassifierConfig(crossing_threshold=-0.1, rearm_threshold=1.0)

    def test_rearm_must_exceed_crossing_threshold(self):
        with pytest.raises(ValueError):
            ClassifierConfig(crossing_threshold=0.5, rearm_threshold=0.5)
        with pytest.raises(ValueError):
            ClassifierConfig(crossing_threshold=0.5, rearm_threshold=0.4)

    def test_zero_crossing_threshold_is_allowed(self):
        ClassifierConfig(crossing_threshold=0.0, rearm_threshold=0.5)  # must not raise


class TestMotionConfig:
    def _kwargs(self, **overrides):
        defaults = dict(waypoints=[(0.0, 0.0), (10.0, 0.0)], seed=1)
        defaults.update(overrides)
        return defaults

    def test_zero_speed_period_rejected(self):
        """speed_period divides a step's phase update -- zero would crash
        MotionSimulator.step with a ZeroDivisionError instead of failing at
        config-load time with a clear message."""
        with pytest.raises(ValueError, match="speed_period"):
            MotionConfig(**self._kwargs(speed_period=0.0))

    def test_negative_speed_period_rejected(self):
        with pytest.raises(ValueError, match="speed_period"):
            MotionConfig(**self._kwargs(speed_period=-1.0))

    def test_non_positive_avg_speed_rejected(self):
        with pytest.raises(ValueError, match="avg_speed"):
            MotionConfig(**self._kwargs(avg_speed=0.0))


class TestSensorConfig:
    def test_negative_noise_std_rejected(self):
        with pytest.raises(ValueError, match="noise_std"):
            SensorConfig(noise_std=-0.1)

    def test_zero_noise_std_is_allowed(self):
        SensorConfig(noise_std=0.0)  # must not raise -- a noiseless sensor is valid


class TestSimulationConfig:
    def test_non_positive_dt_rejected(self):
        with pytest.raises(ValueError, match="dt"):
            SimulationConfig(dt=0.0)
        with pytest.raises(ValueError, match="dt"):
            SimulationConfig(dt=-0.1)

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError, match="duration"):
            SimulationConfig(duration=-1.0)

    def test_null_duration_is_allowed(self):
        SimulationConfig(duration=None)  # must not raise -- runs until Ctrl+C

    def test_non_positive_realtime_factor_rejected(self):
        with pytest.raises(ValueError, match="realtime_factor"):
            SimulationConfig(realtime_factor=0.0)
        with pytest.raises(ValueError, match="realtime_factor"):
            SimulationConfig(realtime_factor=-2.0)
