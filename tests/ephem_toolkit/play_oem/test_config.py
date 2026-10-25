"""Tests for user configuration loading and persistence."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem.config import (
    ConfigError,
    load_config,
    save_interpolation_settings,
    save_render_rate_fps,
)


def test_saving_render_rate_fps_preserves_other_config_and_comments(tmp_path) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text(
        "config_version = 1\n\n"
        "[playback]\n"
        "speed = 10.0\n"
        "reverse = true\n"
        "fps = 24 # preferred rate\n\n"
        "[display]\n"
        'three_d_backend = "matplotlib"\n'
        'plots = ["overview"]\n'
    )

    save_render_rate_fps(18, path)

    text = path.read_text()
    config = load_config(path)
    assert "render_rate_fps = 18 # preferred rate" in text
    assert config.speed == 10.0
    assert config.reverse
    assert config.render_rate_fps == 18
    assert config.three_d_backend == "matplotlib"
    assert config.plots == ("trajectory-3d", "speed-altitude")


def test_saving_render_rate_fps_creates_config_file_when_missing(tmp_path) -> None:
    path = tmp_path / "nested" / "play-oem.toml"

    save_render_rate_fps(24, path)

    assert load_config(path).render_rate_fps == 24


def test_saving_render_rate_fps_adds_playback_section_when_missing(tmp_path) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text('config_version = 1\n\n[display]\nplots = ["overview"]\n')

    save_render_rate_fps(12, path)

    assert load_config(path).render_rate_fps == 12
    assert path.read_text().endswith("[playback]\nrender_rate_fps = 12\n")


def test_saving_render_rate_fps_updates_inline_playback_table(tmp_path) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text("config_version = 1\nplayback = { speed = 2, fps = 24 }\n")

    save_render_rate_fps(18, path)

    assert path.read_text().endswith(
        "playback = { speed = 2, render_rate_fps = 18 }\n"
    )
    assert load_config(path).render_rate_fps == 18


def test_loading_legacy_fps_key_remains_supported(tmp_path) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text("config_version = 1\n[playback]\nfps = 17\n")

    assert load_config(path).render_rate_fps == 17


def test_interpolation_defaults_to_hermite_degree_five_without_oem_metadata(
    tmp_path,
) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text("config_version = 1\n")

    config = load_config(path)

    assert not config.use_oem_interpolation
    assert config.interpolation_method == "hermite"
    assert config.interpolation_degree == 5


def test_loading_interpolation_override_settings(tmp_path) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text(
        "config_version = 1\n"
        "[interpolation]\n"
        "use_oem_metadata = false\n"
        'method = "chebyshev"\n'
        "degree = 8\n"
    )

    config = load_config(path)

    assert not config.use_oem_interpolation
    assert config.interpolation_method == "chebyshev"
    assert config.interpolation_degree == 8


def test_saving_interpolation_settings_preserves_other_config_and_comments(
    tmp_path,
) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text(
        "config_version = 1\n"
        "[playback]\n"
        "speed = 3.0 # retain\n"
        "[interpolation]\n"
        "use_oem_metadata = true # metadata preference\n"
        'method = "hermite"\n'
        "degree = 5\n"
        "[display]\n"
        'three_d_backend = "auto"\n'
    )

    save_interpolation_settings(False, "lagrange", 7, path)

    config = load_config(path)
    text = path.read_text()
    assert config.speed == 3.0
    assert not config.use_oem_interpolation
    assert config.interpolation_method == "lagrange"
    assert config.interpolation_degree == 7
    assert "speed = 3.0 # retain" in text
    assert "use_oem_metadata = false # metadata preference" in text


def test_saving_interpolation_settings_creates_section_and_updates_inline_table(
    tmp_path,
) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text('config_version = 1\ninterpolation = { method = "hermite" }\n')

    save_interpolation_settings(False, "chebyshev", 9, path)

    assert load_config(path).interpolation_method == "chebyshev"
    assert load_config(path).interpolation_degree == 9
    assert "use_oem_metadata = false" in path.read_text()


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("use_oem_metadata", '"false"', "use_oem_metadata"),
        ("method", '"linear"', "interpolation.method"),
        ("degree", "-1", "interpolation.degree"),
        ("degree", "true", "interpolation.degree"),
    ],
)
def test_invalid_interpolation_settings_are_rejected(
    tmp_path, setting, value, message
) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text(f"config_version = 1\n[interpolation]\n{setting} = {value}\n")

    with pytest.raises(ConfigError, match=message):
        load_config(path)


@pytest.mark.parametrize(
    ("use_oem_metadata", "method", "degree"),
    [(True, "invalid", 5), (False, "hermite", -1), (1, "hermite", 5)],
)
def test_saving_invalid_interpolation_settings_is_rejected(
    tmp_path, use_oem_metadata, method, degree
) -> None:
    with pytest.raises(ConfigError, match="interpolation."):
        save_interpolation_settings(
            use_oem_metadata, method, degree, tmp_path / "play-oem.toml"
        )


def test_loading_both_render_rate_keys_is_rejected(tmp_path) -> None:
    path = tmp_path / "play-oem.toml"
    path.write_text(
        "config_version = 1\n[playback]\nfps = 17\nrender_rate_fps = 18\n"
    )

    with pytest.raises(ConfigError, match="set only playback.render_rate_fps"):
        load_config(path)


@pytest.mark.parametrize("render_rate_fps", [True, 0, 31])
def test_saving_invalid_render_rate_fps_is_rejected(tmp_path, render_rate_fps) -> None:
    with pytest.raises(ConfigError, match="playback.render_rate_fps"):
        save_render_rate_fps(render_rate_fps, tmp_path / "play-oem.toml")
