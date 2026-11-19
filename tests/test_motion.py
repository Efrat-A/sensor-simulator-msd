import math

import pytest

from sensor_sim.config import MotionConfig
from sensor_sim.motion import MotionSimulator


def make_motion(**overrides) -> MotionSimulator:
    defaults = dict(
        waypoints=[(0.0, 0.0), (10.0, 0.0)],
        avg_speed=2.0,
        speed_variability=0.5,
        speed_noise_std=0.1,
        speed_period=5.0,
        min_speed=0.2,
        waypoint_tolerance=0.5,
        seed=1,
    )
    defaults.update(overrides)
    return MotionSimulator(MotionConfig(**defaults))


def test_starts_at_first_waypoint():
    motion = make_motion()
    assert motion.position == (0.0, 0.0)


def test_step_moves_the_point():
    motion = make_motion()
    before = motion.position
    motion.step(0.1)
    after = motion.position
    assert before != after


def test_moves_towards_the_next_waypoint_first():
    motion = make_motion(waypoints=[(0.0, 0.0), (10.0, 0.0)])
    motion.step(0.1)
    x, y = motion.position
    assert x > 0.0  # heading towards (10, 0), not away
    assert y == pytest.approx(0.0)


def test_moves_diagonally_towards_a_2d_waypoint():
    motion = make_motion(waypoints=[(0.0, 0.0), (10.0, 10.0)])
    motion.step(0.1)
    x, y = motion.position
    assert x > 0.0
    assert y > 0.0
    assert x == pytest.approx(y)  # straight line towards (10, 10)


def test_speed_never_drops_below_configured_minimum():
    motion = make_motion(min_speed=0.3, speed_noise_std=0.5)
    for _ in range(500):
        motion.step(0.1)
        assert motion.speed >= 0.3 - 1e-9


def test_walker_reaches_and_cycles_through_waypoints():
    motion = make_motion(waypoints=[(0.0, 0.0), (5.0, 5.0), (-5.0, 0.0)])
    visited_near_second = False
    for _ in range(2000):
        motion.step(0.05)
        x, y = motion.position
        if math.hypot(x - 5.0, y - 5.0) < 0.5:
            visited_near_second = True
    assert visited_near_second


def test_same_seed_is_deterministic():
    motion_a = make_motion(seed=123)
    motion_b = make_motion(seed=123)
    for _ in range(50):
        motion_a.step(0.1)
        motion_b.step(0.1)
    assert motion_a.position == motion_b.position


def test_at_least_two_waypoints_required():
    with pytest.raises(ValueError):
        MotionConfig(waypoints=[(0.0, 0.0)])


def test_zero_dt_step_is_a_no_op():
    """A caller that steps with dt=0 (e.g. a paused clock) must not move the
    walker or raise -- only elapsed simulated time should ever move it."""
    motion = make_motion()
    before = motion.position
    motion.step(0.0)
    assert motion.position == before


def test_large_dt_overshoots_a_waypoint_without_raising():
    """A dt far bigger than usual (e.g. after a stalled caller catches up in
    one big step) can jump straight past a waypoint; that must not crash,
    and the walker should simply continue towards the next one."""
    motion = make_motion(waypoints=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)], waypoint_tolerance=0.1)
    motion.step(1000.0)
    assert motion.position != (0.0, 0.0)


def test_exactly_on_a_waypoint_does_not_crash():
    """Once the walker lands exactly on its target, the direction vector's
    length is zero -- must not raise a divide-by-zero."""
    motion = make_motion(waypoints=[(0.0, 0.0), (0.0, 0.0)], waypoint_tolerance=0.01)
    motion.step(0.1)  # must not raise
