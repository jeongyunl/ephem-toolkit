"""User configuration for ``play-oem``."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 and 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from .clock import PlaybackClock
from .views.registry import parse_plot_selection
from .views.trajectory3d.selection import THREE_D_BACKEND_CHOICES

CONFIG_DIRECTORY = "ephem-toolkit"
CONFIG_FILENAME = "play-oem.toml"
CONFIG_VERSION = 1
FPS_MIN = 1
FPS_MAX = 30


class ConfigError(ValueError):
    """Raised when a selected user configuration cannot be loaded or validated."""


@dataclass(frozen=True)
class PlayOemConfig:
    """Validated user defaults consumed by the CLI and GUI."""

    speed: float = 1.0
    reverse: bool = False
    fps: int = 30
    three_d_backend: str = "auto"
    plots: tuple[str, ...] = ("overview",)
    plots_configured: bool = False


def default_config_directory(
    *, environ: dict[str, str] | None = None, home: Path | None = None
) -> Path:
    """Return the XDG-style application config directory.

    A relative ``XDG_CONFIG_HOME`` is ignored, as required by the XDG base-directory
    convention. The same path policy is used on Linux and macOS.
    """
    environment = os.environ if environ is None else environ
    home_directory = Path.home() if home is None else home
    config_home = environment.get("XDG_CONFIG_HOME", "")
    if config_home:
        candidate = Path(config_home).expanduser()
        if candidate.is_absolute():
            return candidate / CONFIG_DIRECTORY
    return home_directory / ".config" / CONFIG_DIRECTORY


def default_config_path() -> Path:
    """Return the default user configuration path."""
    return default_config_directory() / CONFIG_FILENAME


def _table(value: Any, name: str, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: [{name}] must be a TOML table")
    return value


def _reject_unknown_keys(
    table: dict[str, Any], allowed: set[str], section: str, path: Path
) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        key = f"{section}.{unknown[0]}" if section else unknown[0]
        raise ConfigError(f"{path}: unknown configuration key {key!r}")


def _read_toml(path: Path, *, explicit: bool) -> dict[str, Any] | None:
    try:
        with path.open("rb") as stream:
            document = tomllib.load(stream)
    except FileNotFoundError as error:
        if explicit:
            raise ConfigError(f"configuration file does not exist: {path}") from error
        return None
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(
            f"could not read configuration file {path}: {error}"
        ) from error
    if not isinstance(document, dict):
        raise ConfigError(f"{path}: configuration root must be a TOML table")
    return document


def load_config(path: str | Path | None = None) -> PlayOemConfig:
    """Load and validate a user config, using defaults when the default file is absent."""
    explicit = path is not None
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    document = _read_toml(config_path, explicit=explicit)
    if document is None:
        return PlayOemConfig()

    _reject_unknown_keys(
        document, {"config_version", "playback", "display"}, "", config_path
    )
    version = document.get("config_version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != CONFIG_VERSION
    ):
        raise ConfigError(f"{config_path}: config_version must be {CONFIG_VERSION}")

    playback = _table(document.get("playback", {}), "playback", config_path)
    display = _table(document.get("display", {}), "display", config_path)
    _reject_unknown_keys(playback, {"speed", "reverse", "fps"}, "playback", config_path)
    _reject_unknown_keys(display, {"three_d_backend", "plots"}, "display", config_path)

    speed = playback.get("speed", 1.0)
    try:
        speed_value = float(speed)
    except (OverflowError, TypeError, ValueError):
        speed_value = math.nan
    if (
        not isinstance(speed, (int, float))
        or isinstance(speed, bool)
        or not (
            math.isfinite(speed_value) and 1.0 <= speed_value <= PlaybackClock.MAX_SPEED
        )
    ):
        raise ConfigError(
            f"{config_path}: playback.speed must be between 1 and "
            f"{PlaybackClock.MAX_SPEED}"
        )

    reverse = playback.get("reverse", False)
    if not isinstance(reverse, bool):
        raise ConfigError(f"{config_path}: playback.reverse must be true or false")

    fps = playback.get("fps", FPS_MAX)
    if (
        isinstance(fps, bool)
        or not isinstance(fps, int)
        or not FPS_MIN <= fps <= FPS_MAX
    ):
        raise ConfigError(
            f"{config_path}: playback.fps must be between {FPS_MIN} and {FPS_MAX}"
        )

    backend = display.get("three_d_backend", "auto")
    if not isinstance(backend, str) or backend not in THREE_D_BACKEND_CHOICES:
        choices = ", ".join(THREE_D_BACKEND_CHOICES)
        raise ConfigError(
            f"{config_path}: display.three_d_backend must be one of {choices}"
        )

    plots_value = display.get("plots", ["overview"])
    if not isinstance(plots_value, list) or any(
        not isinstance(item, str) for item in plots_value
    ):
        raise ConfigError(f"{config_path}: display.plots must be an array of strings")
    try:
        plots = parse_plot_selection(",".join(plots_value))
    except ValueError as error:
        raise ConfigError(f"{config_path}: invalid display.plots: {error}") from error

    return PlayOemConfig(
        speed=speed_value,
        reverse=reverse,
        fps=fps,
        three_d_backend=backend,
        plots=plots,
        plots_configured="plots" in display,
    )


def supplied_options(argv: list[str]) -> set[str]:
    """Return config-capable CLI destinations explicitly present in ``argv``."""
    aliases = {
        "--plots": "plots",
        "--3d-backend": "three_d_backend",
        "--config": "config",
    }
    provided: set[str] = set()
    for argument in argv:
        option = argument.split("=", 1)[0]
        if option in aliases:
            provided.add(aliases[option])
    return provided
