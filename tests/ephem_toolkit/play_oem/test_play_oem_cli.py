"""Tests for the play-oem command-line scaffold."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any

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
    assert "--3d-backend" in help_output


def test_input_path_is_parsed() -> None:
    args = parse_arguments(build_arg_parser(), ["orbit.oem"])

    assert args.input_oem == "orbit.oem"
    assert args.plots == ("overview",)
    assert args.three_d_backend == "auto"
    assert args.config is None
    assert args.provided_options == frozenset()


@pytest.mark.parametrize("backend", ("auto", "vtk", "matplotlib"))
def test_3d_backend_option_accepts_supported_choices(backend: str) -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", "--3d-backend", backend],
    )

    assert args.three_d_backend == backend


def test_3d_backend_option_rejects_unknown_choice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(
            build_arg_parser(),
            ["orbit.oem", "--3d-backend", "opengl"],
        )

    assert exc_info.value.code == 2
    assert "invalid choice: 'opengl'" in capsys.readouterr().err


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
                "ground-track",
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


def test_input_path_is_optional() -> None:
    args = parse_arguments(build_arg_parser(), [])

    assert args.input_oem is None


def test_cli_without_input_starts_with_file_loading_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ephem_toolkit.play_oem import app

    launched: dict[str, Any] = {}

    class FakePlayerApp:
        def __init__(self, *_args, **kwargs) -> None:
            launched.update(kwargs)

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([])

    assert launched["oem_loaded"] is False
    assert callable(launched["on_open_file"])
    assert launched["run"] is True


def test_cli_passes_configured_render_rate_and_path_to_player(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from ephem_toolkit.play_oem import app, saved_state

    config_path = tmp_path / "custom-play-oem.toml"
    config_path.write_text(
        "config_version = 1\n"
        "[playback]\n"
        "render_rate_fps = 17\n"
        "[interpolation]\n"
        "use_oem_metadata = false\n"
        'method = "chebyshev"\n'
        "degree = 8\n"
    )
    launched: dict[str, Any] = {}

    class FakePlayerApp:
        def __init__(self, *_args, **kwargs) -> None:
            launched.update(kwargs)

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)
    monkeypatch.setattr(saved_state, "load_saved_state", saved_state.SavedAppState)

    main(["--config", str(config_path)])

    assert launched["render_rate_fps"] == 17
    assert launched["tick_interval_ms"] == 59
    assert launched["config_path"] == str(config_path)
    assert launched["use_oem_interpolation"] is False
    assert launched["interpolation_method"] == "chebyshev"
    assert launched["interpolation_degree"] == 8
    assert launched["run"] is True


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


def test_cli_reports_playback_extra_when_wx_is_missing() -> None:
    script = """
import importlib.abc
import sys

class BlockWx(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "wx" or fullname.startswith("wx."):
            raise ModuleNotFoundError("No module named 'wx'", name=fullname)
        return None

sys.meta_path.insert(0, BlockWx())
from ephem_toolkit.play_oem import cli
raise SystemExit(cli([sys.argv[1]]))
"""
    oem_path = Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    result = subprocess.run(
        [sys.executable, "-c", script, str(oem_path)],
        check=False,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[3],
        text=True,
    )

    assert result.returncode == 1
    assert "wxPython is required to run" in result.stderr
    assert 'pip install "ephem-toolkit[playback]"' in result.stderr


def test_cli_loads_oem_and_launches_player(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )
    from ephem_toolkit.play_oem import app

    config_path = tmp_path / "play-oem.toml"
    config_path.write_text(
        "config_version = 1\n"
        "[display]\n"
        'plots = ["overview"]\n'
    )
    launched: dict[str, Any] = {}

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
            three_d_backend,
            tick_interval_ms,
            render_rate_fps,
            dashboard_context,
            metadata_details,
            on_open_file=None,
            oem_loaded=True,
            **_kwargs,
        ) -> None:
            launched["clock"] = clock
            launched["series"] = series
            launched["time_unit"] = time_unit
            launched["cursor"] = cursor
            launched["object_name"] = object_name
            launched["frame_context"] = frame_context
            launched["plots"] = plots
            launched["three_d_backend"] = three_d_backend
            launched["tick_interval_ms"] = tick_interval_ms
            launched["dashboard_context"] = dashboard_context
            launched["metadata_details"] = metadata_details

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([str(input_oem), "--config", str(config_path)])

    output = capsys.readouterr().out
    assert "Loaded 721 states" in output
    assert "Prepared orbit series with 721 samples using hours." in output
    assert launched["run"] is True
    assert launched["clock"].t_start < launched["clock"].t_end
    assert launched["series"].elapsed_time.size == 721
    assert isinstance(launched["cursor"], OemCursor)
    assert launched["cursor"].t_start == launched["clock"].t_start
    assert launched["cursor"].t_end == launched["clock"].t_end
    assert launched["object_name"] == "ISS"
    assert launched["frame_context"] == "EME2000 / Earth"
    assert launched["plots"] == ("trajectory-3d", "speed-altitude")
    assert launched["three_d_backend"] == "auto"
    assert launched["time_unit"].value == "hours"
    assert launched["clock"].rate == 1.0
    assert launched["clock"].t_now == launched["clock"].t_start
    assert not launched["clock"].playing
    assert not launched["clock"].loop
    assert launched["tick_interval_ms"] == 34


def test_cli_uses_playback_defaults_from_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )
    from ephem_toolkit.play_oem import app

    config_path = tmp_path / "play-oem.toml"
    config_path.write_text(
        "config_version = 1\n"
        "[playback]\n"
        "speed = 10\n"
        "reverse = true\n"
        "render_rate_fps = 20\n"
        "[display]\n"
        'three_d_backend = "matplotlib"\n'
    )
    launched: dict[str, Any] = {}

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
            three_d_backend,
            tick_interval_ms,
            render_rate_fps,
            dashboard_context,
            metadata_details,
            on_open_file=None,
            oem_loaded=True,
            **_kwargs,
        ) -> None:
            launched["clock"] = clock
            launched["three_d_backend"] = three_d_backend
            launched["tick_interval_ms"] = tick_interval_ms

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([str(input_oem), "--config", str(config_path)])

    clock = launched["clock"]
    assert launched["run"] is True
    assert clock.rate == -10.0
    assert clock.t_now == clock.t_end
    assert not clock.playing
    assert not clock.loop
    assert launched["three_d_backend"] == "matplotlib"
