"""Tests for the play-oem command-line scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest

from ephem_toolkit.play_oem import cli, main
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.play_oem_cli import build_arg_parser, parse_arguments


def test_help_shows_command_and_input(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    help_output = capsys.readouterr().out
    assert "play-oem" in help_output
    assert "<input_oem>" in help_output


def test_input_path_is_parsed() -> None:
    args = parse_arguments(build_arg_parser(), ["orbit.oem"])

    assert args.input_oem == "orbit.oem"
    assert args.speed == 1.0
    assert not args.reverse
    assert args.start is None
    assert not args.autoplay
    assert not args.loop
    assert args.plots == ("overview",)
    assert args.fps == 30


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("overview, trajectory-3d", ("trajectory-3d", "speed-altitude")),
        ("state", ("state-components",)),
        ("state-vectors", ("trajectory-3d", "state-components")),
        (
            "motion",
            ("rtn", "angular-velocity", "direction-change", "distance"),
        ),
        (
            "all",
            (
                "trajectory-3d",
                "state-components",
                "speed-altitude",
                "rtn",
                "angular-velocity",
                "direction-change",
                "distance",
            ),
        ),
    ],
)
def test_plots_option_expands_names_and_groups(
    selection: str, expected: tuple[str, ...]
) -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", "--plots", selection],
    )

    assert args.plots == expected


def test_plots_option_rejects_unknown_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(build_arg_parser(), ["orbit.oem", "--plots", "not-a-plot"])

    assert exc_info.value.code == 2
    assert "unknown plot name 'not-a-plot'" in capsys.readouterr().err


def test_missing_input_reports_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2
    error_output = capsys.readouterr().err
    assert "usage:" in error_output
    assert "<input_oem>" in error_output


def test_duration_and_time_unit_options_are_accepted() -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", "-d", "90m", "--time-unit", "minutes"],
    )

    assert args.input_oem == "orbit.oem"
    assert args.duration == "90m"
    assert args.time_unit == "minutes"


def test_playback_options_are_parsed() -> None:
    args = parse_arguments(
        build_arg_parser(),
        [
            "orbit.oem",
            "--speed",
            "-25",
            "--reverse",
            "--start",
            "30m",
            "--autoplay",
            "--loop",
            "--fps",
            "60",
        ],
    )

    assert args.speed == -25.0
    assert args.reverse
    assert args.start == "30m"
    assert args.autoplay
    assert args.loop
    assert args.fps == 60


@pytest.mark.parametrize("value", ["0", "0.5", "1001", "nan", "inf", "fast"])
def test_cli_rejects_invalid_speed_values(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(build_arg_parser(), ["orbit.oem", "--speed", value])

    assert exc_info.value.code == 2
    assert "--speed" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["0", "-1", "1001", "30.5", "fast"])
def test_cli_rejects_invalid_fps_values(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(build_arg_parser(), ["orbit.oem", "--fps", value])

    assert exc_info.value.code == 2
    assert "--fps" in capsys.readouterr().err


def test_static_output_option_is_not_supported() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(build_arg_parser(), ["orbit.oem", "-o", "orbit.png"])

    assert exc_info.value.code == 2


def test_cli_reports_missing_input_file(
    capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    result = cli([str(tmp_path / "missing.oem")])

    assert result == 1
    assert "File not found" in capsys.readouterr().err


def test_cli_loads_oem_and_launches_player(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )
    from ephem_toolkit.play_oem import app

    launched: dict[str, object] = {}

    class FakePlayerApp:
        def __init__(
            self,
            clock,
            series,
            time_unit,
            cursor,
            object_name,
            frame_context,
            *,
            plots,
            tick_interval_ms,
        ) -> None:
            launched["clock"] = clock
            launched["series"] = series
            launched["time_unit"] = time_unit
            launched["cursor"] = cursor
            launched["object_name"] = object_name
            launched["frame_context"] = frame_context
            launched["plots"] = plots
            launched["tick_interval_ms"] = tick_interval_ms

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([str(input_oem), "--duration", "1h", "--time-unit", "minutes"])

    output = capsys.readouterr().out
    assert "Loaded 721 states" in output
    assert "Using 16 states after duration filtering" in output
    assert "Prepared orbit series with 16 samples using minutes." in output
    assert launched["run"] is True
    assert launched["clock"].t_start < launched["clock"].t_end
    assert launched["series"].elapsed_time.size == 16
    assert isinstance(launched["cursor"], OemCursor)
    assert launched["cursor"].t_start == launched["clock"].t_start
    assert launched["cursor"].t_end == launched["clock"].t_end
    assert launched["object_name"] == "ISS"
    assert launched["frame_context"] == "EME2000 / Earth"
    assert launched["plots"] == ("overview",)
    assert launched["clock"].rate == 1.0
    assert launched["clock"].t_now == launched["clock"].t_start
    assert not launched["clock"].playing
    assert not launched["clock"].loop
    assert launched["tick_interval_ms"] == 34


def test_cli_configures_reverse_autoplay_loop_and_elapsed_start(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )
    from ephem_toolkit.play_oem import app

    launched: dict[str, object] = {}

    class FakePlayerApp:
        def __init__(
            self,
            clock,
            _series,
            _time_unit,
            _cursor,
            _object_name,
            _frame_context,
            *,
            plots,
            tick_interval_ms,
        ) -> None:
            launched["clock"] = clock
            launched["tick_interval_ms"] = tick_interval_ms

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main(
        [
            str(input_oem),
            "--duration",
            "1h",
            "--reverse",
            "--speed",
            "10",
            "--autoplay",
            "--loop",
            "--fps",
            "50",
        ]
    )

    clock = launched["clock"]
    assert launched["run"] is True
    assert clock.rate == -10.0
    assert clock.t_now == clock.t_end
    assert clock.playing
    assert clock.loop
    assert launched["tick_interval_ms"] == 20
    clock.tick(400.0)
    assert clock.playing
    assert clock.t_start <= clock.t_now < clock.t_end
    assert "Using 16 states after duration filtering" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("direction_options", "boundary"),
    [
        ([], "end"),
        (["--reverse"], "start"),
    ],
)
def test_cli_autoplay_pauses_at_forward_and_reverse_boundaries(
    direction_options: list[str],
    boundary: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )
    from ephem_toolkit.play_oem import app

    launched: dict[str, object] = {}

    class FakePlayerApp:
        def __init__(
            self,
            clock,
            _series,
            _time_unit,
            _cursor,
            _object_name,
            _frame_context,
            *,
            plots,
            tick_interval_ms,
        ) -> None:
            launched["clock"] = clock

        def run(self) -> None:
            pass

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)
    main(
        [
            str(input_oem),
            "--duration",
            "1h",
            "--autoplay",
            *direction_options,
        ]
    )
    clock = launched["clock"]
    clock.tick(3600.0)

    expected_time = clock.t_end if boundary == "end" else clock.t_start
    assert clock.t_now == expected_time
    assert not clock.playing
    capsys.readouterr()


def test_cli_resolves_elapsed_and_utc_start_times(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )
    from ephem_toolkit.core import time_utils
    from ephem_toolkit.play_oem import app
    from ephem_toolkit.play_oem.data import read_oem_states

    _, timestamps_s, _ = read_oem_states(input_oem)
    expected_t = timestamps_s[0] + 30 * 60
    utc_start = time_utils.datetime_to_iso8601(time_utils.tt_s_to_datetime(expected_t))
    launched: list[tuple[float, float]] = []

    class FakePlayerApp:
        def __init__(
            self,
            clock,
            _series,
            _time_unit,
            _cursor,
            _object_name,
            _frame_context,
            *,
            plots,
            tick_interval_ms,
        ) -> None:
            launched.append((clock.t_now, clock.rate))

        def run(self) -> None:
            pass

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([str(input_oem), "--duration", "1h", "--start", "30m"])
    main([str(input_oem), "--duration", "1h", "--start", utc_start])
    main(
        [
            str(input_oem),
            "--duration",
            "1h",
            "--speed",
            "-10",
            "--reverse",
            "--start",
            "30m",
        ]
    )

    assert [time for time, _rate in launched] == pytest.approx(
        [expected_t, expected_t, expected_t]
    )
    assert [rate for _time, rate in launched] == [1.0, 1.0, 10.0]
    capsys.readouterr()


def test_cli_rejects_invalid_and_out_of_range_start_times(
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )

    for start_value in ("not-a-time", "2h"):
        with pytest.raises(SystemExit) as exc_info:
            main([str(input_oem), "--duration", "1h", "--start", start_value])
        assert exc_info.value.code == 1
        assert "failed to parse start time" in capsys.readouterr().err


def test_cli_reports_invalid_duration(capsys: pytest.CaptureFixture[str]) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )

    with pytest.raises(SystemExit) as exc_info:
        main([str(input_oem), "--duration", "not-a-duration"])

    assert exc_info.value.code == 1
    assert "failed to parse duration" in capsys.readouterr().err
