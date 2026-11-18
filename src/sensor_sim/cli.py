"""Command-line entry point: ``sensor-sim``."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from sensor_sim.classifier import RegionState
from sensor_sim.config import AppConfig
from sensor_sim.simulation import Tick, pace, simulate_ticks

_STATE_LABEL = {
    RegionState.OUTSIDE: "OUTSIDE",
    RegionState.IN_A: "IN A   ",
    RegionState.IN_B: "IN B   ",
}


def _print_tick(tick: Tick) -> None:
    print(
        f"\rt={tick.t:7.1f}s  x={tick.x:+7.2f}  "
        f"dist_a={tick.dist_a:6.2f}  dist_b={tick.dist_b:6.2f}  -> {_STATE_LABEL[tick.state]}",
        end="",
        flush=True,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sensor-sim",
        description=(
            "Real-time In A / In B / Outside classification demo, driven only by "
            "simulated boundary-distance readings (get_dist_a / get_dist_b)."
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to a YAML config file (default: the packaged default configuration).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Override simulation.duration in seconds (omit to run until Ctrl+C).",
    )
    parser.add_argument(
        "--realtime-factor",
        type=float,
        default=None,
        help="Override simulation.realtime_factor, e.g. 2 runs twice as fast as real time.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Text-only mode: print live state to the terminal instead of opening a plot window.",
    )
    return parser


def _load_config(args: argparse.Namespace) -> AppConfig:
    config = AppConfig.from_yaml(args.config) if args.config else AppConfig.default()
    if args.duration is None and args.realtime_factor is None:
        return config
    sim = config.simulation
    return replace(
        config,
        simulation=replace(
            sim,
            duration=sim.duration if args.duration is None else args.duration,
            realtime_factor=(
                sim.realtime_factor if args.realtime_factor is None else args.realtime_factor
            ),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = _load_config(args)
    ticks = pace(simulate_ticks(config), config.simulation.dt, config.simulation.realtime_factor)

    view = None
    if not args.no_plot:
        from sensor_sim.visualize import LiveView

        view = LiveView(config)

    try:
        for tick in ticks:
            if view is not None and not view.is_open():
                break
            _print_tick(tick)
            if view is not None:
                view.update(tick)
    except KeyboardInterrupt:
        pass
    finally:
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
