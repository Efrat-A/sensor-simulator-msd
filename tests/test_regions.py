import pytest

from sensor_sim.regions import Interval


class TestInterval:
    def test_rejects_low_not_less_than_high(self):
        with pytest.raises(ValueError):
            Interval(low=5.0, high=5.0)
        with pytest.raises(ValueError):
            Interval(low=5.0, high=1.0)

    def test_half_width(self):
        assert Interval(low=0.0, high=10.0).half_width == pytest.approx(5.0)

    def test_distance_is_zero_on_either_bar(self):
        region = Interval(low=0.0, high=10.0)
        assert region.unsigned_distance(0.0) == pytest.approx(0.0)
        assert region.unsigned_distance(10.0) == pytest.approx(0.0)

    def test_distance_peaks_at_center_while_inside(self):
        region = Interval(low=0.0, high=10.0)
        assert region.unsigned_distance(5.0) == pytest.approx(5.0)

    def test_distance_grows_moving_away_outside(self):
        region = Interval(low=0.0, high=10.0)
        assert region.unsigned_distance(-3.0) == pytest.approx(3.0)
        assert region.unsigned_distance(13.0) == pytest.approx(3.0)

    def test_just_inside_and_just_outside_the_same_bar_report_equal_distance(self):
        """The core ambiguity the classifier has to deal with: unsigned
        distance alone cannot distinguish which side of the bar you're on."""
        region = Interval(low=0.0, high=10.0)
        assert region.unsigned_distance(0.2) == pytest.approx(region.unsigned_distance(-0.2))

    def test_contains_is_ground_truth_only(self):
        region = Interval(low=0.0, high=10.0)
        assert region.contains(5.0) is True
        assert region.contains(-0.1) is False
        assert region.contains(0.0) is True
        assert region.contains(10.0) is True
