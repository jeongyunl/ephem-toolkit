"""User configuration for ``play-oem``."""

from __future__ import annotations

from dataclasses import dataclass
import json
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
from ephem_toolkit.core.interpolator.interpolation_spec import (
    DEFAULT_HERMITE_DEGREE,
    InterpolationType,
)
from .ground_stations import GroundStation, parse_ground_station_records
from .display_time import DISPLAY_TIME_ZONES, UTC_DISPLAY
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
    use_oem_interpolation: bool = False
    interpolation_method: str = InterpolationType.HERMITE.value
    interpolation_degree: int = DEFAULT_HERMITE_DEGREE
    display_time_zone: str = UTC_DISPLAY
    three_d_backend: str = "auto"
    plots: tuple[str, ...] = ("overview",)
    plots_configured: bool = False
    ground_stations: tuple[GroundStation, ...] = ()
    ground_stations_configured: bool = False


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


def _validate_interpolation_settings(
    use_oem_metadata: Any,
    method: Any,
    degree: Any,
    *,
    path: Path | None = None,
) -> tuple[bool, str, int]:
    prefix = f"{path}: " if path is not None else ""
    if not isinstance(use_oem_metadata, bool):
        raise ConfigError(
            f"{prefix}interpolation.use_oem_metadata must be true or false"
        )
    methods = tuple(item.value for item in InterpolationType)
    if not isinstance(method, str) or method not in methods:
        choices = ", ".join(methods)
        raise ConfigError(f"{prefix}interpolation.method must be one of {choices}")
    if isinstance(degree, bool) or not isinstance(degree, int) or degree < 0:
        raise ConfigError(
            f"{prefix}interpolation.degree must be a non-negative integer"
        )
    return use_oem_metadata, method, degree


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
        document,
        {
            "config_version",
            "playback",
            "display",
            "interpolation",
            "ground_stations",
        },
        "",
        config_path,
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
    interpolation = _table(
        document.get("interpolation", {}), "interpolation", config_path
    )
    ground_stations_section = _table(
        document.get("ground_stations", {}), "ground_stations", config_path
    )
    _reject_unknown_keys(
        playback,
        {"speed", "reverse", "fps", "render_rate_fps"},
        "playback",
        config_path,
    )
    _reject_unknown_keys(
        display, {"three_d_backend", "plots", "time_zone"}, "display", config_path
    )
    display_time_zone = display.get("time_zone", UTC_DISPLAY)
    if display_time_zone not in DISPLAY_TIME_ZONES:
        raise ConfigError(
            f"{config_path}: display.time_zone must be one of "
            f"{', '.join(DISPLAY_TIME_ZONES)}"
        )
    _reject_unknown_keys(
        interpolation,
        {"use_oem_metadata", "method", "degree"},
        "interpolation",
        config_path,
    )
    _reject_unknown_keys(
        ground_stations_section, {"stations"}, "ground_stations", config_path
    )
    try:
        ground_stations = parse_ground_station_records(
            ground_stations_section.get("stations", [])
        )
    except ValueError as error:
        raise ConfigError(f"{config_path}: {error}") from error

    use_oem_interpolation, interpolation_method, interpolation_degree = (
        _validate_interpolation_settings(
            interpolation.get("use_oem_metadata", False),
            interpolation.get("method", InterpolationType.HERMITE.value),
            interpolation.get("degree", DEFAULT_HERMITE_DEGREE),
            path=config_path,
        )
    )

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
        use_oem_interpolation=use_oem_interpolation,
        interpolation_method=interpolation_method,
        interpolation_degree=interpolation_degree,
        display_time_zone=display_time_zone,
        three_d_backend=backend,
        plots=plots,
        plots_configured="plots" in display,
        ground_stations=tuple(ground_stations),
        ground_stations_configured="ground_stations" in document,
    )


def _station_records_value(stations: tuple[GroundStation, ...]) -> str:
    records = []
    seen_ids: set[str] = set()
    for station in stations:
        if not isinstance(station, GroundStation):
            raise ConfigError("ground_stations must contain GroundStation records")
        if station.station_id in seen_ids:
            raise ConfigError(f"duplicate ground station id: {station.station_id!r}")
        seen_ids.add(station.station_id)
        records.append(
            "{ "
            f"id = {json.dumps(station.station_id, ensure_ascii=False)}, "
            f"name = {json.dumps(station.name, ensure_ascii=False)}, "
            f"latitude_deg = {station.latitude_deg!r}, "
            f"longitude_deg = {station.longitude_deg!r}, "
            f"altitude_m = {station.altitude_m!r}, "
            f"minimum_elevation_deg = {station.minimum_elevation_deg}"
            " }"
        )
    return "[" + ", ".join(records) + "]"


def _with_ground_stations(document: str, stations: tuple[GroundStation, ...]) -> str:
    newline = "\r\n" if "\r\n" in document else "\n"
    lines = document.splitlines()
    value = _station_records_value(stations)
    section_header = re.compile(r"^[ \t]*\[{1,2}[^\]]+\]{1,2}[ \t]*(?:#.*)?$")
    ground_stations_header = re.compile(
        r"^[ \t]*\[[ \t]*(?:ground_stations|\"ground_stations\"|"
        r"'ground_stations')[ \t]*\][ \t]*(?:#.*)?$"
    )
    inline_ground_stations = re.compile(
        r"^([ \t]*(?:ground_stations|\"ground_stations\"|'ground_stations')"
        r"[ \t]*=[ \t]*\{)(.*)(\}[ \t]*(?:#.*)?)$"
    )

    for index, line in enumerate(lines):
        inline_match = inline_ground_stations.match(line)
        if inline_match is not None:
            lines[index] = (
                f"{inline_match.group(1)}stations = {value}" f"{inline_match.group(3)}"
            )
            updated = newline.join(lines)
            return updated + newline if document.endswith(("\n", "\r")) else updated

    section_start = next(
        (
            index
            for index, line in enumerate(lines)
            if ground_stations_header.match(line)
        ),
        None,
    )
    if section_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(("[ground_stations]", f"stations = {value}"))
    else:
        section_end = next(
            (
                index
                for index in range(section_start + 1, len(lines))
                if section_header.match(lines[index])
            ),
            len(lines),
        )
        comments = [
            line
            for line in lines[section_start + 1 : section_end]
            if line.lstrip().startswith("#")
        ]
        lines[section_start + 1 : section_end] = [*comments, f"stations = {value}"]

    updated = newline.join(lines)
    return updated + newline if document.endswith(("\n", "\r")) else updated


def save_ground_stations(
    stations: tuple[GroundStation, ...] | list[GroundStation],
    path: str | Path | None = None,
) -> Path:
    """Persist station definitions in the selected user configuration file."""
    station_tuple = tuple(stations)
    _station_records_value(station_tuple)
    config_path = default_config_path() if path is None else Path(path).expanduser()
    if config_path.exists():
        load_config(config_path)
        document = config_path.read_text(encoding="utf-8")
    else:
        document = f"config_version = {CONFIG_VERSION}\n"
    updated_document = _with_ground_stations(document, station_tuple)

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
                values[: rate_match.start()] + replacement + values[rate_match.end() :]
            )
        lines[index] = f"{inline_match.group(1)}{values}{inline_match.group(3)}"
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


def save_render_rate_fps(render_rate_fps: int, path: str | Path | None = None) -> Path:
    """Persist the selected render rate in the user configuration file."""
    if (
        isinstance(render_rate_fps, bool)
        or not isinstance(render_rate_fps, int)
        or not RENDER_RATE_FPS_MIN <= render_rate_fps <= RENDER_RATE_FPS_MAX
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


def _with_interpolation_settings(
    document: str,
    use_oem_metadata: bool,
    method: str,
    degree: int,
) -> str:
    newline = "\r\n" if "\r\n" in document else "\n"
    lines = document.splitlines()
    values = {
        "use_oem_metadata": str(use_oem_metadata).lower(),
        "method": f'"{method}"',
        "degree": str(degree),
    }
    section_header = re.compile(r"^[ \t]*\[{1,2}[^\]]+\]{1,2}[ \t]*(?:#.*)?$")
    interpolation_header = re.compile(
        r"^[ \t]*\[[ \t]*(?:interpolation|\"interpolation\"|'interpolation')[ \t]*\][ \t]*(?:#.*)?$"
    )
    inline_interpolation = re.compile(
        r"^([ \t]*interpolation[ \t]*=[ \t]*\{)(.*)(\}[ \t]*(?:#.*)?)$"
    )

    for index, line in enumerate(lines):
        inline_match = inline_interpolation.match(line)
        if inline_match is None:
            continue
        contents = inline_match.group(2)
        for key, value in values.items():
            key_match = re.search(
                rf"(^[ \t]*|,[ \t]*)(?:{re.escape(key)}|\"{re.escape(key)}\"|"
                rf"'{re.escape(key)}')[ \t]*=[ \t]*[^,]*",
                contents,
            )
            if key_match is None:
                contents = (
                    f"{contents.rstrip()}, {key} = {value}"
                    if contents.strip()
                    else f"{key} = {value}"
                )
            else:
                contents = (
                    contents[: key_match.start()]
                    + f"{key_match.group(1)}{key} = {value}"
                    + contents[key_match.end() :]
                )
        lines[index] = f"{inline_match.group(1)}{contents}{inline_match.group(3)}"
        updated = newline.join(lines)
        if document.endswith(("\n", "\r")):
            updated += newline
        return updated

    interpolation_start = next(
        (index for index, line in enumerate(lines) if interpolation_header.match(line)),
        None,
    )
    if interpolation_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[interpolation]")
        lines.extend(f"{key} = {value}" for key, value in values.items())
    else:
        interpolation_end = next(
            (
                index
                for index in range(interpolation_start + 1, len(lines))
                if section_header.match(lines[index])
            ),
            len(lines),
        )
        for key, value in values.items():
            key_pattern = re.compile(
                rf"^([ \t]*)(?:{re.escape(key)}|\"{re.escape(key)}\"|"
                rf"'{re.escape(key)}')([ \t]*=[ \t]*)(.*?)([ \t]*(?:#.*)?)$"
            )
            for index in range(interpolation_start + 1, interpolation_end):
                match = key_pattern.match(lines[index])
                if match is None:
                    continue
                lines[index] = (
                    f"{match.group(1)}{key}{match.group(2)}{value}{match.group(4)}"
                )
                break
            else:
                lines.insert(interpolation_end, f"{key} = {value}")
                interpolation_end += 1

    updated = newline.join(lines)
    if document.endswith(("\n", "\r")):
        updated += newline
    return updated


def save_interpolation_settings(
    use_oem_metadata: bool,
    method: str,
    degree: int,
    path: str | Path | None = None,
) -> Path:
    """Persist interpolation settings in the user configuration file."""
    use_oem_metadata, method, degree = _validate_interpolation_settings(
        use_oem_metadata, method, degree
    )
    config_path = default_config_path() if path is None else Path(path).expanduser()
    if config_path.exists():
        load_config(config_path)
        document = config_path.read_text(encoding="utf-8")
    else:
        document = f"config_version = {CONFIG_VERSION}\n"
    updated_document = _with_interpolation_settings(
        document, use_oem_metadata, method, degree
    )

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


def save_display_time_zone(
    display_time_zone: str, path: str | Path | None = None
) -> Path:
    """Persist the display time zone in the user configuration file."""
    if display_time_zone not in DISPLAY_TIME_ZONES:
        raise ConfigError(
            f"display.time_zone must be one of {', '.join(DISPLAY_TIME_ZONES)}"
        )
    config_path = default_config_path() if path is None else Path(path).expanduser()
    if config_path.exists():
        load_config(config_path)
        document = config_path.read_text(encoding="utf-8")
    else:
        document = f"config_version = {CONFIG_VERSION}\n"
    lines = document.splitlines()
    newline = "\r\n" if "\r\n" in document else "\n"
    inline_display = re.compile(
        r"^([ \t]*display[ \t]*=[ \t]*\{)(.*)(\}[ \t]*(?:#.*)?)$"
    )
    inline_key = re.compile(
        r"(^|,[ \t]*)(?:time_zone|\"time_zone\"|'time_zone')[ \t]*=[ \t]*[^,]*"
    )
    for index, line in enumerate(lines):
        inline_match = inline_display.match(line)
        if inline_match is None:
            continue
        values = inline_match.group(2)
        key_match = inline_key.search(values)
        replacement = f'time_zone = "{display_time_zone}"'
        if key_match is None:
            values = f"{values.rstrip()}, {replacement}" if values.strip() else replacement
        else:
            values = (
                values[: key_match.start()]
                + f"{key_match.group(1)}{replacement}"
                + values[key_match.end() :]
            )
        lines[index] = f"{inline_match.group(1)}{values}{inline_match.group(3)}"
        break
    else:
        inline_match = None
    if inline_match is not None:
        updated = newline.join(lines)
        if document.endswith(("\n", "\r")):
            updated += newline
        _write_config_document(config_path, updated)
        return config_path
    header = re.compile(
        r"^[ \t]*\[[ \t]*(?:display|\"display\"|'display')[ \t]*\][ \t]*(?:#.*)?$"
    )
    section_header = re.compile(r"^[ \t]*\[{1,2}[^\]]+\]{1,2}[ \t]*(?:#.*)?$")
    start = next((i for i, line in enumerate(lines) if header.match(line)), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(("[display]", f'time_zone = "{display_time_zone}"'))
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if section_header.match(lines[i])),
            len(lines),
        )
        key = re.compile(
            r"^([ \t]*)(?:time_zone|\"time_zone\"|'time_zone')([ \t]*=[ \t]*)(.*?)([ \t]*(?:#.*)?)$"
        )
        for i in range(start + 1, end):
            match = key.match(lines[i])
            if match:
                lines[i] = (
                    f'{match.group(1)}time_zone{match.group(2)}'
                    f'"{display_time_zone}"{match.group(4)}'
                )
                break
        else:
            lines.insert(end, f'time_zone = "{display_time_zone}"')
    updated = newline.join(lines) + (newline if document.endswith(("\n", "\r")) else "")
    _write_config_document(config_path, updated)
    return config_path


def _write_config_document(config_path: Path, updated: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=config_path.parent,
            prefix=f".{config_path.name}.", delete=False,
        ) as stream:
            stream.write(updated)
            temporary_path = stream.name
        os.replace(temporary_path, config_path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)


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
