import matplotlib.patches as patches
import matplotlib.pyplot as plt
import pytest

# from conftest import attach_figure  # unused while the plot call below is commented out
from sensor_sim import sensor
from sensor_sim.config import MotionConfig, SensorConfig
from sensor_sim.motion import MotionSimulator
from sensor_sim.regions import Rectangle
from sensor_sim.sensor import SensorSimulator


@pytest.fixture(autouse=True)
def _reset_global_sensor():
    sensor._active_sensor = None
    yield
    sensor._active_sensor = None


# The attach_figure() call below is commented out: generating and attaching
# a plot on every run is heavy for routine `make check` runs. Uncomment it
# to get that test's picture in the Allure report.
def regions_and_point_figure(region_a: Rectangle, region_b: Rectangle, point: tuple[float, float]):
    """Draw both regions plus the sensor's true position, so a reported
    distance can be checked by eye against the picture."""
    fig, ax = plt.subplots()
    for region, color, label in [(region_a, "tab:blue", "A"), (region_b, "tab:orange", "B")]:
        ax.add_patch(
            patches.Rectangle(
                (region.x_low, region.y_low),
                region.x_high - region.x_low,
                region.y_high - region.y_low,
                fill=False,
                edgecolor=color,
                label=label,
            )
        )
    ax.scatter(*point, color="tab:red", zorder=3, label="true position")
    ax.legend()
    ax.set_aspect("equal")
    margin = 2.0
    xs = [region_a.x_low, region_a.x_high, region_b.x_low, region_b.x_high, point[0]]
    ys = [region_a.y_low, region_a.y_high, region_b.y_low, region_b.y_high, point[1]]
    ax.set_xlim(min(xs) - margin, max(xs) + margin)
    ax.set_ylim(min(ys) - margin, max(ys) + margin)
    return fig


def test_get_dist_a_requires_configure_first():
    with pytest.raises(RuntimeError):
        sensor.get_dist_a()


def test_get_dist_a_and_b_reflect_true_distance_within_noise():
    motion = MotionSimulator(MotionConfig(waypoints=[(0.0, 0.0), (1.0, 0.0)], seed=0))
    region_a = Rectangle(x_low=-3.0, y_low=-3.0, x_high=3.0, y_high=3.0)  # centered on start
    region_b = Rectangle(x_low=100.0, y_low=-3.0, x_high=106.0, y_high=3.0)  # far away
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
    # attach_figure(
    #     regions_and_point_figure(region_a, region_b, motion.position),
    #     "true position vs. both regions",
    # )
    assert dist_a == pytest.approx(3.0, abs=0.2)  # distance to nearer edge from center
    assert dist_b == pytest.approx(100.0, abs=0.2)


def test_repeated_reads_without_stepping_motion_track_the_same_position():
    """get_dist_a()/get_dist_b() are no-argument functions with no notion of
    wall-clock time -- the sensor's true position only moves when something
    explicitly calls motion.step(). So any number of reads back-to-back (or
    with an arbitrarily long real-world gap between them, since nothing
    here is clock-driven) must track the same true position, differing
    only by fresh measurement noise each call -- never drifting simply
    because time passed without a step()."""
    motion = MotionSimulator(MotionConfig(waypoints=[(0.0, 0.0), (1.0, 0.0)], seed=0))
    region_a = Rectangle(x_low=-3.0, y_low=-3.0, x_high=3.0, y_high=3.0)
    region_b = Rectangle(x_low=100.0, y_low=-3.0, x_high=106.0, y_high=3.0)
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
    assert motion.position == (0.0, 0.0)  # never moved -- nothing ever called step()


def test_readings_are_never_negative():
    """Even with noise that would push the true (near-zero) distance
    negative, the reported value must be clamped to >= 0."""
    motion = MotionSimulator(MotionConfig(waypoints=[(0.0, 0.0), (1.0, 0.0)], seed=0))
    region_a = Rectangle(x_low=0.0, y_low=-5.0, x_high=10.0, y_high=5.0)  # starts on an edge
    region_b = Rectangle(x_low=-5.0, y_low=0.0, x_high=5.0, y_high=10.0)  # also starts on an edge
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
        assert sensor.get_dist_b() >= 0.0
