"""Live view: the sensor's true (x, y) path against both regions' boxes,
and the raw dist_a(t)/dist_b(t) traces with the crossing threshold marked —
so the Schmitt-trigger crossings in ``classifier.py`` are visible as they
happen, not just their result.

This is a pure display layer — it is driven one :class:`~sensor_sim.simulation.Tick`
at a time by the CLI loop and never computes a classification itself.
"""

from __future__ import annotations

import matplotlib.patches as patches
import matplotlib.pyplot as plt

from sensor_sim.classifier import RegionState
from sensor_sim.config import AppConfig
from sensor_sim.simulation import Tick

_STATE_COLORS = {
    RegionState.OUTSIDE: "tab:gray",
    RegionState.IN_A: "tab:blue",
    RegionState.IN_B: "tab:orange",
}


class LiveView:
    def __init__(self, config: AppConfig, window_seconds: float = 40.0) -> None:
        self._window = window_seconds
        self._t: list[float] = []
        self._x: list[float] = []
        self._y: list[float] = []
        self._dist_a: list[float] = []
        self._dist_b: list[float] = []

        plt.ion()
        self.fig, (self.ax_xy, self.ax_d) = plt.subplots(2, 1, figsize=(7, 9))
        self.fig.suptitle("Sensor simulator - live classification")

        region_a, region_b = config.region_a, config.region_b
        for region, color, label in ((region_a, "tab:blue", "A"), (region_b, "tab:orange", "B")):
            self.ax_xy.add_patch(
                patches.Rectangle(
                    (region.x_low, region.y_low),
                    region.x_high - region.x_low,
                    region.y_high - region.y_low,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.2,
                    linewidth=1.5,
                    label=f"Region {label}",
                )
            )
        self.ax_xy.set_xlabel("x")
        self.ax_xy.set_ylabel("y")
        self.ax_xy.set_aspect("equal", adjustable="box")
        self.ax_xy.legend(loc="upper right", fontsize=8)
        self._autoscale_xy(config)

        self.ax_d.axhline(
            config.classifier.crossing_threshold,
            color="0.4",
            linestyle=":",
            linewidth=1,
            label="crossing threshold",
        )
        self.ax_d.set_ylabel("distance to nearest edge")
        self.ax_d.set_xlabel("t (s)")

        (self._xy_line,) = self.ax_xy.plot([], [], "-", color="0.3", linewidth=1)
        (self._xy_point,) = self.ax_xy.plot([], [], "o", markersize=8)
        (self._dist_a_line,) = self.ax_d.plot(
            [], [], "-", color="tab:blue", linewidth=1, label="dist_a"
        )
        (self._dist_b_line,) = self.ax_d.plot(
            [], [], "-", color="tab:orange", linewidth=1, label="dist_b"
        )
        self.ax_d.legend(loc="upper right", fontsize=8)

        self._text = self.ax_xy.text(
            0.02,
            0.98,
            "",
            transform=self.ax_xy.transAxes,
            va="top",
            fontsize=10,
            fontfamily="monospace",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
        )

    def _autoscale_xy(self, config: AppConfig) -> None:
        regions = (config.region_a, config.region_b)
        xs = [r.x_low for r in regions] + [r.x_high for r in regions]
        ys = [r.y_low for r in regions] + [r.y_high for r in regions]
        xs += [wx for wx, _ in config.motion.waypoints]
        ys += [wy for _, wy in config.motion.waypoints]
        pad = (max(max(xs) - min(xs), max(ys) - min(ys))) * 0.1 + 1
        self.ax_xy.set_xlim(min(xs) - pad, max(xs) + pad)
        self.ax_xy.set_ylim(min(ys) - pad, max(ys) + pad)

    def update(self, tick: Tick) -> None:
        self._t.append(tick.t)
        self._x.append(tick.x)
        self._y.append(tick.y)
        self._dist_a.append(tick.dist_a)
        self._dist_b.append(tick.dist_b)

        cutoff = tick.t - self._window
        while len(self._t) > 1 and self._t[0] < cutoff:
            del self._t[0]
            del self._x[0]
            del self._y[0]
            del self._dist_a[0]
            del self._dist_b[0]

        self._xy_line.set_data(self._x, self._y)
        self._xy_point.set_data([tick.x], [tick.y])
        self._xy_point.set_color(_STATE_COLORS[tick.state])
        self._dist_a_line.set_data(self._t, self._dist_a)
        self._dist_b_line.set_data(self._t, self._dist_b)
        self._text.set_text(f"t = {tick.t:6.1f}s\nstate = {tick.state.value}")

        self.ax_d.set_xlim(self._t[0], max(self._t[-1], self._t[0] + 1e-6))
        self.ax_d.relim()
        self.ax_d.autoscale_view(scalex=False)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def is_open(self) -> bool:
        return plt.fignum_exists(self.fig.number)

    def close(self) -> None:
        plt.close(self.fig)
