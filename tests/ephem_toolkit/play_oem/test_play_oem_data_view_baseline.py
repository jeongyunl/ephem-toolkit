"""Compare wx-migrated Matplotlib data_views with the recorded Tk-era baseline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.data import read_oem_states
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView
from ephem_toolkit.play_oem.views.state_components import (
    MAX_STATE_COMPONENT_DISPLAY_POINTS_PER_SEGMENT,
    StateComponentsView,
)
from ephem_toolkit.play_oem.views.trajectory3d import Trajectory3DView
from ephem_toolkit.play_oem.views.plotting import MAX_DISPLAY_POINTS_PER_SEGMENT
from tests.ephem_toolkit.play_oem.cursor_helpers import make_store_context, make_store_cursor

TEST_DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"
BASELINE_PATH = TEST_DATA_DIRECTORY / "play_oem_tk_baseline.json"
OEM_PATH = TEST_DATA_DIRECTORY / "ISS_2026-05-20.OEM"


def test_migrated_data_views_preserve_baseline_data_labels_and_cursor_locations() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    _, timestamps_s, states_m = read_oem_states(OEM_PATH)
    assert len(timestamps_s) == baseline["oem"]["sample_count"]
    time_unit = TimeUnit.from_string(baseline["oem"]["time_unit"])
    orbit_series = compute_orbit_series(timestamps_s, states_m, time_unit)
    _, cursor = make_store_cursor(timestamps_s, states_m)
    speed_view = SpeedAltitudeView(timestamps_s[0])
    components_view = StateComponentsView(
        timestamps_s[0],
        f"{baseline['oem']['reference_frame']} / {baseline['oem']['center']}",
    )
    trajectory_view = Trajectory3DView(
        cursor,
        baseline["oem"]["object_name"],
        f"{baseline['oem']['reference_frame']} / {baseline['oem']['center']}",
    )
    context = make_store_context(timestamps_s, states_m, time_unit)
    figures = [
        speed_view.build_from_store(context),
        components_view.build_from_store(context),
        trajectory_view.build_from_store(context),
    ]

    try:
        for figure in figures:
            FigureCanvasAgg(figure).draw()

        speed_labels = baseline["plot_labels"]["speed_altitude"]
        assert figures[0].axes[1].get_xlabel() == speed_labels["x"]
        assert [axes.get_ylabel() for axes in figures[0].axes] == speed_labels["y"]
        for axes, original in zip(
            figures[0].axes,
            (orbit_series.velocity_magnitude_km_s, orbit_series.altitude_km),
        ):
            assert axes.patches
            assert sum(
                len(patch.get_path().vertices)
                for patch in axes.patches
                if hasattr(patch, "get_path")
            ) <= MAX_DISPLAY_POINTS_PER_SEGMENT * 2

        component_labels = baseline["plot_labels"]["state_components"]
        assert [axes.get_ylabel() for axes in figures[1].axes] == component_labels["y"]
        assert figures[1].axes[4].get_xlabel() == component_labels["x"]
        assert figures[1].axes[5].get_xlabel() == component_labels["x"]
        assert figures[1]._suptitle is not None
        assert figures[1]._suptitle.get_text() == component_labels["figure_title"]
        for component_index, axes in enumerate(figures[1].axes):
            component_values = (
                orbit_series.position_km[:, component_index // 2]
                if component_index % 2 == 0
                else orbit_series.velocity_km_s[:, component_index // 2]
            )
            assert axes.patches
            assert sum(
                len(patch.get_path().vertices)
                for patch in axes.patches
                if hasattr(patch, "get_path")
            ) <= MAX_STATE_COMPONENT_DISPLAY_POINTS_PER_SEGMENT * 2

        trajectory_labels = baseline["plot_labels"]["trajectory_3d"]
        trajectory_axes = figures[2].axes[0]
        assert [
            trajectory_axes.get_xlabel(),
            trajectory_axes.get_ylabel(),
            trajectory_axes.get_zlabel(),
        ] == trajectory_labels["axes"]
        assert trajectory_axes.get_title() == trajectory_labels["plot_title"]
        assert figures[2]._suptitle is not None
        assert figures[2]._suptitle.get_text() == trajectory_labels["figure_title"]
        assert trajectory_view._orbit_artists

        for checkpoint in baseline["checkpoints"]:
            sample_index = checkpoint["sample_index"]
            elapsed_time = orbit_series.elapsed_time[sample_index]
            checkpoint_time_s = checkpoint["time_tt_seconds"]

            speed_view.update(checkpoint_time_s)
            components_view.update(checkpoint_time_s)
            trajectory_view.update(checkpoint_time_s)

            for artist in speed_view.cursor_artists:
                np.testing.assert_allclose(
                    artist.get_xdata(),
                    [elapsed_time, elapsed_time],
                )
            for artist in components_view.cursor_artists:
                np.testing.assert_allclose(
                    artist.get_xdata(),
                    [elapsed_time, elapsed_time],
                )
            np.testing.assert_allclose(
                trajectory_view._cursor_position_km,
                checkpoint["position_km"],
                rtol=1e-10,
            )
            np.testing.assert_allclose(
                [
                    orbit_series.velocity_magnitude_km_s[sample_index],
                    orbit_series.altitude_km[sample_index],
                ],
                [checkpoint["speed_km_s"], checkpoint["altitude_km"]],
                rtol=1e-10,
            )
            np.testing.assert_allclose(
                orbit_series.position_km[sample_index],
                checkpoint["position_km"],
                rtol=1e-10,
            )
            np.testing.assert_allclose(
                orbit_series.velocity_km_s[sample_index],
                checkpoint["velocity_km_s"],
                rtol=1e-10,
            )
    finally:
        speed_view.close()
        components_view.close()
        trajectory_view.close()
