import pytest

from sensor_sim import sensor
from sensor_sim.config import MotionConfig, SensorConfig
from sensor_sim.motion import MotionSimulator
from sensor_sim.regions import Interval
from sensor_sim.sensor import SensorSimulator


@pytest.fixture(autouse=True)
def _reset_global_sensor():
    sensor._active_sensor = None
    yield
    sensor._active_sensor = None


def test_get_dist_a_requires_configure_first():
    with pytest.raises(RuntimeError):
        sensor.get_dist_a()


def test_get_dist_a_and_b_reflect_true_distance_within_noise():
    motion = MotionSimulator(MotionConfig(waypoints=[0.0, 1.0], seed=0))
    region_a = Interval(low=-3.0, high=3.0)  # motion starts at x=0, center of A
    region_b = Interval(low=100.0, high=106.0)  # far away
    sim = SensorSimulator(
        motion=motion,
        region_a=region_a,
        region_b=region_b,
        config=SensorConfig(noise_std=0.01),
        seed=0,
    )
    sensor.configure(sim)

    dist_a = sensor.get_dist_a()
    dist_b = sensor.get_dist_b()
    assert dist_a == pytest.approx(3.0, abs=0.2)  # distance to nearer bar from center
    assert dist_b == pytest.approx(100.0, abs=0.2)


def test_repeated_reads_without_stepping_motion_track_the_same_position():
    """get_dist_a()/get_dist_b() are no-argument functions with no notion of
    wall-clock time -- the sensor's true position only moves when something
    explicitly calls motion.step(). So any number of reads back-to-back (or
    with an arbitrarily long real-world gap between them, since nothing
    here is clock-driven) must track the same true position, differing
    only by fresh measurement noise each call -- never drifting simply
    because time passed without a step()."""
    motion = MotionSimulator(MotionConfig(waypoints=[0.0, 1.0], seed=0))
    region_a = Interval(low=-3.0, high=3.0)
    region_b = Interval(low=100.0, high=106.0)
    sim = SensorSimulator(
        motion=motion,
        region_a=region_a,
        region_b=region_b,
        config=SensorConfig(noise_std=0.05),
        seed=0,
    )
    sensor.configure(sim)

    readings = [sensor.get_dist_a() for _ in range(50)]
    assert all(r == pytest.approx(3.0, abs=0.3) for r in readings)
    assert motion.position == 0.0  # never moved -- nothing ever called step()


def test_readings_are_never_negative():
    """Even with noise that would push the true (near-zero) distance
    negative, the reported value must be clamped to >= 0."""
    motion = MotionSimulator(MotionConfig(waypoints=[0.0, 1.0], seed=0))
    region_a = Interval(low=0.0, high=10.0)  # motion starts exactly on a bar
    region_b = Interval(low=100.0, high=106.0)
    sim = SensorSimulator(
        motion=motion,
        region_a=region_a,
        region_b=region_b,
        config=SensorConfig(noise_std=5.0),  # large noise, true distance is 0
        seed=0,
    )
    sensor.configure(sim)

    for _ in range(1000):
        assert sensor.get_dist_a() >= 0.0
