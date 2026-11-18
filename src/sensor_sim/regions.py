"""Regions: each is an interval on the X axis bounded by two bars.

``Interval.unsigned_distance(x)`` is the one thing the rest of the system
can ask a region for: the distance from ``x`` to the *nearer* of its two
bars (``low``/``high``) — always ``>= 0``, on either side. That mirrors the
real sensor API this project simulates: ``get_dist_a()``/``get_dist_b()``
report magnitude only, never which side of the bar the reading is on (see
``sensor.py``). ``Interval.contains`` is ground truth, kept only for the
simulator/plot — the classifier never calls it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    """A region bounded by two bars at ``low`` and ``high`` on the X axis."""

    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low >= self.high:
            raise ValueError(f"low ({self.low}) must be less than high ({self.high})")

    @property
    def half_width(self) -> float:
        return (self.high - self.low) / 2

    def unsigned_distance(self, x: float) -> float:
        """Distance from ``x`` to the nearer bar — identical whether ``x``
        is just inside or just outside that same bar; see ``classifier.py``
        for why that ambiguity is the crux of this problem."""
        return min(abs(x - self.low), abs(x - self.high))

    def contains(self, x: float) -> bool:
        """Ground truth only (simulator/plot use); the classifier has no
        way to compute this from an unsigned distance reading alone."""
        return self.low <= x <= self.high
