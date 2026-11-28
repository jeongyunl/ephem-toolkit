"""Store-only play-oem data-path profiler for analysis-3."""

from __future__ import annotations

import argparse
import cProfile
import json
from pathlib import Path
import pstats
import statistics
import sys
import time
from threading import Event
from typing import Callable, Sequence

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.streaming_oem import read_oem_into_store


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_OEM = ROOT / "tests/data/ISS_2026-05-20.OEM"
DEFAULT_SCENARIO = Path(__file__).with_name("scenario-recorded.json")
STATION_LOCATIONS = (
    (0.0, 0.0),
    (35.68, 139.69),
    (-35.3, 149.1),
)


def _load_store(source: Path) -> OemDataStore:
    store = OemDataStore()
    epoch = store.begin(OemDataStore.capacity_for_file(source))
    completion = read_oem_into_store(
        source,
        store,
        batch_size=512,
        on_append=lambda _notice: None,
        cancel_event=Event(),
        expected_epoch=epoch,
    )
    if completion.state_count != store.snapshot().sample_count:
        store.close()
        raise RuntimeError("store and completion counts do not match")
    return store


def _median(samples: Sequence[float]) -> float:
    return statistics.median(samples)


def _measure(function: Callable[[], object], repeats: int) -> list[float]:
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        samples.append(time.perf_counter() - started)
    return samples


def _stations(count: int) -> tuple[GroundStation, ...]:
    locations = STATION_LOCATIONS[:count]
    if count > len(locations):
        locations = tuple(
            (
                ((index * 37.2) % 180.0) - 90.0,
                ((index * 137.5) % 360.0) - 180.0,
            )
            for index in range(count)
        )
    return tuple(
        GroundStation(
            station_id=f"analysis-3-{index + 1:02d}",
            name=f"Analysis 3 station {index + 1:02d}",
            latitude_deg=latitude,
            longitude_deg=longitude,
            altitude_m=0.0,
            minimum_elevation_deg=10,
        )
        for index, (latitude, longitude) in enumerate(locations)
    )


def _recorded_ranges(scenario: Path, start_s: float, end_s: float) -> tuple[tuple[float, float], ...]:
    document = json.loads(scenario.read_text(encoding="utf-8"))
    events = document.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("recorded scenario must contain events")
    coverage = end_s - start_s
    ranges: list[tuple[float, float]] = []
    for event in events:
        start_fraction = float(event["start_fraction"])
        end_fraction = float(event["end_fraction"])
        ranges.append(
            (
                start_s + start_fraction * coverage,
                start_s + end_fraction * coverage,
            )
        )
    return tuple(ranges)


def run(source: Path, scenario: Path, repeats: int) -> None:
    store = _load_store(source)
    try:
        snapshot = store.snapshot()
        start_s = float(snapshot.raw[0, 0])
        end_s = float(snapshot.raw[-1, 0])
        coverage = end_s - start_s
        midpoint_s = start_s + coverage * 0.5
        ranges = _recorded_ranges(scenario, start_s, end_s)

        def state_work() -> None:
            store.state_at(snapshot, midpoint_s)
            store.earth_fixed_state_at(snapshot, midpoint_s)

        def range_work() -> None:
            for bounds in ranges:
                store.earth_fixed_positions(snapshot, bounds, wait=True)
                store.ground_track(snapshot, bounds, wait=True)
                for station in stations:
                    store.station_access(
                        snapshot,
                        station,
                        bounds,
                        wait=True,
                    )

        print(
            f"Input: {source}; bytes={source.stat().st_size}; "
            f"samples={snapshot.sample_count}; "
            f"coverage_days={(coverage / 86400.0):.3f}"
        )
        print(f"Recorded ranges: {len(ranges)}; repeats={repeats}")

        state_samples = _measure(state_work, repeats)
        print(
            f"State lookup (raw + Earth-fixed): median="
            f"{_median(state_samples):.6f}s "
            f"samples={[round(value, 6) for value in state_samples]}"
        )

        for station_count in (1, 3, 10):
            stations = _stations(station_count)
            samples = _measure(range_work, repeats)
            station_queries = len(ranges) * station_count
            print(
                f"Recorded range sweep ({station_count} stations): median="
                f"{_median(samples):.6f}s "
                f"samples={[round(value, 6) for value in samples]}"
                f"; station_queries={station_queries}"
            )
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oem", type=Path, default=DEFAULT_OEM)
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    if not args.oem.is_file():
        parser.error(f"OEM file does not exist: {args.oem}")
    if not args.scenario.is_file():
        parser.error(f"scenario file does not exist: {args.scenario}")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    if args.profile is not None:
        profiler = cProfile.Profile()
        profiler.enable()
        run(args.oem, args.scenario, args.repeats)
        profiler.disable()
        args.profile.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(args.profile))
        if args.summary is not None:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            with args.summary.open("w", encoding="utf-8") as stream:
                pstats.Stats(
                    profiler,
                    stream=stream,
                ).strip_dirs().sort_stats("cumtime").print_stats(50)
    else:
        run(args.oem, args.scenario, args.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
