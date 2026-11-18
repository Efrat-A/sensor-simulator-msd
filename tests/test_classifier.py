from sensor_sim.classifier import RealTimeClassifier, RegionState
from sensor_sim.config import ClassifierConfig


def make_classifier(crossing_threshold: float = 0.3, rearm_threshold: float = 1.0):
    return RealTimeClassifier(ClassifierConfig(crossing_threshold, rearm_threshold))


class TestStartsOutside:
    def test_initial_state(self):
        clf = make_classifier()
        assert clf.state is RegionState.OUTSIDE


class TestFullCrossingCycle:
    """A full approach-enter-dwell-rearm-exit sequence on Region A, with
    Region B held far away (dist_b large) throughout."""

    def test_entering_region_a(self):
        clf = make_classifier()
        assert clf.classify(dist_a=5.0, dist_b=50.0) is RegionState.OUTSIDE  # approaching
        assert clf.classify(dist_a=0.5, dist_b=50.0) is RegionState.OUTSIDE  # still outside band
        assert clf.classify(dist_a=0.2, dist_b=50.0) is RegionState.IN_A  # crossed

    def test_stays_in_a_while_disarmed_even_if_reading_dithers_near_zero(self):
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # trigger entry
        for dist_a in (0.1, 0.05, 0.25, 0.0, 0.29):
            assert clf.classify(dist_a=dist_a, dist_b=50.0) is RegionState.IN_A

    def test_rearming_deep_inside_does_not_itself_change_state(self):
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # trigger entry
        assert clf.classify(dist_a=3.0, dist_b=50.0) is RegionState.IN_A  # rearms, stays IN_A

    def test_exiting_region_a_after_rearming(self):
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # enter
        clf.classify(dist_a=3.0, dist_b=50.0)  # rearm
        clf.classify(dist_a=0.5, dist_b=50.0)  # approaching exit bar, not yet
        assert clf.classify(dist_a=0.2, dist_b=50.0) is RegionState.OUTSIDE  # exit crossing

    def test_exit_crossing_is_ignored_before_rearming(self):
        """Without crossing the rearm threshold first, a second dip below
        crossing_threshold must NOT be treated as an exit -- it's the same
        physical crossing still being read noisily."""
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # enter
        for dist_a in (0.1, 0.4, 0.15, 0.3):  # all below rearm_threshold (1.0)
            assert clf.classify(dist_a=dist_a, dist_b=50.0) is RegionState.IN_A


class TestTransitionsBetweenRegions:
    def test_a_to_outside_to_b(self):
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # enter A
        clf.classify(dist_a=3.0, dist_b=50.0)  # rearm A
        clf.classify(dist_a=0.2, dist_b=50.0)  # exit A -> OUTSIDE
        assert clf.classify(dist_a=10.0, dist_b=5.0) is RegionState.OUTSIDE
        assert clf.classify(dist_a=10.0, dist_b=0.1) is RegionState.IN_B


class TestOverlappingRegions:
    """The classifier has no notion of region geometry -- each detector is
    independent -- so when both happen to be inside at once (only possible
    when A and B overlap), classify() must still return a single state.
    Region A takes priority over Region B."""

    def test_inside_both_regions_at_once_reports_a(self):
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # enter A
        assert clf.classify(dist_a=3.0, dist_b=0.2) is RegionState.IN_A  # also enter B, A wins

    def test_leaving_a_while_still_inside_b_falls_back_to_b(self):
        clf = make_classifier()
        clf.classify(dist_a=0.2, dist_b=50.0)  # enter A
        assert clf.classify(dist_a=3.0, dist_b=0.2) is RegionState.IN_A  # rearm A, enter B, A wins
        assert clf.classify(dist_a=0.2, dist_b=3.0) is RegionState.IN_B  # exit A, rearm B


class TestKnownLimitation:
    """Documents, rather than hides, the inherent ambiguity: with unsigned
    distance alone, a close approach that turns back without truly crossing
    is indistinguishable from an actual crossing (see classifier.py's
    module docstring). This is expected behavior given the sensor model,
    not something a smarter classifier could fix without more information.
    """

    def test_a_close_approach_toggles_state_even_without_a_true_crossing(self):
        clf = make_classifier(crossing_threshold=0.3)
        clf.classify(dist_a=5.0, dist_b=50.0)
        state = clf.classify(dist_a=0.1, dist_b=50.0)  # "got close", by design = a crossing
        assert state is RegionState.IN_A


class TestClassifyIsCausal:
    def test_same_call_sequence_is_order_dependent_only_on_past(self):
        """classify() must be a pure function of (internal state, current
        reading) -- replaying the same sequence twice gives the same
        sequence of states, with no hidden lookahead."""
        readings = [
            (5.0, 50.0),
            (0.2, 50.0),
            (3.0, 50.0),
            (0.2, 50.0),
            (10.0, 0.1),
            (10.0, 3.0),
        ]

        def run():
            clf = make_classifier()
            return [clf.classify(a, b) for a, b in readings]

        assert run() == run()
