# sensor-sim

Real-time **In A / In B / Outside** classification of a simulated GPS
sensor moving across a 2D plane over time, using nothing but two
no-argument distance readings — `get_dist_a()` and `get_dist_b()` — the
way a real GPS unit's firmware would expose unsigned nearest-boundary
distances with no access to "true" position.

```
t=   42.3s  x= +28.14  y=  +3.90  dist_a= 28.14  dist_b=  4.86  -> IN B
```

![live demo: the sensor's (x, y) path through both regions' boxes (top), and the raw dist_a/dist_b traces dipping to the crossing threshold at each crossing (bottom)](docs/demo.gif)

## The problem

A sensor moves continuously across the (X, Y) plane over time, through a
space containing two **disjoint** regions, A and B — separated by a clear
gap, never touching or overlapping, as in the packaged default scenario.
Each region is an axis-aligned box bounded by a **low corner** and a
**high corner**. At any instant you can ask two things:

- `get_dist_a()` — distance from the sensor to the nearest edge of Region A's box
- `get_dist_b()` — distance from the sensor to the nearest edge of Region B's box

Both are **unsigned** — always `>= 0`, whichever side of the edge the
sensor is on. That is the whole difficulty: a point just inside a region
near one edge and a point just outside that same edge report the *same*
number. Distance magnitude alone cannot say "inside" or "outside" (see
**Design decisions** below for how this is actually resolved).

The task: classify the sensor's region (`IN_A`, `IN_B`, or `OUTSIDE`) in
real time, as each reading arrives — no buffering a trajectory and
analyzing it afterwards.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the live demo (opens a matplotlib window with the sensor's (x, y)
path against both regions' boxes, and the raw distance traces below it;
also prints each tick to the terminal):

```bash
sensor-sim
```

Terminal-only, no plot window (handy over SSH / in CI):

```bash
sensor-sim --no-plot
```

Run a different scenario, faster:

```bash
sensor-sim --config configs/alt_scenario.yaml --realtime-factor 20
```

Log state transitions (region crossings, waypoints reached) to stderr while running:

```bash
sensor-sim --no-plot -v
```

Run the test suite:

```bash
pytest
```

Or, via the [Makefile](Makefile): `make install` sets up `.venv` and
installs everything above, `make test` / `make lint` / `make typecheck` /
`make check` (all three) run the checks, `make run` / `make run-noplot`
run the demo, and `make clean` removes the venv and caches.

## How it works

```
MotionSimulator  -->  SensorSimulator  -->  RealTimeClassifier  -->  Tick stream
  (true (x,y)(t))   get_dist_a()/get_dist_b()    IN_A/IN_B/OUTSIDE        |
                   (noisy unsigned distance)                              v
                                                                  CLI text + LiveView plot
```

| Module | Responsibility |
|---|---|
| [`regions.py`](src/sensor_sim/regions.py) | `Rectangle`: an axis-aligned box region, with `unsigned_distance(x, y)` |
| [`config.py`](src/sensor_sim/config.py) | Loads region corners, motion, sensor noise, and classifier thresholds from YAML into typed, validated dataclasses |
| [`motion.py`](src/sensor_sim/motion.py) | `MotionSimulator`: the sensor's *true* position `(x, y)` over time, following a looping 2D route at a non-constant, noisy speed |
| [`sensor.py`](src/sensor_sim/sensor.py) | The `get_dist_a()` / `get_dist_b()` API itself — true unsigned distance plus Gaussian measurement noise, clamped `>= 0` |
| [`classifier.py`](src/sensor_sim/classifier.py) | `RealTimeClassifier`: a Schmitt-trigger crossing detector per region, causal and online |
| [`simulation.py`](src/sensor_sim/simulation.py) | Wires the above into a `Tick` stream (`simulate_ticks`), plus `pace()` for real-time playback |
| [`visualize.py`](src/sensor_sim/visualize.py) | Live matplotlib view: the (x, y) path plus region boxes, and a distance-vs-time panel |
| [`cli.py`](src/sensor_sim/cli.py) | `sensor-sim` entry point |

### Design decisions

**Crossing detection, not a level check — because the reading has no sign.**
With a *signed* distance, `dist_a < 0` would mean "inside" directly. Here
`get_dist_a()`/`get_dist_b()` only ever report magnitude, so a single
reading is ambiguous: distance `0.2` could be just inside a region's edge,
or just outside it — the number is identical either way. What *is*
unambiguous is the crossing itself: as the sensor passes through an edge
(from either direction), distance dips to (near) zero and rises again
symmetrically on the other side. `RealTimeClassifier` watches for that dip
and toggles an inside/outside flag per region each time it sees one — a
Schmitt trigger: `crossing_threshold` is how close counts as a crossing,
`rearm_threshold` is how far the reading must recede afterwards before the
*next* crossing can register, which is what stops sensor noise dithering
near one edge from being counted as several crossings. See the extended
rationale — including the honest limitation that a close approach which
turns back without truly crossing is indistinguishable from a real
crossing, given magnitude alone — in the [`classifier.py`](src/sensor_sim/classifier.py)
module docstring. Note that this logic is entirely dimension-agnostic:
`RealTimeClassifier` only ever sees the two distance *numbers*, never the
2D geometry that produced them, so the 1D-to-2D rework of this project
changed `regions.py`/`motion.py`/`sensor.py` but not a single line of
`classifier.py`.

**Regions are disjoint by design, but the classifier doesn't require it.**
Each region gets its own, fully independent crossing detector —
`RealTimeClassifier` never looks at region geometry, just the two
booleans `inside_a`/`inside_b`. The packaged scenarios keep A and B
disjoint (as the task describes), but nothing stops a region config from
making them adjacent or genuinely overlapping; `configs/overlap_scenario.yaml`
demonstrates this. If both detectors are ever `True` at once (only
possible when A and B overlap), Region A takes priority — the classifier
always returns exactly one state, never a hybrid one.

**A narrow region can trap a naive version of this detector.** If a
region's half-width (half of its *shorter* side) is smaller than
`rearm_threshold`, the sensor could be certainly inside it yet never read
far enough from an edge to re-arm — so the detector would latch "inside"
forever and miss the exit crossing. `AppConfig` validates `rearm_threshold`
against both regions' half-widths at load time and refuses a config where
this can happen, rather than failing silently at run time.

**Variable speed via waypoint-seeking, not a formula over time.** Real GPS
speed isn't `avg_speed` with a single sine wave riding on it — it's
"roughly head towards the next landmark, speeding up and slowing down
along the way." `MotionSimulator` steers towards a looping list of 2D
waypoints (moving along the straight-line direction to the next one) while
speed oscillates around a configured average with added Gaussian jitter.
This is also what makes the default route reliably pass through both
regions and back again, which a purely random walk would not guarantee.

**Configuration is data, not constants.** Region corners, motion/noise
parameters, and classifier thresholds all live in a YAML file
(`src/sensor_sim/data/default.yaml`, or any file passed via `--config`) and
flow into typed, validated dataclasses in `config.py`. No Python file
contains a region corner or an average speed — changing the scenario never
means editing code. `configs/alt_scenario.yaml` demonstrates this with a
completely different (still disjoint) scenario, and
`configs/overlap_scenario.yaml` with an overlapping-regions one.

**Classification is decoupled from display.** `simulate_ticks()` is a plain
generator with no wall-clock sleeping — cheap and deterministic to unit
test. `pace()` is the only place that sleeps, so "run as fast as possible"
(tests, CI) and "run live" (the demo) are the exact same simulation,
consumed two different ways.

**Reads are tick-driven, not clock-driven — a slow consumer can't corrupt
them.** `get_dist_a()`/`get_dist_b()` only ever report the position
`MotionSimulator` currently holds; that position only changes when
something explicitly calls `motion.step(dt)`, which only happens once per
tick inside `simulate_ticks()`'s loop. So if a caller goes quiet for a
while — 6 seconds, a minute, doesn't matter — and then reads again, it
gets the *same* true position (fresh noise aside), never a jump. The only
place wall-clock time enters at all is `pace()`, and even there a stalled
consumer just means `pace()` stops sleeping until it's caught back up to
schedule — every tick still gets delivered, in order, none skipped.

## Configuring a scenario

```yaml
regions:
  A: { low: [0.0, 0.0], high: [10.0, 10.0] }
  B: { low: [22.0, -4.0], high: [32.0, 6.0] }  # a clear gap from A -- disjoint

classifier:
  crossing_threshold: 0.3   # how close to an edge counts as "crossing" it
  rearm_threshold: 1.5      # must stay below both regions' half-widths
```

Regions are ordinarily disjoint (as above and in both packaged scenarios),
but the classifier doesn't require it — `configs/overlap_scenario.yaml`
shows two genuinely overlapping boxes, where the classifier reports `IN_A`
throughout the shared span since Region A takes priority. `AppConfig`
only rejects configs where `rearm_threshold` isn't small enough for either
region's half-width, so a misconfigured scenario fails fast with a clear
error instead of producing a detector that gets stuck or double-counts
crossings at run time.

## Testing

```bash
pytest                 # unit tests: regions, motion, sensor, classifier, config, simulation
ruff check .           # lint
mypy src               # types
```

Notable coverage:
- `Rectangle.unsigned_distance`: zero on every edge (including a corner),
  peaks at the center while inside, equal just inside and just outside the
  same edge (the core ambiguity the classifier has to handle), and
  correctly Euclidean — not axis-aligned — when the nearest boundary point
  is a corner.
- The crossing detector: a full enter → dwell → re-arm → exit cycle,
  that dithering near an edge before re-arming does *not* cause extra
  toggles, and that it is a pure function of `(internal state, reading)` —
  no lookahead.
- The packaged default scenario is asserted to visit all three states
  (`IN_A`, `IN_B`, `OUTSIDE`) over its route, and distance readings are
  asserted to never go negative; `configs/overlap_scenario.yaml` is
  asserted to resolve to a single state throughout, with `IN_A` taking
  priority in the overlap.
- Config validation (missing regions, invalid thresholds, an unreachable
  rearm threshold, non-positive `dt`/`speed_period`/`realtime_factor`,
  negative `duration`/`noise_std`) fails with a clear `ValueError` at
  load time rather than crashing or hanging mid-run; overlapping regions
  are asserted to load without error.
- `pace()`, with a fake clock (no real sleeping): a consumer that stalls
  for several seconds between reads never causes a tick to be skipped,
  and `MotionSimulator`/the sensor API never move or drift just because
  wall-clock time passed without an explicit `step()`.

## Project layout

```
src/sensor_sim/
  regions.py          Rectangle (an axis-aligned box region)
  config.py           AppConfig and friends, YAML loading + validation
  motion.py           MotionSimulator (true position (x, y) over time)
  sensor.py           get_dist_a() / get_dist_b()
  classifier.py       RealTimeClassifier, RegionState (crossing detector)
  simulation.py       simulate_ticks(), pace(), Tick
  visualize.py        LiveView ((x, y) path + distance-vs-time panels)
  cli.py              sensor-sim entry point
  data/default.yaml   Packaged default scenario
configs/
  alt_scenario.yaml     A second disjoint-regions scenario with different boxes/noise/thresholds
  overlap_scenario.yaml An overlapping-regions scenario (IN_A takes priority)
tests/
```

## License

MIT, see [LICENSE](LICENSE).
