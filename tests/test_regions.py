import pytest

from sensor_sim.regions import Rectangle


def make_rect(x_low=0.0, y_low=0.0, x_high=10.0, y_high=10.0) -> Rectangle:
    return Rectangle(x_low=x_low, y_low=y_low, x_high=x_high, y_high=y_high)


class TestRectangle:
    def test_rejects_x_low_not_less_than_x_high(self):
        with pytest.raises(ValueError):
            Rectangle(x_low=5.0, y_low=0.0, x_high=5.0, y_high=10.0)
        with pytest.raises(ValueError):
            Rectangle(x_low=5.0, y_low=0.0, x_high=1.0, y_high=10.0)

    def test_rejects_y_low_not_less_than_y_high(self):
        with pytest.raises(ValueError):
            Rectangle(x_low=0.0, y_low=5.0, x_high=10.0, y_high=5.0)
        with pytest.raises(ValueError):
            Rectangle(x_low=0.0, y_low=5.0, x_high=10.0, y_high=1.0)

    def test_half_width_is_half_the_shorter_side(self):
        assert make_rect(x_high=10.0, y_high=4.0).half_width == pytest.approx(2.0)
        assert make_rect(x_high=4.0, y_high=10.0).half_width == pytest.approx(2.0)

    def test_distance_is_zero_on_every_edge(self):
        region = make_rect()
        assert region.unsigned_distance(0.0, 5.0) == pytest.approx(0.0)  # left edge
        assert region.unsigned_distance(10.0, 5.0) == pytest.approx(0.0)  # right edge
        assert region.unsigned_distance(5.0, 0.0) == pytest.approx(0.0)  # bottom edge
        assert region.unsigned_distance(5.0, 10.0) == pytest.approx(0.0)  # top edge
        assert region.unsigned_distance(0.0, 0.0) == pytest.approx(0.0)  # corner

    def test_distance_peaks_at_center_while_inside(self):
        region = make_rect(x_high=10.0, y_high=10.0)
        assert region.unsigned_distance(5.0, 5.0) == pytest.approx(5.0)

    def test_distance_inside_is_distance_to_nearest_edge_not_corner(self):
        """A point near one edge but far from the others must report the
        distance to that nearest edge only."""
        region = make_rect()
        assert region.unsigned_distance(1.0, 5.0) == pytest.approx(1.0)

    def test_distance_grows_moving_away_outside_along_the_x_axis(self):
        region = make_rect()
        assert region.unsigned_distance(-3.0, 5.0) == pytest.approx(3.0)
        assert region.unsigned_distance(13.0, 5.0) == pytest.approx(3.0)

    def test_distance_grows_moving_away_outside_along_the_y_axis(self):
        """Same check as the x-axis case, but off the top/bottom edges --
        the two axes use independent clamping in unsigned_distance, so
        this isn't implied by the x-axis test alone."""
        region = make_rect()
        assert region.unsigned_distance(5.0, -3.0) == pytest.approx(3.0)
        assert region.unsigned_distance(5.0, 13.0) == pytest.approx(3.0)

    def test_distance_outside_a_corner_is_euclidean(self):
        """Diagonally outside a corner, the nearest boundary point is the
        corner itself -- straight-line (Euclidean) distance, not axis-aligned."""
        region = make_rect(x_high=10.0, y_high=10.0)
        assert region.unsigned_distance(13.0, 14.0) == pytest.approx((3.0**2 + 4.0**2) ** 0.5)

    def test_just_inside_and_just_outside_the_same_edge_report_equal_distance(self):
        """The core ambiguity the classifier has to deal with: unsigned
        distance alone cannot distinguish which side of the edge you're on."""
        region = make_rect()
        assert region.unsigned_distance(0.2, 5.0) == pytest.approx(
            region.unsigned_distance(-0.2, 5.0)
        )

    def test_contains_is_ground_truth_only(self):
        region = make_rect()
        assert region.contains(5.0, 5.0) is True
        assert region.contains(-0.1, 5.0) is False
        assert region.contains(5.0, -0.1) is False
        assert region.contains(0.0, 0.0) is True
        assert region.contains(10.0, 10.0) is True
