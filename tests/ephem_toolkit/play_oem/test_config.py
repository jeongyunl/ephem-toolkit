"""Tests for user configuration loading and persistence."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem.config import (
    ConfigError,
    load_config,
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
