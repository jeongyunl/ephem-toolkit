"""Tests for the play-oem command-line scaffold."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from ephem_toolkit.play_oem import cli, main, saved_state
from ephem_toolkit.play_oem.cursor import StoreCursor
from ephem_toolkit.play_oem.play_oem_cli import (
    CONFIG_DIR_OPTION,
    CONFIG_FILE_OPTION,
    STATE_FILE_OPTION,
    THREE_D_BACKEND_OPTION,
    PLOTS_OPTION,
    build_arg_parser,
    parse_arguments,
)


@pytest.fixture(autouse=True)
def isolate_play_oem_app_toml_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "play-oem.toml").write_text("config_version = 1\n")
    (config_dir / "play-oem-state.toml").write_text(
        f"state_version = {saved_state.STATE_VERSION}\n"
    )
    original_main = main

    def isolated_main(argv=None):
        argument_list = list(sys.argv[1:] if argv is None else argv)
        if not any(
            argument.split("=", 1)[0] == CONFIG_DIR_OPTION
            for argument in argument_list
        ):
            argument_list.extend([CONFIG_DIR_OPTION, str(config_dir)])
        original_main(argument_list)

    monkeypatch.setitem(globals(), "main", isolated_main)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))


def test_help_shows_command_and_input(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    help_output = capsys.readouterr().out
    assert "play-oem" in help_output
    assert "<input_oem>" in help_output
    assert THREE_D_BACKEND_OPTION in help_output


def test_input_path_is_parsed() -> None:
    args = parse_arguments(build_arg_parser(), ["orbit.oem"])

    assert args.input_oem == "orbit.oem"
    assert args.plots == ("overview",)
    assert args.three_d_backend == "auto"
    assert args.config_file is None
    assert args.state_file is None
    assert args.config_dir is None
    assert args.provided_options == frozenset()


def test_config_and_state_paths_are_parsed() -> None:
    args = parse_arguments(
        build_arg_parser(),
        [
            "orbit.oem",
            CONFIG_FILE_OPTION,
            "custom.toml",
            STATE_FILE_OPTION,
            "custom-state.toml",
        ],
    )

    assert args.config_file == "custom.toml"
    assert args.state_file == "custom-state.toml"
    assert args.provided_options == frozenset({"config_file", "state_file"})


def test_config_dir_and_explicit_file_precedence_are_parsed() -> None:
    args = parse_arguments(
        build_arg_parser(),
        [
            "orbit.oem",
            CONFIG_DIR_OPTION,
            "/tmp/play-oem",
            CONFIG_FILE_OPTION,
            "/tmp/custom.toml",
            STATE_FILE_OPTION,
            "/tmp/custom-state.toml",
        ],
    )

    assert args.config_dir == "/tmp/play-oem"
    assert args.config_file == "/tmp/custom.toml"
    assert args.state_file == "/tmp/custom-state.toml"


def test_resolve_config_paths_uses_explicit_files_before_config_dir(tmp_path: Path) -> None:
    from ephem_toolkit.play_oem.config import resolve_config_paths

    config_dir = tmp_path / "toml"
    config_file = tmp_path / "custom.toml"
    state_file = tmp_path / "custom-state.toml"

    paths = resolve_config_paths(
        config_file=config_file,
        state_file=state_file,
        config_dir=config_dir,
    )

    assert paths.config_file == config_file
    assert paths.state_file == state_file


@pytest.mark.parametrize("backend", ("auto", "vtk", "matplotlib"))
def test_3d_backend_option_accepts_supported_choices(backend: str) -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", THREE_D_BACKEND_OPTION, backend],
    )

    assert args.three_d_backend == backend


def test_3d_backend_option_rejects_unknown_choice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(
            build_arg_parser(),
            ["orbit.oem", THREE_D_BACKEND_OPTION, "opengl"],
        )

    assert exc_info.value.code == 2
    assert "invalid choice: 'opengl'" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("overview, trajectory-3d", ("overview", "trajectory-3d")),
        ("state", ("state",)),
        ("motion", ("motion",)),
        ("all", ("all",)),
        ("access-overview", ("access-overview",)),
        ("pass-study", ("pass-study",)),
    ],
)
def test_plots_option_preserves_canonical_names_and_groups(
    selection: str, expected: tuple[str, ...]
) -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", PLOTS_OPTION, selection],
    )

    assert args.plots == expected


def test_plots_option_rejects_empty_selection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(
            build_arg_parser(),
            ["orbit.oem", PLOTS_OPTION, "overview,"],
        )

    assert exc_info.value.code == 2
    assert "at least one non-empty plot name is required" in capsys.readouterr().err


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
    assert launched["initial_file_path"] is None
    assert "on_open_file" not in launched
    assert launched["run"] is True


def test_cli_config_dir_resolves_both_toml_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from ephem_toolkit.play_oem import app, saved_state

    config_dir = tmp_path / "toml"
    config_dir.mkdir()
    (config_dir / "play-oem.toml").write_text("config_version = 1\n")
    (config_dir / "play-oem-state.toml").write_text(
        f"state_version = {saved_state.STATE_VERSION}\n"
    )
    launched: dict[str, Any] = {}

    class FakePlayerApp:
        def __init__(self, *_args, **kwargs) -> None:
            launched.update(kwargs)

        def run(self) -> None:
            pass

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([CONFIG_DIR_OPTION, str(config_dir)])

    assert launched["config_path"] == str(config_dir / "play-oem.toml")
    assert launched["state_path"] == str(config_dir / "play-oem-state.toml")


def test_cli_passes_config_and_state_paths_to_player(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from ephem_toolkit.play_oem import app, saved_state

    config_path = tmp_path / "custom-play-oem.toml"
    state_path = tmp_path / "custom-play-oem-state.toml"
    config_path.write_text("config_version = 1\n")
    state_path.write_text(f"state_version = {saved_state.STATE_VERSION}\n")
    loaded_state_paths: list[object] = []
    launched: dict[str, Any] = {}

    class FakePlayerApp:
        def __init__(self, *_args, **kwargs) -> None:
            launched.update(kwargs)

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    original_load_state = saved_state.load_saved_state

    def load_state(path=None):
        loaded_state_paths.append(path)
        return original_load_state(path)

    monkeypatch.setattr(saved_state, "load_saved_state", load_state)

    main(
        [
            CONFIG_FILE_OPTION,
            str(config_path),
            STATE_FILE_OPTION,
            str(state_path),
        ]
    )

    assert loaded_state_paths == [state_path]
    assert launched["config_path"] == str(config_path)
    assert launched["state_path"] == str(state_path)
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
        "[ground_stations]\n"
        "stations = [{ id = \"one\", name = \"North\", latitude_deg = 64.0, "
        "longitude_deg = -21.0, altitude_m = 45.0, minimum_elevation_deg = 12 }]\n"
    )
    launched: dict[str, Any] = {}

    class FakePlayerApp:
        def __init__(self, *_args, **kwargs) -> None:
            launched.update(kwargs)

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)
    monkeypatch.setattr(saved_state, "load_saved_state", saved_state.SavedAppState)

    main([CONFIG_FILE_OPTION, str(config_path)])

    assert launched["render_rate_fps"] == 17
    assert launched["tick_interval_ms"] == 59
    assert launched["config_path"] == str(config_path)
    assert launched["use_oem_interpolation"] is False
    assert launched["interpolation_method"] == "chebyshev"
    assert launched["interpolation_degree"] == 8
    assert len(launched["ground_stations"]) == 1
    assert launched["ground_stations"][0].name == "North"
    assert launched["run"] is True


def test_cli_migrates_legacy_stations_into_user_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from ephem_toolkit.play_oem import app, config, saved_state
    from ephem_toolkit.play_oem.ground_stations import GroundStation

    config_path = tmp_path / "play-oem.toml"
    config_path.write_text("config_version = 1\n")
    station = GroundStation("legacy", "Legacy site", 10.0, 20.0, 30.0)
    monkeypatch.setattr(
        saved_state,
        "load_saved_state",
        lambda _path=None: saved_state.SavedAppState(ground_stations=[station]),
    )
    launched: dict[str, Any] = {}

    class FakePlayerApp:
        def __init__(self, *_args, **kwargs) -> None:
            launched.update(kwargs)

        def run(self) -> None:
            pass

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([CONFIG_FILE_OPTION, str(config_path)])

    assert launched["ground_stations"] == [station]
    assert config.load_config(config_path).ground_stations == (station,)


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


def test_cli_reports_playback_extra_when_wx_is_missing(
    tmp_path: Path,
) -> None:
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
from ephem_toolkit.play_oem.play_oem_cli import CONFIG_DIR_OPTION
raise SystemExit(cli([sys.argv[1], CONFIG_DIR_OPTION, sys.argv[2]]))
"""
    oem_path = Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "play-oem.toml").write_text("config_version = 1\n")
    result = subprocess.run(
        [sys.executable, "-c", script, str(oem_path), str(config_dir)],
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
            **kwargs,
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
            launched["on_open_file"] = on_open_file
            launched["oem_loaded"] = oem_loaded
            launched.update(kwargs)

        def run(self) -> None:
            launched["run"] = True

    monkeypatch.setattr(app, "PlayerApp", FakePlayerApp)

    main([str(input_oem), CONFIG_FILE_OPTION, str(config_path)])

    output = capsys.readouterr().out
    assert output == ""
    assert launched["run"] is True
    assert launched["clock"].t_start == launched["clock"].t_end
    assert launched["series"].elapsed_time.size == 1
    assert isinstance(launched["cursor"], StoreCursor)
    assert launched["object_name"] == "No OEM loaded"
    assert launched["oem_loaded"] is False
    assert launched["on_open_file"] is None
    assert launched["initial_file_path"] == str(input_oem)
    assert launched["plots"] == ("overview",)
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

    main([str(input_oem), CONFIG_FILE_OPTION, str(config_path)])

    clock = launched["clock"]
    assert launched["run"] is True
    assert clock.rate == -10.0
    assert clock.t_now == clock.t_end
    assert not clock.playing
    assert not clock.loop
    assert launched["three_d_backend"] == "matplotlib"
