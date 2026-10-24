"""Application-maintained workspace state for ``play-oem``."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import tempfile
import warnings
from typing import Any, cast

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 and 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from .config import default_config_directory
from .time_range import (
    PlotTimeRange,
    TimeRangeEndpoint,
    validate_plot_range,
)
from .views.registry import parse_plot_selection

STATE_FILENAME = "play-oem-state.toml"
STATE_VERSION = 6
MAX_RECENT_FILES = 15
MIN_STORED_WINDOW_DIMENSION = 320
MAX_STORED_WINDOW_DIMENSION = 10000
MIN_STORED_WINDOW_POSITION = -100000
MAX_STORED_WINDOW_POSITION = 100000

# Default values are kept together for easy review and adjustment.
DEFAULT_WINDOW_SIZE = (1100, 760)
DEFAULT_MINIMUM_ELEVATION_DEG = 10
DEFAULT_GROUND_TRACK_PROJECTION = "Robinson"
DEFAULT_GROUND_TRACK_BACKGROUND = "Shaded relief"
DEFAULT_GROUND_TRACK_CENTER_LONGITUDE_DEG = 0.0

GROUND_TRACK_PROJECTIONS = ("Robinson", "Equirectangular")
GROUND_TRACK_BACKGROUNDS = ("Shaded relief", "Satellite imagery", "Political map")
MINIMUM_ELEVATION_DEG_RANGE = (0, 90)
CENTER_LONGITUDE_DEG_RANGE = (-180.0, 180.0)
EMPTY_EXTENT = []
GROUND_TRACK_EXTENT_KEYS = ("xlim", "ylim")


@dataclass
class RecentFileSettings:
    """Settings associated with one recent OEM path."""

    playback_range: tuple[float, float] | None = None
    plot_range: PlotTimeRange | None = None


@dataclass
class SavedAppState:
    """Mutable application preferences stored outside the user config file."""

    width: int = DEFAULT_WINDOW_SIZE[0]
    height: int = DEFAULT_WINDOW_SIZE[1]
    maximized: bool = False
    position: tuple[int, int] | None = None
    recent_files: list[str] = field(default_factory=list)
    recent_file_settings: dict[str, RecentFileSettings] = field(default_factory=dict)
    open_plots: list[str] | None = None
    minimum_elevation_deg: int = DEFAULT_MINIMUM_ELEVATION_DEG
    ground_track_projection: str = DEFAULT_GROUND_TRACK_PROJECTION
    ground_track_background: str = DEFAULT_GROUND_TRACK_BACKGROUND
    ground_track_center_longitude_deg: float = DEFAULT_GROUND_TRACK_CENTER_LONGITUDE_DEG
    ground_track_xlim: tuple[float, float] | None = None
    ground_track_ylim: tuple[float, float] | None = None


def default_state_path() -> Path:
    """Return the XDG-style state file path beside ``play-oem.toml``."""
    return default_config_directory() / STATE_FILENAME


def _state_error(path: Path, error: object) -> SavedAppState:
    warnings.warn(
        f"Ignoring invalid play-oem state file {path}: {error}",
        RuntimeWarning,
        stacklevel=2,
    )
    return SavedAppState()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validated_playback_range(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("must contain exactly two timestamps")
    timestamps: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("timestamps must be finite numbers")
        try:
            timestamp = float(item)
        except OverflowError as error:
            raise ValueError("timestamps must be finite numbers") from error
        if not math.isfinite(timestamp):
            raise ValueError("timestamps must be finite numbers")
        timestamps.append(timestamp)
    start, end = timestamps
    if start > end:
        raise ValueError("start must not be after end")
    return start, end


def _validated_plot_range(value: Any) -> PlotTimeRange:
    if not isinstance(value, dict) or set(value) != {"enabled", "start", "end"}:
        raise ValueError("must contain enabled, start, and end")
    enabled = value["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")

    def endpoint(name: str) -> TimeRangeEndpoint:
        endpoint_value = value[name]
        if not isinstance(endpoint_value, dict) or set(endpoint_value) != {
            "mode",
            "value_s",
        }:
            raise ValueError(f"{name} must contain mode and value_s")
        mode = endpoint_value["mode"]
        if mode not in ("follow", "fixed", "offset"):
            raise ValueError(f"{name}.mode must be follow, fixed, or offset")
        value_s = endpoint_value["value_s"]
        if isinstance(value_s, bool) or not isinstance(value_s, (int, float)):
            raise ValueError(f"{name}.value_s must be a finite number")
        try:
            value_s = float(value_s)
        except OverflowError as error:
            raise ValueError(f"{name}.value_s must be a finite number") from error
        if not math.isfinite(value_s):
            raise ValueError(f"{name}.value_s must be a finite number")
        return TimeRangeEndpoint(mode, value_s)

    try:
        return validate_plot_range(
            PlotTimeRange(enabled, endpoint("start"), endpoint("end"))
        )
    except OverflowError as error:
        raise ValueError("endpoint values must be finite numbers") from error


def load_saved_state(path: str | Path | None = None) -> SavedAppState:
    """Read saved state; missing or invalid state never prevents application startup."""
    state_path = default_state_path() if path is None else Path(path).expanduser()
    try:
        with state_path.open("rb") as stream:
            document = tomllib.load(stream)
    except FileNotFoundError:
        return SavedAppState()
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        return _state_error(state_path, error)

    if not isinstance(document, dict):
        return _state_error(state_path, "the document root must be a TOML table")
    allowed_root = {
        "state_version",
        "window",
        "recent_files",
        "workspace",
        "ground_track",
        "playback",
    }
    unknown_root = set(document) - allowed_root
    if unknown_root:
        return _state_error(state_path, f"unknown key {sorted(unknown_root)[0]!r}")
    version = document.get("state_version")
    if (
        isinstance(version, bool)
        or not _is_int(version)
        or version not in (1, 2, 3, 4, 5, STATE_VERSION)
    ):
        return _state_error(
            state_path, f"state_version must be 1, 2, 3, 4, 5, or {STATE_VERSION}"
        )

    window = document.get("window", {})
    if not isinstance(window, dict):
        return _state_error(state_path, "[window] must be a TOML table")
    if set(window) - {"width", "height", "maximized", "position"}:
        unknown = sorted(set(window) - {"width", "height", "maximized", "position"})[0]
        return _state_error(state_path, f"unknown key window.{unknown!s}")
    width = window.get("width", DEFAULT_WINDOW_SIZE[0])
    height = window.get("height", DEFAULT_WINDOW_SIZE[1])
    maximized = window.get("maximized", False)
    if not _is_int(width) or not (
        MIN_STORED_WINDOW_DIMENSION <= width <= MAX_STORED_WINDOW_DIMENSION
    ):
        return _state_error(state_path, "window.width is outside the supported range")
    if not _is_int(height) or not (
        MIN_STORED_WINDOW_DIMENSION <= height <= MAX_STORED_WINDOW_DIMENSION
    ):
        return _state_error(state_path, "window.height is outside the supported range")
    if not isinstance(maximized, bool):
        return _state_error(state_path, "window.maximized must be true or false")
    position_value = window.get("position")
    position: tuple[int, int] | None = None
    if position_value is not None:
        if (
            not isinstance(position_value, list)
            or len(position_value) != 2
            or any(
                not _is_int(coordinate)
                or not MIN_STORED_WINDOW_POSITION
                <= coordinate
                <= MAX_STORED_WINDOW_POSITION
                for coordinate in position_value
            )
        ):
            return _state_error(
                state_path,
                "window.position must contain two supported integer coordinates",
            )
        position = (position_value[0], position_value[1])

    recent_section = document.get("recent_files", {})
    if not isinstance(recent_section, dict):
        return _state_error(state_path, "[recent_files] must be a TOML table")
    if set(recent_section) - {"paths", "settings"}:
        unknown = sorted(set(recent_section) - {"paths", "settings"})[0]
        return _state_error(state_path, f"unknown key recent_files.{unknown!s}")
    paths = recent_section.get("paths", [])
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        return _state_error(
            state_path, "recent_files.paths must be an array of strings"
        )
    if any(not Path(item).is_absolute() for item in paths):
        return _state_error(
            state_path, "recent_files.paths must contain absolute paths"
        )
    normalized_paths = set(_unique_recent_paths(paths)[:MAX_RECENT_FILES])
    settings_section = recent_section.get("settings", {})
    if not isinstance(settings_section, dict):
        return _state_error(state_path, "[recent_files.settings] must be a TOML table")
    recent_file_settings: dict[str, RecentFileSettings] = {}
    for file_path, settings in settings_section.items():
        if not Path(file_path).is_absolute():
            return _state_error(
                state_path, "recent_files.settings keys must be absolute paths"
            )
        normalized_path = normalize_recent_path(file_path)
        if normalized_path not in normalized_paths:
            continue
        if not isinstance(settings, dict):
            return _state_error(
                state_path,
                f"recent_files.settings[{file_path!r}] must be a TOML table",
            )
        if set(settings) - {"playback_range", "plot_range"}:
            unknown = sorted(set(settings) - {"playback_range", "plot_range"})[0]
            return _state_error(
                state_path,
                f"unknown key recent_files.settings[{file_path!r}].{unknown}",
            )
        playback_range = settings.get("playback_range")
        if playback_range is not None:
            try:
                parsed_range = _validated_playback_range(playback_range)
            except ValueError as error:
                return _state_error(
                    state_path,
                    f"invalid recent_files.settings[{file_path!r}].playback_range: "
                    f"{error}",
                )
        else:
            parsed_range = None
        plot_range = settings.get("plot_range")
        if plot_range is not None:
            try:
                parsed_plot_range = _validated_plot_range(plot_range)
            except ValueError as error:
                return _state_error(
                    state_path,
                    f"invalid recent_files.settings[{file_path!r}].plot_range: "
                    f"{error}",
                )
        else:
            parsed_plot_range = None
        recent_file_settings[normalized_path] = RecentFileSettings(
            parsed_range, parsed_plot_range
        )

    workspace = document.get("workspace", {})
    if not isinstance(workspace, dict):
        return _state_error(state_path, "[workspace] must be a TOML table")
    if set(workspace) - {"open_plots"}:
        unknown = sorted(set(workspace) - {"open_plots"})[0]
        return _state_error(state_path, f"unknown key workspace.{unknown!s}")
    open_plots = workspace.get("open_plots", [])
    if not isinstance(open_plots, list) or any(
        not isinstance(item, str) for item in open_plots
    ):
        return _state_error(
            state_path, "workspace.open_plots must be an array of strings"
        )
    try:
        parsed_open_plots = (
            parse_plot_selection(",".join(cast(list[str], open_plots)))
            if open_plots
            else ()
        )
    except ValueError as error:
        return _state_error(state_path, f"invalid workspace.open_plots: {error}")

    ground_track = document.get("ground_track", {})
    if not isinstance(ground_track, dict):
        return _state_error(state_path, "[ground_track] must be a TOML table")
    if set(ground_track) - {
        "minimum_elevation_deg",
        "projection",
        "background",
        "center_longitude_deg",
        "xlim",
        "ylim",
    }:
        unknown = sorted(
            set(ground_track)
            - {
                "minimum_elevation_deg",
                "projection",
                "background",
                "center_longitude_deg",
                "xlim",
                "ylim",
            }
        )[0]
        return _state_error(state_path, f"unknown key ground_track.{unknown!s}")
    minimum_elevation = ground_track.get("minimum_elevation_deg", 10)
    if not _is_int(minimum_elevation) or not 0 <= minimum_elevation <= 90:
        return _state_error(
            state_path,
            "ground_track.minimum_elevation_deg must be an integer from 0 through 90",
        )
    projection = ground_track.get("projection", "Robinson")
    background = ground_track.get("background", "Shaded relief")
    center = ground_track.get("center_longitude_deg", 0.0)
    if projection not in ("Robinson", "Equirectangular") or background not in (
        "Shaded relief",
        "Satellite imagery",
        "Political map",
    ):
        return _state_error(state_path, "invalid ground_track projection or background")
    if (
        isinstance(center, bool)
        or not isinstance(center, (int, float))
        or not -180 <= center <= 180
    ):
        return _state_error(
            state_path,
            "ground_track.center_longitude_deg must be from -180 through 180",
        )

    def extent(key: str) -> tuple[float, float] | None:
        value = ground_track.get(key)
        if value is None or value == []:
            return None
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) for v in value
            )
            or value[0] >= value[1]
        ):
            raise ValueError(f"ground_track.{key} must be an increasing pair")
        return (float(value[0]), float(value[1]))

    try:
        xlim, ylim = extent("xlim"), extent("ylim")
    except ValueError as error:
        return _state_error(state_path, error)

    # Older state files stored FPS here; the render rate now belongs to user config.
    playback = document.get("playback", {})
    if not isinstance(playback, dict):
        return _state_error(state_path, "[playback] must be a TOML table")
    if set(playback) - {"fps"}:
        unknown = sorted(set(playback) - {"fps"})[0]
        return _state_error(state_path, f"unknown key playback.{unknown!s}")

    return SavedAppState(
        width=width,
        height=height,
        maximized=maximized,
        position=position,
        recent_files=_unique_recent_paths(paths)[:MAX_RECENT_FILES],
        recent_file_settings=recent_file_settings,
        open_plots=list(parsed_open_plots),
        minimum_elevation_deg=minimum_elevation,
        ground_track_projection=projection,
        ground_track_background=background,
        ground_track_center_longitude_deg=float(center),
        ground_track_xlim=xlim,
        ground_track_ylim=ylim,
    )


def normalize_recent_path(path: str | Path) -> str:
    """Return an absolute, normalized OEM path without resolving symlinks."""
    return os.path.abspath(os.path.expanduser(os.fspath(path)))


def _unique_recent_paths(paths: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = normalize_recent_path(path)
        if normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return unique


def remember_recent_file(state: SavedAppState, path: str | Path) -> None:
    """Move a successfully opened OEM path to the top of the recent list."""
    normalized = normalize_recent_path(path)
    state.recent_files = [
        normalized,
        *(
            existing
            for existing in state.recent_files
            if normalize_recent_path(existing) != normalized
        ),
    ][:MAX_RECENT_FILES]
    retained_paths = set(state.recent_files)
    state.recent_file_settings = {
        normalize_recent_path(existing): settings
        for existing, settings in state.recent_file_settings.items()
        if normalize_recent_path(existing) in retained_paths
    }
    state.recent_file_settings.setdefault(normalized, RecentFileSettings())


def _toml_string(value: str) -> str:
    # JSON basic strings are a compatible subset of TOML basic strings.
    return json.dumps(value, ensure_ascii=False)


def serialize_saved_state(state: SavedAppState) -> str:
    """Serialize the known state schema as deterministic TOML."""
    paths = _unique_recent_paths(state.recent_files)[:MAX_RECENT_FILES]
    plots = parse_plot_selection(",".join(state.open_plots)) if state.open_plots else ()
    encoded_paths = ",\n".join(f"    {_toml_string(path)}" for path in paths)
    path_body = f"\n{encoded_paths}\n" if paths else "\n"
    encoded_settings = []
    for path in paths:
        settings = state.recent_file_settings.get(path)
        if settings is None:
            continue
        setting_values = []
        if settings.playback_range is not None:
            start, end = _validated_playback_range(settings.playback_range)
            setting_values.append(f"playback_range = [{start!r}, {end!r}]")
        if settings.plot_range is not None:
            plot_range = validate_plot_range(settings.plot_range)
            setting_values.append(
                "plot_range = { "
                f"enabled = {str(plot_range.enabled).lower()}, "
                f"start = {{ mode = {_toml_string(plot_range.start.mode)}, "
                f"value_s = {plot_range.start.value_s!r} }}, "
                f"end = {{ mode = {_toml_string(plot_range.end.mode)}, "
                f"value_s = {plot_range.end.value_s!r} }}"
                " }"
            )
        settings_body = (
            f"{{ {', '.join(setting_values)} }}" if setting_values else "{}"
        )
        encoded_settings.append(f"    {_toml_string(path)} = {settings_body}")
    settings_body = "\n".join(encoded_settings)
    settings_table = f"\n{settings_body}\n" if settings_body else "\n"
    position_line = (
        f"position = [{state.position[0]}, {state.position[1]}]\n"
        if state.position is not None
        else ""
    )
    return (
        f"state_version = {STATE_VERSION}\n\n"
        "[window]\n"
        f"width = {int(state.width)}\n"
        f"height = {int(state.height)}\n"
        f"maximized = {str(bool(state.maximized)).lower()}\n"
        f"{position_line}"
        "\n"
        "[recent_files]\n"
        f"paths = [{path_body}]\n\n"
        "[recent_files.settings]\n"
        f"{settings_table}\n"
        "[workspace]\n"
        f"open_plots = [{', '.join(_toml_string(name) for name in plots)}]\n\n"
        "[ground_track]\n"
        f"minimum_elevation_deg = {int(state.minimum_elevation_deg)}\n\n"
        f"projection = {_toml_string(state.ground_track_projection)}\n"
        f"background = {_toml_string(state.ground_track_background)}\n"
        f"center_longitude_deg = {state.ground_track_center_longitude_deg}\n"
        f"xlim = {list(state.ground_track_xlim) if state.ground_track_xlim else '[]'}\n"
        f"ylim = {list(state.ground_track_ylim) if state.ground_track_ylim else '[]'}\n"
    )


def save_saved_state(state: SavedAppState, path: str | Path | None = None) -> Path:
    """Write saved state atomically and return its destination path."""
    state_path = default_state_path() if path is None else Path(path).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=state_path.parent,
            prefix=f".{STATE_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = stream.name
            stream.write(serialize_saved_state(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, state_path)
    except OSError:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise
    return state_path
