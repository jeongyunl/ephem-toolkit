"""Parity tests for play-oem OEM loading, filtering and derived series."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from threading import Event

import numpy as np
import pytest

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.core.time_utils import datetime_to_tt_s, iso8601_to_datetime
from ephem_toolkit.play_oem.data import filter_states_by_duration, read_oem_states
from ephem_toolkit.play_oem.oem_data_store import InterpolationPolicy, OemDataStore
from ephem_toolkit.play_oem.playback_data import (
    oem_declared_slider_bounds,
    oem_slider_bounds,
)
from ephem_toolkit.play_oem.series import OrbitSeries, compute_orbit_series
from ephem_toolkit.play_oem.streaming_oem import read_oem_into_store
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit as PlotTimeUnit,
    compute_orbit_series as compute_plot_orbit_series,
    filter_states_by_duration as filter_plot_states_by_duration,
    read_oem_states as read_plot_oem_states,
)
from tests.ephem_toolkit.play_oem.cursor_helpers import make_store_cursor


@pytest.fixture
def iss_oem_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"


def _load_store(source: Path) -> OemDataStore:
    store = OemDataStore()
    epoch = store.begin(OemDataStore.capacity_for_file(source))
    read_oem_into_store(
        source,
        store,
        batch_size=512,
        on_append=lambda _notice: None,
        cancel_event=Event(),
        expected_epoch=epoch,
    )
    return store


def test_read_oem_states_matches_plot_oem(iss_oem_path: Path) -> None:
    play_oem_data, play_timestamps, play_states = read_oem_states(iss_oem_path)
    plot_oem_data, plot_timestamps, plot_states = read_plot_oem_states(iss_oem_path)

    assert len(play_oem_data.states) == len(plot_oem_data.states)
    np.testing.assert_array_equal(play_timestamps, plot_timestamps)
    np.testing.assert_allclose(play_states, plot_states)


def test_oem_slider_bounds_include_metadata_times(
    iss_oem_path: Path,
) -> None:
    metadata = CcsdsOem.from_file(iss_oem_path).meta
    expected = (
        datetime_to_tt_s(iso8601_to_datetime(metadata.start_time)),
        datetime_to_tt_s(iso8601_to_datetime(metadata.stop_time)),
    )

    _, timestamps_s, _ = read_oem_states(iss_oem_path)
    assert oem_slider_bounds(
        metadata.start_time,
        metadata.stop_time,
        (timestamps_s[0], timestamps_s[-1]),
    ) == expected


def test_oem_declared_slider_bounds_require_a_valid_utc_interval() -> None:
    observed = (1.0, 2.0)

    assert oem_declared_slider_bounds(
        "2026-01-01T00:00:00", "2026-01-01T01:00:00"
    ) == (
        datetime_to_tt_s(iso8601_to_datetime("2026-01-01T00:00:00")),
        datetime_to_tt_s(iso8601_to_datetime("2026-01-01T01:00:00")),
    )
    assert oem_declared_slider_bounds("invalid", "2026-01-01T01:00:00") is None
    assert oem_declared_slider_bounds(
        "2026-01-01T01:00:00", "2026-01-01T00:00:00"
    ) is None
    assert oem_slider_bounds(
        "2026-01-01T01:00:00", "2026-01-01T00:00:00", observed
    ) == observed


def test_oem_slider_bounds_reject_non_utc_time_systems() -> None:
    with pytest.raises(ValueError, match="UTC only"):
        oem_declared_slider_bounds(
            "2026-01-01T00:00:00",
            "2026-01-01T01:00:00",
            time_system="TAI",
        )


def test_direct_store_load_exposes_oem_metadata_and_raw_views(iss_oem_path: Path) -> None:
    store = _load_store(iss_oem_path)
    snapshot = store.snapshot()
    metadata = dict(snapshot.meta)

    assert str(metadata["CENTER_NAME"]).strip().upper() == "EARTH"
    assert metadata["REF_FRAME"] == "EME2000"
    assert snapshot.sample_count > 0
    assert np.shares_memory(snapshot.positions_m, snapshot.raw)
    assert np.shares_memory(snapshot.velocities_m_s, snapshot.raw)
    assert np.shares_memory(store.sample_times.values, snapshot.raw)


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    (("ISS_2026-05-20.OEM", 5402), ("JPSS-1.oem", 21601)),
)
def test_real_fixture_store_kinematics_are_lazy_shared_and_numerically_equivalent(
    filename: str, expected_count: int
) -> None:
    source = Path(__file__).resolve().parents[2] / "data" / filename
    oem_data, timestamps_s, states_m = read_oem_states(source)
    store = _load_store(source)
    snapshot = store.snapshot()

    assert snapshot.sample_count == expected_count
    assert store._series_buffers == {}
    assert np.shares_memory(snapshot.positions_m, snapshot.raw)
    assert np.shares_memory(snapshot.velocities_m_s, snapshot.raw)

    query = store.series(
        snapshot,
        (float(timestamps_s[0]), float(timestamps_s[-1])),
        groups=("kinematics",),
        wait=True,
    )
    expected = compute_orbit_series(
        timestamps_s,
        list(states_m),
        TimeUnit.for_duration(float(timestamps_s[-1] - timestamps_s[0])),
        oem_data.segment_ids[: len(timestamps_s)],
    )
    groups = query.value["kinematics"]
    actual = np.concatenate([group.values for group in groups])

    assert set(store._series_buffers) == {"kinematics"}
    assert query.coverage.complete
    assert all(
        np.shares_memory(group.values, store._series_buffers["kinematics"])
        for group in groups
    )
    np.testing.assert_array_equal(actual[:, 0], timestamps_s)
    np.testing.assert_allclose(
        actual[:, 1], expected.velocity_magnitude_km_s * 1000.0
    )
    np.testing.assert_allclose(
        actual[:, 2], expected.geocentric_distance_km * 1000.0
    )
    np.testing.assert_allclose(actual[:, 3], expected.altitude_km * 1000.0)


def test_store_interpolation_policy_can_use_or_override_oem_metadata() -> None:
    jp_sat_oem_path = (
        Path(__file__).resolve().parents[2] / "data" / "JPSS-1_small.15m.oem"
    )
    oem_data, timestamps_s, states_m = read_oem_states(jp_sat_oem_path)
    assert oem_data.meta.interpolation == "Lagrange"
    assert oem_data.meta.interpolation_degree == 5

    store = _load_store(jp_sat_oem_path)
    store.set_interpolation(
        InterpolationPolicy(
            oem_data.meta.interpolation.lower(),
            oem_data.meta.interpolation_degree,
        )
    )
    metadata_interpolator = InterpolatorFactory.create(
        InterpolationSpec(
            InterpolationType(oem_data.meta.interpolation.lower()),
            degree=oem_data.meta.interpolation_degree,
        ),
        dimension=6,
        data=list(zip(timestamps_s, states_m)),
    )
    store_policy_state = store.state_at(
        store.snapshot(), (timestamps_s[0] + timestamps_s[1]) / 2.0
    ).state_m
    assert store_policy_state is not None
    midpoint = (timestamps_s[0] + timestamps_s[1]) / 2.0
    store.set_interpolation(InterpolationPolicy("hermite", 5))
    default_policy_state = store.state_at(store.snapshot(), midpoint).state_m
    assert default_policy_state is not None
    reference_interpolator = InterpolatorFactory.create(
        InterpolationSpec(InterpolationType.HERMITE, degree=5),
        dimension=6,
        is_cartesian_state=True,
        data=list(zip(timestamps_s, states_m)),
    )

    np.testing.assert_allclose(
        store_policy_state, metadata_interpolator.interpolate(midpoint)
    )
    np.testing.assert_allclose(
        default_policy_state, reference_interpolator.interpolate(midpoint)
    )


def test_duration_filter_matches_plot_oem(iss_oem_path: Path) -> None:
    _, timestamps_s, states_m = read_oem_states(iss_oem_path)

    play_timestamps, play_states = filter_states_by_duration(
        timestamps_s, states_m, 3600.0
    )
    plot_timestamps, plot_states = filter_plot_states_by_duration(
        timestamps_s, states_m, 3600.0
    )

    np.testing.assert_array_equal(play_timestamps, plot_timestamps)
    np.testing.assert_allclose(play_states, plot_states)
    assert play_timestamps[-1] <= timestamps_s[0] + 3600.0


def test_compute_orbit_series_matches_plot_oem(iss_oem_path: Path) -> None:
    _, timestamps_s, states_m = read_oem_states(iss_oem_path)
    timestamps_s, states_m = filter_states_by_duration(timestamps_s, states_m, 3600.0)

    play_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.HOURS)
    plot_series = compute_plot_orbit_series(timestamps_s, states_m, PlotTimeUnit.HOURS)

    for field in fields(play_series):
        if field.name in ("segment_ids", "rtn_segment_ids"):
            continue
        np.testing.assert_allclose(
            getattr(play_series, field.name),
            getattr(plot_series, field.name),
            atol=1e-12,
            err_msg=f"Mismatch in derived series field {field.name}",
        )


def test_oem_loader_preserves_multiple_segment_ids() -> None:
    from ephem_toolkit.core.ccsds.oem import CcsdsOem

    text = """CCSDS_OEM_VERS = 2.0
META_START
OBJECT_NAME = TEST
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:00:00 7000 0 0 0 7.5 0
2026-01-01T00:00:10 7000 1 0 0 7.5 0
META_START
OBJECT_NAME = TEST
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:10:00 7000 2 0 0 7.5 0
2026-01-01T00:10:10 7000 3 0 0 7.5 0
"""
    parsed = CcsdsOem.from_text(text)
    assert parsed.segment_ids == [0, 0, 1, 1]


def test_series_does_not_compute_cross_segment_deltas_or_rates() -> None:
    timestamps = [0.0, 10.0, 100.0, 110.0]
    states = [
        np.array([7_000_000.0, index * 1_000.0, 0.0, 0.0, 7_500.0, 0.0])
        for index in range(4)
    ]
    computed = compute_orbit_series(timestamps, states, TimeUnit.MINUTES, [0, 0, 1, 1])

    assert computed.segment_ids.tolist() == [0, 0, 1, 1]
    assert computed.rtn_segment_ids.tolist() == [0, -1, 1]
    assert np.isnan(computed.rtn_delta_km[1]).all()
    assert computed.angular_velocity_deg_s[2] == 0.0
    assert np.all(computed.euler_angle_rates_deg_s[2] == 0.0)


def test_vectorized_rtn_direction_matches_scalar_for_degenerate_states() -> None:
    states = np.asarray(
        [
            [7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            [7_000_000.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 7_500.0, 0.0],
            [7_000_000.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    expected = np.asarray(
        [
            OrbitSeries._compute_rtn_velocity_direction_vector(state)
            for state in states
        ]
    )

    actual = OrbitSeries._compute_rtn_velocity_direction_vectors(states)

    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-15)


def test_time_series_view_plots_oem_segments_as_separate_runs() -> None:
    from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView

    timestamps = [0.0, 10.0, 100.0, 110.0]
    states = [
        np.array([7_000_000.0, index * 1_000.0, 0.0, 0.0, 7_500.0, 0.0])
        for index in range(4)
    ]
    computed = compute_orbit_series(timestamps, states, TimeUnit.MINUTES, [0, 0, 1, 1])
    view = SpeedAltitudeView(timestamps[0])
    figure = view.build(computed, TimeUnit.MINUTES)
    try:
        for axes in figure.axes:
            series_lines = [
                line for line in axes.lines if line.get_label() != "_child0"
            ]
            assert len(series_lines) == 2
            assert [len(line.get_xdata()) for line in series_lines] == [2, 2]
    finally:
        view.close()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("m", TimeUnit.MINUTES),
        ("minutes", TimeUnit.MINUTES),
        ("H", TimeUnit.HOURS),
        ("hours", TimeUnit.HOURS),
    ],
)
def test_time_unit_parsing_matches_plot_oem(value: str, expected: TimeUnit) -> None:
    assert TimeUnit.from_string(value) is expected
    assert TimeUnit.from_string(value).value == PlotTimeUnit.from_string(value).value
