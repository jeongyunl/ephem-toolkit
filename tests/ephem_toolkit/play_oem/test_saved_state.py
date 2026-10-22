"""Tests for application-maintained play-oem preferences."""

from __future__ import annotations

import warnings

from ephem_toolkit.play_oem.saved_state import (
    SavedAppState,
    load_saved_state,
    serialize_saved_state,
)


def test_ground_track_minimum_elevation_round_trips(tmp_path) -> None:
    path = tmp_path / "play-oem-state.toml"
    path.write_text(serialize_saved_state(SavedAppState(minimum_elevation_deg=42)))

    state = load_saved_state(path)

    assert state.minimum_elevation_deg == 42


def test_playback_fps_round_trips(tmp_path) -> None:
    path = tmp_path / "play-oem-state.toml"
    path.write_text(serialize_saved_state(SavedAppState(fps=24)))

    assert load_saved_state(path).fps == 24


def test_state_version_one_migrates_with_ground_track_default(tmp_path) -> None:
    path = tmp_path / "play-oem-state.toml"
    path.write_text(
        "state_version = 1\n[window]\nwidth = 1100\nheight = 760\n"
        "maximized = false\n[recent_files]\npaths = []\n[workspace]\nopen_plots = []\n"
    )

    assert load_saved_state(path).minimum_elevation_deg == 10
    assert load_saved_state(path).fps is None


def test_invalid_ground_track_preference_falls_back(tmp_path) -> None:
    path = tmp_path / "play-oem-state.toml"
    path.write_text("state_version = 2\n[ground_track]\nminimum_elevation_deg = 91\n")

    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        state = load_saved_state(path)

    assert state.minimum_elevation_deg == 10
    assert observed


def test_invalid_saved_fps_falls_back(tmp_path) -> None:
    path = tmp_path / "play-oem-state.toml"
    path.write_text("state_version = 3\n[playback]\nfps = 0\n")

    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        state = load_saved_state(path)

    assert state.fps is None
    assert observed
