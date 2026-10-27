"""Repeatable data-layer and optional wx event-loop benchmarks for play-oem."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import statistics
import time
from typing import Callable, Optional, Sequence

from ephem_toolkit.play_oem.data import read_oem_states
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.ground_track import (
    EarthFixedPositionCache,
    prepare_ground_track,
    state_position_to_itrf_m,
)
from ephem_toolkit.play_oem.playback_data import load_playback_data
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.station_access import StationAccessCache
from ephem_toolkit.play_oem.time_unit import TimeUnit


_STATION_LOCATIONS = (
    (0.0, 0.0),
    (35.68, 139.69),
    (-35.3, 149.1),
    (40.7, -74.0),
    (51.5, 0.0),
    (-33.9, 151.2),
    (28.6, 77.2),
    (37.8, -122.4),
    (-23.5, -46.6),
    (64.1, -21.9),
)


def _measure(function: Callable[[], object], repeats: int) -> list[float]:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        samples.append(time.perf_counter() - started)
    return samples


def _print_measurement(name: str, samples: list[float]) -> None:
    print(
        f"{name}: median={statistics.median(samples):.3f}s "
        f"samples={[round(sample, 3) for sample in samples]}"
    )


def _stations(count: int) -> list[GroundStation]:
    return [
        GroundStation(
            station_id=f"benchmark-{index + 1:02d}",
            name=f"Benchmark station {index + 1:02d}",
            latitude_deg=latitude,
            longitude_deg=longitude,
            altitude_m=0.0,
        )
        for index, (latitude, longitude) in enumerate(_STATION_LOCATIONS[:count])
    ]


def run_data_benchmarks(source: Path, repeats: int, range_days: float) -> None:
    """Measure parser, derived-series, range conversion, and station access costs."""
    parsed_oem, timestamps_s, states_m = read_oem_states(source)
    segment_ids = parsed_oem.segment_ids[: len(timestamps_s)]
    selected_time_unit = TimeUnit.for_duration(timestamps_s[-1] - timestamps_s[0])

    parse_samples = _measure(lambda: read_oem_states(source), repeats)
    series_samples = _measure(
        lambda: compute_orbit_series(
            timestamps_s, states_m, selected_time_unit, segment_ids
        ),
        repeats,
    )
    preparation_samples = _measure(lambda: load_playback_data(source), repeats)

    playback_data = load_playback_data(source)
    source_track = playback_data.ground_track_source
    if source_track is None:
        raise RuntimeError("loaded playback data has no Ground Track source")
    start_s = float(playback_data.cursor.timestamps_s[0])
    end_s = float(playback_data.cursor.timestamps_s[-1])
    range_end_s = min(start_s + range_days * 86_400.0, end_s)
    bounds = (start_s, range_end_s)
    if range_end_s <= start_s:
        raise ValueError("the OEM must span a positive time range")

    sample_index = len(playback_data.cursor.timestamps_s) // 2
    state_position_to_itrf_m(
        playback_data.cursor.states_m[sample_index],
        source_track.frame_name,
        float(playback_data.cursor.timestamps_s[sample_index]),
    )
    ground_track_samples = _measure(
        lambda: prepare_ground_track(
            source_track,
            position_cache=EarthFixedPositionCache(),
            bounds=bounds,
        ),
        repeats,
    )

    print(f"Input: {source}")
    print(
        f"Samples: {playback_data.source_sample_count}; "
        f"coverage: {(end_s - start_s) / 86_400.0:.3f} days; "
        f"range: {(range_end_s - start_s) / 86_400.0:.3f} days"
    )
    _print_measurement("OEM parse", parse_samples)
    _print_measurement("compute_orbit_series", series_samples)
    _print_measurement("Full playback preparation", preparation_samples)
    _print_measurement("Ground Track range conversion", ground_track_samples)

    for station_count in (1, 3, 10):
        stations = _stations(station_count)

        def prepare_access() -> None:
            cache = StationAccessCache()
            for station in stations:
                cache.prepare(
                    source_track,
                    playback_data.cursor,
                    station,
                    bounds,
                )

        samples = _measure(prepare_access, repeats)
        _print_measurement(f"Access analysis ({station_count} stations)", samples)


def run_gui_stall_probe(source: Path) -> None:
    """Measure wx timer delays while the real play-oem app incrementally loads a file."""
    import wx

    from ephem_toolkit.play_oem import playback_data
    from ephem_toolkit.play_oem.app import PlayerApp

    initial_data = playback_data.empty_playback_data()
    player = PlayerApp(
        initial_data.clock,
        initial_data.series,
        initial_data.time_unit,
        initial_data.cursor,
        initial_data.object_name,
        initial_data.frame_context,
        dashboard_context=initial_data.dashboard_context,
        metadata_details=initial_data.metadata_details,
        ground_track_source=initial_data.ground_track_source,
        initial_file_path=str(source),
        oem_loaded=False,
    )
    timer = wx.Timer(player.frame)
    last_tick: list[Optional[float]] = [None]
    load_finished_at: list[Optional[float]] = [None]
    load_timer_gaps_s = []
    idle_timer_gaps_s = []
    refresh_metrics = {
        "calls": 0,
        "retained_views": 0,
        "replaced_views": 0,
        "retained_figures": 0,
        "replaced_figures": 0,
        "durations_s": [],
    }
    open_view_durations: dict[str, list[float]] = {}
    inside_refresh = [False]
    original_refresh = player._refresh_incremental_views
    original_open_panel_view = player.open_panel_view

    def observe_open_panel_view(
        name: str, panel_id: str, stack: str = "middle", *, force_replace: bool = False
    ) -> None:
        started = time.perf_counter()
        original_open_panel_view(
            name, panel_id, stack, force_replace=force_replace
        )
        if inside_refresh[0]:
            open_view_durations.setdefault(name, []).append(
                time.perf_counter() - started
            )

    def observe_refresh(*, force: bool = False) -> None:
        before = {
            panel_id: (
                id(opened.view),
                None if opened.canvas is None else id(opened.canvas),
            )
            for panel_id, opened in player._open_panels.items()
        }
        refresh_started = time.perf_counter()
        inside_refresh[0] = True
        try:
            original_refresh(force=force)
        finally:
            inside_refresh[0] = False
        refresh_metrics["durations_s"].append(time.perf_counter() - refresh_started)
        after = {
            panel_id: (id(opened.view), None if opened.canvas is None else id(opened.canvas))
            for panel_id, opened in player._open_panels.items()
        }
        for panel_id in before.keys() & after.keys():
            old_view, old_figure = before[panel_id]
            new_view, new_figure = after[panel_id]
            if old_view == new_view:
                refresh_metrics["retained_views"] += 1
            else:
                refresh_metrics["replaced_views"] += 1
            if old_figure == new_figure:
                refresh_metrics["retained_figures"] += 1
            else:
                refresh_metrics["replaced_figures"] += 1
        refresh_metrics["calls"] += 1

    player._refresh_incremental_views = observe_refresh
    player.open_panel_view = observe_open_panel_view
    result = {"failed": False, "timed_out": False}
    started_at = time.perf_counter()

    def on_probe_tick(_event: wx.TimerEvent) -> None:
        del _event
        now = time.perf_counter()
        previous = last_tick[0]
        if (
            previous is not None
            and player._active_load_path is not None
        ):
            if player._oem_coverage_complete:
                idle_timer_gaps_s.append(now - previous)
            else:
                load_timer_gaps_s.append(now - previous)
        last_tick[0] = now

        if player._active_load_failed:
            result["failed"] = True
            if load_finished_at[0] is None:
                load_finished_at[0] = now
        elif player._oem_coverage_complete:
            if load_finished_at[0] is None:
                load_finished_at[0] = now
        elif now - started_at > 300.0:
            result["timed_out"] = True
            load_finished_at[0] = now

        if load_finished_at[0] is not None and now - load_finished_at[0] >= 2.0:
            timer.Stop()
            player.frame.Close(force=True)

    player.frame.Bind(wx.EVT_TIMER, on_probe_tick, timer)
    if not timer.Start(10):
        raise RuntimeError("could not start wx benchmark timer")
    player.run()

    if not load_timer_gaps_s:
        raise RuntimeError(
            "wx timer probe recorded no intervals during incremental loading"
        )
    max_gap_ms = max(load_timer_gaps_s) * 1000.0
    median_gap_ms = statistics.median(load_timer_gaps_s) * 1000.0
    print(
        f"wx load timer gaps: samples={len(load_timer_gaps_s)}, "
        f"median={median_gap_ms:.1f}ms, max={max_gap_ms:.1f}ms, "
        f"over_100ms={sum(gap > 0.1 for gap in load_timer_gaps_s)}"
    )
    if idle_timer_gaps_s:
        print(
            f"wx post-load timer gaps: samples={len(idle_timer_gaps_s)}, "
            f"median={statistics.median(idle_timer_gaps_s) * 1000.0:.1f}ms, "
            f"max={max(idle_timer_gaps_s) * 1000.0:.1f}ms, "
            f"over_100ms={sum(gap > 0.1 for gap in idle_timer_gaps_s)}"
        )
    print(
        f"incremental refreshes: {refresh_metrics['calls']}, "
        f"retained/replaced views: {refresh_metrics['retained_views']}/"
        f"{refresh_metrics['replaced_views']}, retained/replaced figures: "
        f"{refresh_metrics['retained_figures']}/{refresh_metrics['replaced_figures']}, "
        f"max refresh: {max(refresh_metrics['durations_s'], default=0.0) * 1000.0:.1f}ms"
    )
    slowest_open = max(
        (
            (max(durations), name)
            for name, durations in open_view_durations.items()
            if durations
        ),
        default=(0.0, "none"),
    )
    print(
        f"slowest panel construction during refresh: {slowest_open[1]} "
        f"{slowest_open[0] * 1000.0:.1f}ms"
    )
    if result["timed_out"]:
        raise TimeoutError("incremental GUI load did not finish within 300 seconds")
    if result["failed"]:
        raise RuntimeError("incremental GUI load failed; inspect the play-oem status")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "oem",
        nargs="?",
        type=Path,
        default=Path("tests/data/JPSS-1.oem"),
        help="OEM fixture to benchmark (default: tests/data/JPSS-1.oem)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="number of unprofiled measurements per data benchmark (default: 3)",
    )
    parser.add_argument(
        "--range-days",
        type=float,
        default=1.0,
        help="Ground Track and Access plot range in days (default: 1)",
    )
    parser.add_argument(
        "--gui-stall-probe",
        action="store_true",
        help="open play-oem and measure wx timer delays during incremental loading",
    )
    parser.add_argument(
        "--skip-data-benchmarks",
        action="store_true",
        help="run only the optional GUI timer probe",
    )
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.range_days <= 0.0:
        parser.error("--range-days must be positive")
    if not args.oem.is_file():
        parser.error(f"OEM file does not exist: {args.oem}")

    print(
        f"Environment: Python {platform.python_version()}, "
        f"{platform.platform()}, repeats={args.repeats}"
    )
    if not args.skip_data_benchmarks:
        run_data_benchmarks(args.oem, args.repeats, args.range_days)
    if args.gui_stall_probe:
        run_gui_stall_probe(args.oem)
    elif args.skip_data_benchmarks:
        parser.error("--skip-data-benchmarks requires --gui-stall-probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
