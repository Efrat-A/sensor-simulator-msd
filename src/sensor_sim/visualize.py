"""Live time-series view: x(t) against both regions' bars, and the raw
dist_a(t)/dist_b(t) traces with the crossing threshold marked — so the
Schmitt-trigger crossings in ``classifier.py`` are visible as they happen,
not just their result.

This is a pure display layer — it is driven one :class:`~sensor_sim.simulation.Tick`
at a time by the CLI loop and never computes a classification itself.
"""

from __future__ import annotations

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
        self._dist_a: list[float] = []
        self._dist_b: list[float] = []

        plt.ion()
        self.fig, (self.ax_x, self.ax_d) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
        self.fig.suptitle("Sensor simulator - live classification")

        region_a, region_b = config.region_a, config.region_b
        self.ax_x.axhspan(region_a.low, region_a.high, color="tab:blue", alpha=0.15)
        self.ax_x.axhspan(region_b.low, region_b.high, color="tab:orange", alpha=0.15)

        a_bars = {region_a.low, region_a.high}
        b_bars = {region_b.low, region_b.high}
        shared_bars = a_bars & b_bars
        for bar in a_bars - shared_bars:
            self.ax_x.axhline(bar, color="tab:blue", linewidth=0.8, linestyle="--")
        for bar in b_bars - shared_bars:
            self.ax_x.axhline(bar, color="tab:orange", linewidth=0.8, linestyle="--")
        for bar in shared_bars:
            # A's and B's dashed lines would land on the exact same y and hide
            # each other -- draw the shared bar once, distinctly, instead.
            self.ax_x.axhline(bar, color="black", linewidth=1.6, linestyle="-")
            self.ax_x.annotate(
                "A/B shared bar",
                xy=(1.0, bar),
                xycoords=("axes fraction", "data"),
                xytext=(-4, 4),
                textcoords="offset points",
                ha="right",
                fontsize=7,
                color="black",
            )
        self.ax_x.set_ylabel("x")
        self._autoscale_x(config)

        self.ax_d.axhline(
            config.classifier.crossing_threshold,
            color="0.4",
            linestyle=":",
            linewidth=1,
            label="crossing threshold",
        )
        self.ax_d.set_ylabel("distance to nearest bar")
        self.ax_d.set_xlabel("t (s)")

        (self._x_line,) = self.ax_x.plot([], [], "-", color="0.3", linewidth=1)
        (self._x_point,) = self.ax_x.plot([], [], "o", markersize=8)
        (self._dist_a_line,) = self.ax_d.plot(
            [], [], "-", color="tab:blue", linewidth=1, label="dist_a"
        )
        (self._dist_b_line,) = self.ax_d.plot(
            [], [], "-", color="tab:orange", linewidth=1, label="dist_b"
        )
        self.ax_d.legend(loc="upper right", fontsize=8)

        self._text = self.ax_x.text(
            0.02,
            0.98,
            "",
            transform=self.ax_x.transAxes,
            va="top",
            fontsize=10,
            fontfamily="monospace",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
        )

    def _autoscale_x(self, config: AppConfig) -> None:
        bounds = [config.region_a.low, config.region_a.high, config.region_b.low,
                  config.region_b.high, *config.motion.waypoints]
        pad = (max(bounds) - min(bounds)) * 0.1 + 1
        self.ax_x.set_ylim(min(bounds) - pad, max(bounds) + pad)

    def update(self, tick: Tick) -> None:
        self._t.append(tick.t)
        self._x.append(tick.x)
        self._dist_a.append(tick.dist_a)
        self._dist_b.append(tick.dist_b)

        cutoff = tick.t - self._window
        while len(self._t) > 1 and self._t[0] < cutoff:
            del self._t[0]
            del self._x[0]
            del self._dist_a[0]
            del self._dist_b[0]

        self._x_line.set_data(self._t, self._x)
        self._x_point.set_data([tick.t], [tick.x])
        self._x_point.set_color(_STATE_COLORS[tick.state])
        self._dist_a_line.set_data(self._t, self._dist_a)
        self._dist_b_line.set_data(self._t, self._dist_b)
        self._text.set_text(f"t = {tick.t:6.1f}s\nstate = {tick.state.value}")

        self.ax_x.set_xlim(self._t[0], max(self._t[-1], self._t[0] + 1e-6))
        self.ax_d.relim()
        self.ax_d.autoscale_view(scalex=False)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def is_open(self) -> bool:
        return plt.fignum_exists(self.fig.number)

    def close(self) -> None:
        plt.close(self.fig)
