"""Earth-fixed point lookups interpolate converted OEM samples."""

import numpy as np
import pytest

from ephem_toolkit.play_oem.cursor import CursorStatus
from ephem_toolkit.play_oem.oem_data_store import InterpolationPolicy, OemDataStore
from ephem_toolkit.play_oem import ground_track


@pytest.mark.parametrize(
    "method,degree",
    [("linear", None), ("hermite", 3), ("lagrange", 3), ("chebyshev", 3)],
)
def test_interpolates_converted_samples_and_reuses_them(monkeypatch, method, degree):
    store = OemDataStore()
    epoch = store.begin(8)
    reservation = store.reserve(8)
    times = np.arange(8, dtype=float)
    reservation.raw[:, 0] = times
    reservation.raw[:, 1:7] = np.column_stack(
        (7e6 + times**2, times, times, 2 * times, times, times)
    )
    reservation.segment_ids[:] = [0, 0, 0, 0, 1, 1, 1, 1]
    store.commit(reservation, 8)
    store.mark_complete(epoch, (), (("CENTER_NAME", "EARTH"), ("REF_FRAME", "J2000")))
    store.set_interpolation(InterpolationPolicy(method, degree))
    snapshot = store.snapshot()
    calls = []

    def convert(frame, t, state):
        calls.append(t)
        return state + np.array([t * t, 0, 0, 2 * t, 0, 0])

    monkeypatch.setattr(ground_track, "_convert_inertial_state_to_itrf", convert)
    converted = np.stack(
        [convert("J2000", t, row[1:7]) for t, row in zip(times, snapshot.raw)]
    )
    calls.clear()
    expected = store._state_interpolator.interpolate_view(
        times, converted, 1.5, snapshot.segment_ids
    )
    actual = store.earth_fixed_state_at(snapshot, 1.5)
    assert actual.status is CursorStatus.INTERPOLATED
    assert actual.state_m is not None
    assert expected is not None
    np.testing.assert_allclose(actual.state_m, expected)
    count = len(calls)
    store.earth_fixed_state_at(snapshot, 1.5)
    assert len(calls) == count
    exact = store.earth_fixed_state_at(snapshot, 1.0)
    assert exact.state_m is not None
    np.testing.assert_allclose(exact.state_m, converted[1])
    assert store.earth_fixed_state_at(snapshot, 3.5).status is CursorStatus.GAP
    assert store.earth_fixed_state_at(snapshot, -1).status is CursorStatus.OUT_OF_RANGE
    store.close()


def test_configured_target_is_used_for_fixed_input_and_inertial_states(monkeypatch):
    from enum import Enum
    from types import SimpleNamespace
    from ephem_toolkit import core

    class Frame(Enum):
        J2000 = "J2000"
        ITRF1993 = "ITRF1993"
        ITRF = "ITRF"

    calls = []

    def convert(source, target, epoch, state):
        calls.append((source, target, epoch))
        return state + 1

    monkeypatch.setattr(ground_track, "EARTH_FIXED_FRAME_NAME", "ITRF")
    monkeypatch.setattr(
        core,
        "frame_utils",
        SimpleNamespace(Frame=Frame, convert_frame=convert),
        raising=False,
    )
    state = np.array([7e6, 0, 0, 0, 7000, 0])
    inertial = ground_track.state_position_to_itrf_m(state, "J2000", 10.0)
    fixed = ground_track.state_position_to_itrf_m(state, "ITRF93", 20.0)
    np.testing.assert_array_equal(inertial, (state + 1)[:3])
    np.testing.assert_array_equal(fixed, (state + 1)[:3])
    assert calls == [
        (Frame.J2000, Frame.ITRF, 10.0),
        (Frame.ITRF1993, Frame.ITRF, 20.0),
    ]
