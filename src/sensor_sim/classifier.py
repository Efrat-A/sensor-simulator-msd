"""Run-time region membership from *unsigned* nearest-edge distances.

``get_dist_a()``/``get_dist_b()`` report distance-to-nearest-edge with no
sign, so a single reading cannot say "inside" or "outside": a point just
inside a region near one of its edges and a point just outside that same
edge report the same small positive number. In fact, from magnitude alone,
"approached an edge and turned back without crossing it" and "crossed the
edge and kept going" produce the *identical* signal shape (distance dips
towards 0, then rises again) — there is no way to tell them apart from
distance readings alone. That is an honest limitation of a magnitude-only
proximity sensor, not a bug to engineer around; the usual real-world answer
(geofencing, limit switches) is the one used here: treat any sufficiently
close approach as a crossing.

What *is* unambiguous is the crossing event itself, so instead of mapping
a reading to a state directly, :class:`RealTimeClassifier` watches each
region's distance stream for that dip and toggles membership on every one
it sees — a Schmitt-trigger edge detector per region:

- "armed" (ready to detect the next crossing) once the distance has risen
  above ``rearm_threshold`` since the last toggle;
- a crossing registers, and membership flips, the moment the distance
  falls below ``crossing_threshold`` while armed;
- it then de-arms, so sensor noise dithering near zero at the same edge
  cannot register as several crossings.

Each region's detector keeps only two booleans (``inside``, ``armed``) —
no raw reading history, no derivative — so this stays causal and online:
every call looks only at the current sample and that small amount of
carried-over state, never at true position and never ahead.

One consequence worth stating plainly: with no sign in the reading, there
is no way to know the *initial* membership from distance alone either.
This classifier assumes the sensor starts outside both regions (true for
the packaged scenarios, which all begin far from both); if it starts
inside a region without ever crossing an edge during observation, it will
never be classified as inside that region.

Region A and Region B are each tracked by their own, fully independent
detector, so this handles disjoint regions, regions that merely touch
(share an edge), and genuinely overlapping regions identically -- the
detectors don't know about each other. The classifier always reports a
single state, though: if both happen to be inside at once (only possible
when A and B overlap), Region A takes priority.
"""

from __future__ import annotations

import logging
from enum import Enum

from sensor_sim.config import ClassifierConfig

logger = logging.getLogger(__name__)


class RegionState(str, Enum):
    OUTSIDE = "OUTSIDE"
    IN_A = "IN_A"
    IN_B = "IN_B"


class _CrossingDetector:
    """Toggles an inside/outside flag on each edge crossing of one region."""

    def __init__(self, name: str, crossing_threshold: float, rearm_threshold: float) -> None:
        self._name = name
        self._crossing_threshold = crossing_threshold
        self._rearm_threshold = rearm_threshold
        self.inside = False
        self._armed = True

    def update(self, distance: float) -> bool:
        if self._armed and distance < self._crossing_threshold:
            self.inside = not self.inside
            self._armed = False
            logger.debug(
                "%s crossed at distance=%.3f -> inside=%s (now de-armed)",
                self._name,
                distance,
                self.inside,
            )
        elif not self._armed and distance > self._rearm_threshold:
            self._armed = True
            logger.debug("%s re-armed at distance=%.3f", self._name, distance)
        return self.inside


class RealTimeClassifier:
    def __init__(self, config: ClassifierConfig) -> None:
        self._detector_a = _CrossingDetector(
            "detector_a", config.crossing_threshold, config.rearm_threshold
        )
        self._detector_b = _CrossingDetector(
            "detector_b", config.crossing_threshold, config.rearm_threshold
        )
        self._state = RegionState.OUTSIDE

    @property
    def state(self) -> RegionState:
        return self._state

    def classify(self, dist_a: float, dist_b: float) -> RegionState:
        """Update and return the region state for one new ``(dist_a, dist_b)`` sample."""
        inside_a = self._detector_a.update(dist_a)
        inside_b = self._detector_b.update(dist_b)

        if inside_a:
            new_state = RegionState.IN_A
        elif inside_b:
            new_state = RegionState.IN_B
        else:
            new_state = RegionState.OUTSIDE

        if new_state != self._state:
            logger.debug(
                "state %s -> %s (dist_a=%.3f, dist_b=%.3f)",
                self._state.value,
                new_state.value,
                dist_a,
                dist_b,
            )
        self._state = new_state
        return self._state
