"""User configuration for ``play-oem``."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import tempfile
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
RENDER_RATE_FPS_MIN = 1
RENDER_RATE_FPS_MAX = 30


class ConfigError(ValueError):
    """Raised when a selected user configuration cannot be loaded or validated."""


@dataclass(frozen=True)
class PlayOemConfig:
    """Validated user defaults consumed by the CLI and GUI."""

    speed: float = 1.0
    reverse: bool = False
    render_rate_fps: int = RENDER_RATE_FPS_MAX
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
    _reject_unknown_keys(
        playback,
        {"speed", "reverse", "fps", "render_rate_fps"},
        "playback",
        config_path,
    )
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

    if "fps" in playback and "render_rate_fps" in playback:
        raise ConfigError(
            f"{config_path}: set only playback.render_rate_fps, not both "
            "playback.fps and playback.render_rate_fps"
        )
    render_rate_fps = playback.get(
        "render_rate_fps", playback.get("fps", RENDER_RATE_FPS_MAX)
    )
    if (
        isinstance(render_rate_fps, bool)
        or not isinstance(render_rate_fps, int)
        or not RENDER_RATE_FPS_MIN <= render_rate_fps <= RENDER_RATE_FPS_MAX
    ):
        raise ConfigError(
            f"{config_path}: playback.render_rate_fps must be between "
            f"{RENDER_RATE_FPS_MIN} and {RENDER_RATE_FPS_MAX}"
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
        render_rate_fps=render_rate_fps,
        three_d_backend=backend,
        plots=plots,
        plots_configured="plots" in display,
    )


def _with_render_rate_fps(document: str, render_rate_fps: int) -> str:
    newline = "\r\n" if "\r\n" in document else "\n"
    lines = document.splitlines()
    section_header = re.compile(r"^[ \t]*\[{1,2}[^\]]+\]{1,2}[ \t]*(?:#.*)?$")
    playback_header = re.compile(
        r"^[ \t]*\[[ \t]*(?:playback|\"playback\"|'playback')[ \t]*\][ \t]*(?:#.*)?$"
    )
    inline_playback = re.compile(
        r"^([ \t]*playback[ \t]*=[ \t]*\{)(.*)(\}[ \t]*(?:#.*)?)$"
    )
    inline_rate = re.compile(
        r"(^|,[ \t]*)(?:render_rate_fps|\"render_rate_fps\"|'render_rate_fps'|"
        r"fps|\"fps\"|'fps')[ \t]*=[ \t]*[^,]*?([ \t]*)(?=,|$)"
    )

    for index, line in enumerate(lines):
        inline_match = inline_playback.match(line)
        if inline_match is None:
            continue
        values = inline_match.group(2)
        rate_match = inline_rate.search(values)
        if rate_match is None:
            values = (
                f"{values.rstrip()}, render_rate_fps = {render_rate_fps}"
                if values.strip()
                else f"render_rate_fps = {render_rate_fps}"
            )
        else:
            replacement = (
                f"{rate_match.group(1)}render_rate_fps = {render_rate_fps}"
                f"{rate_match.group(2)}"
            )
            values = (
                values[: rate_match.start()]
                + replacement
                + values[rate_match.end() :]
            )
        lines[index] = (
            f"{inline_match.group(1)}{values}{inline_match.group(3)}"
        )
        updated = newline.join(lines)
        if document.endswith(("\n", "\r")):
            updated += newline
        return updated

    playback_start = next(
        (index for index, line in enumerate(lines) if playback_header.match(line)),
        None,
    )

    if playback_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(("[playback]", f"render_rate_fps = {render_rate_fps}"))
    else:
        playback_end = next(
            (
                index
                for index in range(playback_start + 1, len(lines))
                if section_header.match(lines[index])
            ),
            len(lines),
        )
        for index in range(playback_start + 1, playback_end):
            match = re.match(
                r"^([ \t]*)(?:render_rate_fps|\"render_rate_fps\"|'render_rate_fps'|"
                r"fps|\"fps\"|'fps')([ \t]*=[ \t]*)(.*?)([ \t]*(?:#.*)?)$",
                lines[index],
            )
            if match is not None:
                lines[index] = (
                    f"{match.group(1)}render_rate_fps{match.group(2)}"
                    f"{render_rate_fps}{match.group(4)}"
                )
                break
        else:
            lines.insert(playback_end, f"render_rate_fps = {render_rate_fps}")

    updated = newline.join(lines)
    if document.endswith(("\n", "\r")):
        updated += newline
    return updated


def save_render_rate_fps(
    render_rate_fps: int, path: str | Path | None = None
) -> Path:
    """Persist the selected render rate in the user configuration file."""
    if (
        isinstance(render_rate_fps, bool)
        or not isinstance(render_rate_fps, int)
        or not RENDER_RATE_FPS_MIN
        <= render_rate_fps
        <= RENDER_RATE_FPS_MAX
    ):
        raise ConfigError(
            "playback.render_rate_fps must be between "
            f"{RENDER_RATE_FPS_MIN} and {RENDER_RATE_FPS_MAX}"
        )

    config_path = default_config_path() if path is None else Path(path).expanduser()
    if config_path.exists():
        load_config(config_path)
        document = config_path.read_text(encoding="utf-8")
    else:
        document = f"config_version = {CONFIG_VERSION}\n"
    updated_document = _with_render_rate_fps(document, render_rate_fps)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=config_path.parent,
            prefix=f".{config_path.name}.",
            delete=False,
        ) as stream:
            stream.write(updated_document)
            temporary_path = stream.name
        os.replace(temporary_path, config_path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return config_path


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
