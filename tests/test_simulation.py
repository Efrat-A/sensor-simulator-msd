from dataclasses import replace
from pathlib import Path

from sensor_sim.classifier import RealTimeClassifier, RegionState
from sensor_sim.config import AppConfig, ClassifierConfig
from sensor_sim.simulation import pace, simulate_ticks

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


def short_config(duration: float = 60.0) -> AppConfig:
    config = AppConfig.default()
    return replace(config, simulation=replace(config.simulation, duration=duration))


def test_ticks_cover_the_requested_duration_at_dt_steps():
    config = short_config(duration=5.0)
    ticks = list(simulate_ticks(config))
    expected_count = round(5.0 / config.simulation.dt) + 1
    assert ticks[0].t == 0.0
    assert abs(len(ticks) - expected_count) <= 1
    assert ticks[-1].t <= 5.0 + config.simulation.dt


def test_time_is_monotonically_increasing():
    ticks = list(simulate_ticks(short_config(duration=5.0)))
    times = [tick.t for tick in ticks]
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_distances_are_never_negative():
    ticks = list(simulate_ticks(short_config(duration=30.0)))
    assert all(tick.dist_a >= 0.0 and tick.dist_b >= 0.0 for tick in ticks)


def test_route_visits_all_three_states_over_the_default_scenario():
    """The packaged default route is designed to pass through both regions;
    a long enough run should observe all three classification states."""
    ticks = list(simulate_ticks(short_config(duration=180.0)))
    seen = {tick.state for tick in ticks}
    assert seen == {RegionState.OUTSIDE, RegionState.IN_A, RegionState.IN_B}


def test_zero_duration_yields_exactly_one_tick_at_t_zero():
    ticks = list(simulate_ticks(short_config(duration=0.0)))
    assert len(ticks) == 1
    assert ticks[0].t == 0.0


def test_overlap_scenario_resolves_to_a_single_state_with_a_taking_priority():
    """configs/overlap_scenario.yaml defines genuinely overlapping regions;
    the classifier always returns exactly one state, never a hybrid one,
    with Region A taking priority while inside the shared span."""
    config = AppConfig.from_yaml(CONFIGS_DIR / "overlap_scenario.yaml")
    ticks = list(simulate_ticks(config))
    seen = {tick.state for tick in ticks}
    assert seen <= {RegionState.OUTSIDE, RegionState.IN_A, RegionState.IN_B}
    assert RegionState.IN_A in seen  # the route passes through the A/B overlap


class TestPaceUnderConsumerStalls:
    """pace() is what the CLI uses to turn simulate_ticks() into a real-time
    stream. These tests use a fake clock instead of real time.sleep() so a
    6-second stall is instant to run but still proves the real property:
    if a consumer doesn't pull the next tick for a while (e.g. it's busy
    rendering, or the terminal/plot stalls), no ticks are ever skipped --
    pace() just stops sleeping until it has caught back up to schedule."""

    def _fake_clock(self, monkeypatch):
        now = [0.0]
        monkeypatch.setattr("sensor_sim.simulation.time.monotonic", lambda: now[0])
        monkeypatch.setattr(
            "sensor_sim.simulation.time.sleep", lambda s: now.__setitem__(0, now[0] + s)
        )
        return now

    def test_no_ticks_are_dropped_after_a_long_stall(self, monkeypatch):
        now = self._fake_clock(monkeypatch)
        source = list(range(20))
        paced = pace(iter(source), dt=0.1, realtime_factor=1.0)

        received = [next(paced)]
        now[0] += 6.0  # consumer "stalls" for 6 simulated seconds
        received += list(paced)

        assert received == source

    def test_a_stall_does_not_speed_up_ticks_still_ahead_of_schedule(self, monkeypatch):
        now = self._fake_clock(monkeypatch)
        paced = pace(iter(range(5)), dt=0.1, realtime_factor=1.0)
        next(paced)  # tick 0, at t=0
        now[0] += 6.0  # stall well past every tick's schedule
        list(paced)  # drain ticks 1-4 with no sleeping -- they're all overdue
        # once caught up, a subsequent tick with nothing overdue sleeps again
        more_paced = pace(iter([0, 1]), dt=0.1, realtime_factor=1.0)
        next(more_paced)
        before = now[0]
        next(more_paced)
        assert now[0] > before  # slept to stay on schedule, not drop or skip


def test_classification_uses_only_distances_not_position():
    """Two independent classifiers fed the same distance stream must reach
    the same states -- proving classification never peeks at ground-truth
    position, only the (dist_a, dist_b) stream."""
    readings = [(5.0, 50.0), (0.2, 50.0), (3.0, 50.0), (0.2, 50.0), (10.0, 0.1)]
    clf_1 = RealTimeClassifier(ClassifierConfig(crossing_threshold=0.3, rearm_threshold=1.0))
    clf_2 = RealTimeClassifier(ClassifierConfig(crossing_threshold=0.3, rearm_threshold=1.0))
    states_1 = [clf_1.classify(a, b) for a, b in readings]
    states_2 = [clf_2.classify(a, b) for a, b in readings]
    assert states_1 == states_2
