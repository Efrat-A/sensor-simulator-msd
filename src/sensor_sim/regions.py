"""Regions: each is an axis-aligned rectangle on the (X, Y) plane, bounded
by a ``low`` corner and a ``high`` corner -- the direct 2D generalization
of "two bars on an axis".

``Rectangle.unsigned_distance(x, y)`` is the one thing the rest of the
system can ask a region for: the distance from ``(x, y)`` to the *nearest*
point on its boundary (its four edges) -- always ``>= 0``, whether that
point is inside or outside. That mirrors the real sensor API this project
simulates: ``get_dist_a()``/``get_dist_b()`` report magnitude only, never
which side of the boundary the reading is on (see ``sensor.py``).
``Rectangle.contains`` is ground truth, kept only for the simulator/plot --
the classifier never calls it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rectangle:
    """A region bounded by an axis-aligned box from ``low`` to ``high``."""

    x_low: float
    y_low: float
    x_high: float
    y_high: float

    def __post_init__(self) -> None:
        if self.x_low >= self.x_high:
            raise ValueError(f"x_low ({self.x_low}) must be less than x_high ({self.x_high})")
        if self.y_low >= self.y_high:
            raise ValueError(f"y_low ({self.y_low}) must be less than y_high ({self.y_high})")

    @property
    def half_width(self) -> float:
        """Half of the *shorter* side -- the farthest from the boundary a
        point inside this rectangle can ever be (reached only at the
        center, along the tighter axis)."""
        return min(self.x_high - self.x_low, self.y_high - self.y_low) / 2

    def unsigned_distance(self, x: float, y: float) -> float:
        """Distance from ``(x, y)`` to the nearest point on the rectangle's
        boundary -- identical whether that point is just inside or just
        outside the same edge; see ``classifier.py`` for why that ambiguity
        is the crux of this problem."""
        if self.contains(x, y):
            return min(x - self.x_low, self.x_high - x, y - self.y_low, self.y_high - y)
        dx = max(self.x_low - x, 0.0, x - self.x_high)
        dy = max(self.y_low - y, 0.0, y - self.y_high)
        return (dx * dx + dy * dy) ** 0.5

    def contains(self, x: float, y: float) -> bool:
        """Ground truth only (simulator/plot use); the classifier has no
        way to compute this from an unsigned distance reading alone."""
        return self.x_low <= x <= self.x_high and self.y_low <= y <= self.y_high
