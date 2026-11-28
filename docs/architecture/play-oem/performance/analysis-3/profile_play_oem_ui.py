"""Repeatable headless-driven play-oem UI range-replay profiler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import wx

from ephem_toolkit.play_oem import playback_data
from ephem_toolkit.play_oem.app import PlayerApp
from ephem_toolkit.play_oem.config import load_config
from ephem_toolkit.play_oem.saved_state import load_saved_state


def _load_scenario(
    path: Path,
) -> tuple[
    int,
    float,
    float,
    int,
    float,
    float,
    float,
    int,
    tuple[tuple[float, float], ...],
    tuple[float, ...],
]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("kind") == "playback-range-recording":
        events = tuple(
            (
                float(event["start_fraction"]),
                float(event["end_fraction"]),
            )
            for event in document["events"]
        )
        pauses = tuple(
            float(event.get("pause_s", 0.0))
            for event in document["events"][1:]
        )
        if not events:
            raise ValueError("recorded scenario must contain at least one event")
        if any(
            not 0.0 <= start <= end <= 1.0
            for start, end in events
        ):
            raise ValueError("recorded range fractions must fit within OEM coverage")
        return 1, 0.0, 1.0, 20, 0.5, 0.25, 0.1, 5, events, pauses

    cycles = int(document["cycles"])
    dwell_s = float(document["dwell_s"])
    settle_s = float(document["settle_s"])
    drag_steps = int(document.get("drag_steps", 20))
    playback_window_fraction = float(
        document.get("playback_window_fraction", 0.5)
    )
    start_fraction = float(document.get("start_fraction", 0.25))
    pan_fraction = float(document.get("pan_fraction", 0.1))
    pan_count = int(document.get("pan_count", 5))
    if cycles < 1:
        raise ValueError("scenario cycles must be at least 1")
    if dwell_s < 0 or settle_s < 0:
        raise ValueError("scenario durations must be non-negative")
    if drag_steps < 1:
        raise ValueError("scenario drag_steps must be at least 1")
    if pan_count < 1:
        raise ValueError("scenario pan_count must be at least 1")
    if not 0.0 < playback_window_fraction < 1.0:
        raise ValueError("scenario playback_window_fraction must be within (0, 1)")
    if not 0.0 < pan_fraction <= 1.0:
        raise ValueError("scenario pan_fraction must be within (0, 1]")
    if not 0.0 <= start_fraction <= 1.0 - playback_window_fraction:
        raise ValueError("scenario start range must fit inside OEM coverage")
    return (
        cycles,
        dwell_s,
        settle_s,
        drag_steps,
        playback_window_fraction,
        start_fraction,
        pan_fraction,
        pan_count,
        (),
        (),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("oem", type=Path)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument(
        "--stay-open",
        action="store_true",
        help="keep the play-oem window open after the scenario completes",
    )
    parser.add_argument(
        "--record-scenario",
        action="store_true",
        help="record manual playback-range interactions instead of replaying a scenario",
    )
    parser.add_argument(
        "--record-output",
        type=Path,
        default=Path(
            "docs/architecture/play-oem/performance/analysis-3/scenario-recorded.json"
        ),
        help="JSON file written when manual scenario recording completes",
    )
    args = parser.parse_args(argv)

    if not args.oem.is_file():
        parser.error(f"OEM file does not exist: {args.oem}")
    if not args.config_file.is_file():
        parser.error(f"config file does not exist: {args.config_file}")
    if not args.state_file.is_file():
        parser.error(f"state file does not exist: {args.state_file}")

    (
        cycles,
        dwell_s,
        settle_s,
        drag_steps,
        playback_window_fraction,
        start_fraction,
        pan_fraction,
        pan_count,
        recorded_ranges,
        recorded_pauses,
    ) = _load_scenario(args.scenario)
    if recorded_ranges:
        ranges = recorded_ranges
        range_dwells = recorded_pauses
    else:
        pan_shift = playback_window_fraction * pan_fraction
        forward_end = start_fraction + pan_shift * pan_count
        if forward_end + playback_window_fraction > 1.0 + 1e-12:
            raise ValueError("five forward pans exceed OEM coverage")
        ranges = tuple(
            (
                start_fraction + pan_shift * step,
                start_fraction + pan_shift * step + playback_window_fraction,
            )
            for step in range(pan_count + 1)
        )
        ranges += tuple(
            (
                forward_end - pan_shift * step,
                forward_end - pan_shift * step + playback_window_fraction,
            )
            for step in range(1, pan_count + 1)
        )
        range_dwells = tuple(dwell_s for _range in ranges[1:])
    user_config = load_config(args.config_file)
    saved_state = load_saved_state(args.state_file)
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
        data_views=saved_state.open_data_views or user_config.data_views,
        display_time_zone=user_config.display_time_zone,
        time_snapping=user_config.time_snapping,
        use_oem_interpolation=user_config.use_oem_interpolation,
        interpolation_method=user_config.interpolation_method,
        interpolation_degree=user_config.interpolation_degree,
        oem_interpolation=initial_data.oem_interpolation,
        oem_interpolation_degree=initial_data.oem_interpolation_degree,
        saved_state=saved_state,
        ground_stations=list(user_config.ground_stations),
        initial_file_path=str(args.oem),
        oem_loaded=False,
        loaded_file_name=None,
        config_path=str(args.config_file),
        state_path=str(args.state_file),
    )

    timer = wx.Timer(player.frame)
    started_at = time.perf_counter()
    load_complete_at: float | None = None
    settle_complete_at: float | None = None
    cycle = 0
    range_index = 1
    current_range = ranges[0]
    drag_from: tuple[float, float] | None = None
    drag_target: tuple[float, float] | None = None
    drag_step = 0
    next_action_at: float | None = None
    failed = [False]
    recorded_events: list[dict[str, float]] = []
    last_recorded_range: tuple[float, float] | None = None
    recording_started_at: float | None = None

    def save_recording(event: object | None = None) -> None:
        args.record_output.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "kind": "playback-range-recording",
            "oem": str(args.oem),
            "capture_duration_s": (
                0.0
                if recording_started_at is None
                else time.perf_counter() - recording_started_at
            ),
            "events": recorded_events,
        }
        args.record_output.write_text(
            json.dumps(document, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Recorded scenario: {args.record_output}")
        if event is not None:
            event.Skip()

    if args.record_scenario:
        pass

    def on_tick(_event: wx.TimerEvent) -> None:
        nonlocal cycle, range_index, next_action_at
        nonlocal current_range, drag_from, drag_target, drag_step
        nonlocal load_complete_at, settle_complete_at
        nonlocal recording_started_at, last_recorded_range
        del _event

        now = time.perf_counter()
        if player._load_state.failed:
            failed[0] = True
            timer.Stop()
            player.frame.Close(force=True)
            return
        if not player._load_state.coverage_complete:
            return
        if args.record_scenario:
            if recording_started_at is None:
                recording_started_at = time.perf_counter()
                coverage_span = player.clock.t_end - player.clock.t_start
                if coverage_span > 0:
                    start_fraction = (
                        player.clock.playback_start - player.clock.t_start
                    ) / coverage_span
                    end_fraction = (
                        player.clock.playback_end - player.clock.t_start
                    ) / coverage_span
                    initial_range = (
                        min(1.0, max(0.0, start_fraction)),
                        min(1.0, max(0.0, end_fraction)),
                    )
                    recorded_events.append(
                        {
                            "t_s": 0.0,
                            "start_fraction": initial_range[0],
                            "end_fraction": initial_range[1],
                            "pause_s": 0.0,
                        }
                    )
                    last_recorded_range = initial_range
                    save_recording()
            else:
                coverage_span = player.clock.t_end - player.clock.t_start
                if coverage_span > 0:
                    range_value = (
                        min(
                            1.0,
                            max(
                                0.0,
                                (
                                    player.clock.playback_start
                                    - player.clock.t_start
                                )
                                / coverage_span,
                            ),
                        ),
                        min(
                            1.0,
                            max(
                                0.0,
                                (
                                    player.clock.playback_end
                                    - player.clock.t_start
                                )
                                / coverage_span,
                            ),
                        ),
                    )
                    if range_value != last_recorded_range:
                        event_time_s = time.perf_counter() - recording_started_at
                        pause_s = (
                            event_time_s - recorded_events[-1]["t_s"]
                            if recorded_events
                            else 0.0
                        )
                        recorded_events.append(
                            {
                                "t_s": event_time_s,
                                "start_fraction": range_value[0],
                                "end_fraction": range_value[1],
                                "pause_s": pause_s,
                            }
                        )
                        last_recorded_range = range_value
                        save_recording()
            return
        if load_complete_at is None:
            load_complete_at = now
            coverage_span = player.clock.t_end - player.clock.t_start
            start_s = player.clock.t_start + current_range[0] * coverage_span
            end_s = player.clock.t_start + current_range[1] * coverage_span
            player._set_range_dragging(True)
            player._apply_playback_bounds(start_s, end_s)
            player._set_range_dragging(False)
            settle_complete_at = now + settle_s
            next_action_at = settle_complete_at
            return
        if now < settle_complete_at:
            return

        if next_action_at is not None and now < next_action_at:
            return
        if cycle >= cycles:
            timer.Stop()
            if not args.stay_open:
                player.frame.Close(force=True)
            return

        coverage_start = player.clock.t_start
        coverage_end = player.clock.t_end
        coverage_span = coverage_end - coverage_start

        if drag_from is not None and drag_target is not None:
            drag_step += 1
            alpha = drag_step / drag_steps
            start_fraction = (
                drag_from[0] + (drag_target[0] - drag_from[0]) * alpha
            )
            end_fraction = (
                drag_from[1] + (drag_target[1] - drag_from[1]) * alpha
            )
            start_s = coverage_start + start_fraction * coverage_span
            end_s = coverage_start + end_fraction * coverage_span
            player._apply_playback_bounds(start_s, end_s)
            current_range = (start_fraction, end_fraction)

            if drag_step >= drag_steps:
                player._set_range_dragging(False)
                drag_from = None
                drag_target = None
                drag_step = 0
                range_index += 1
                if range_index >= len(ranges):
                    range_index = 0
                    cycle += 1
                dwell_for_transition = (
                    range_dwells[range_index - 1]
                    if range_index > 0 and range_index - 1 < len(range_dwells)
                    else dwell_s
                )
                next_action_at = now + dwell_for_transition
            else:
                next_action_at = now
            return

        drag_target = ranges[range_index]
        drag_from = current_range
        drag_step = 0
        start_fraction = drag_from[0]
        end_fraction = drag_from[1]
        start_s = coverage_start + start_fraction * coverage_span
        end_s = coverage_start + end_fraction * coverage_span
        player._set_range_dragging(True)
        player._apply_playback_bounds(start_s, end_s)
        next_action_at = now

    player.frame.Bind(wx.EVT_TIMER, on_tick, timer)
    if not timer.Start(10):
        raise RuntimeError("could not start wx profiling timer")
    player.run()

    if args.record_scenario:
        save_recording()

    if failed[0]:
        raise RuntimeError("OEM load failed during repeatable UI profiling")
    if load_complete_at is None:
        raise RuntimeError("OEM load did not complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
