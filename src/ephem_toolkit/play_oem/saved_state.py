"""Application-maintained workspace state for ``play-oem``."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
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
from .views.registry import parse_plot_selection

STATE_FILENAME = "play-oem-state.toml"
STATE_VERSION = 3
FPS_MIN = 1
FPS_MAX = 30
DEFAULT_FPS = 30
MAX_RECENT_FILES = 15
DEFAULT_WINDOW_SIZE = (1100, 760)
MIN_STORED_WINDOW_DIMENSION = 320
MAX_STORED_WINDOW_DIMENSION = 10000


@dataclass
class SavedAppState:
    """Mutable application preferences stored outside the user config file."""

    width: int = DEFAULT_WINDOW_SIZE[0]
    height: int = DEFAULT_WINDOW_SIZE[1]
    maximized: bool = False
    recent_files: list[str] = field(default_factory=list)
    open_plots: list[str] | None = None
    minimum_elevation_deg: int = 10
    fps: int | None = None


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
        or version not in (1, 2, STATE_VERSION)
    ):
        return _state_error(
            state_path, f"state_version must be 1, 2, or {STATE_VERSION}"
        )

    window = document.get("window", {})
    if not isinstance(window, dict):
        return _state_error(state_path, "[window] must be a TOML table")
    if set(window) - {"width", "height", "maximized"}:
        unknown = sorted(set(window) - {"width", "height", "maximized"})[0]
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

    recent_section = document.get("recent_files", {})
    if not isinstance(recent_section, dict):
        return _state_error(state_path, "[recent_files] must be a TOML table")
    if set(recent_section) - {"paths"}:
        unknown = sorted(set(recent_section) - {"paths"})[0]
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
    if set(ground_track) - {"minimum_elevation_deg"}:
        unknown = sorted(set(ground_track) - {"minimum_elevation_deg"})[0]
        return _state_error(state_path, f"unknown key ground_track.{unknown!s}")
    minimum_elevation = ground_track.get("minimum_elevation_deg", 10)
    if not _is_int(minimum_elevation) or not 0 <= minimum_elevation <= 90:
        return _state_error(
            state_path,
            "ground_track.minimum_elevation_deg must be an integer from 0 through 90",
        )

    playback = document.get("playback", {})
    if not isinstance(playback, dict):
        return _state_error(state_path, "[playback] must be a TOML table")
    if set(playback) - {"fps"}:
        unknown = sorted(set(playback) - {"fps"})[0]
        return _state_error(state_path, f"unknown key playback.{unknown!s}")
    fps = playback.get("fps")
    if fps is not None and (not _is_int(fps) or not FPS_MIN <= fps <= FPS_MAX):
        return _state_error(
            state_path,
            f"playback.fps must be an integer from {FPS_MIN} through {FPS_MAX}",
        )

    return SavedAppState(
        width=width,
        height=height,
        maximized=maximized,
        recent_files=_unique_recent_paths(paths)[:MAX_RECENT_FILES],
        open_plots=list(parsed_open_plots),
        minimum_elevation_deg=minimum_elevation,
        fps=fps,
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


def _toml_string(value: str) -> str:
    # JSON basic strings are a compatible subset of TOML basic strings.
    return json.dumps(value, ensure_ascii=False)


def serialize_saved_state(state: SavedAppState) -> str:
    """Serialize the known state schema as deterministic TOML."""
    paths = _unique_recent_paths(state.recent_files)[:MAX_RECENT_FILES]
    plots = parse_plot_selection(",".join(state.open_plots)) if state.open_plots else ()
    encoded_paths = ",\n".join(f"    {_toml_string(path)}" for path in paths)
    path_body = f"\n{encoded_paths}\n" if paths else "\n"
    return (
        f"state_version = {STATE_VERSION}\n\n"
        "[window]\n"
        f"width = {int(state.width)}\n"
        f"height = {int(state.height)}\n"
        f"maximized = {str(bool(state.maximized)).lower()}\n\n"
        "[recent_files]\n"
        f"paths = [{path_body}]\n\n"
        "[workspace]\n"
        f"open_plots = [{', '.join(_toml_string(name) for name in plots)}]\n\n"
        "[ground_track]\n"
        f"minimum_elevation_deg = {int(state.minimum_elevation_deg)}\n\n"
        "[playback]\n"
        f"fps = {DEFAULT_FPS if state.fps is None else int(state.fps)}\n"
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
