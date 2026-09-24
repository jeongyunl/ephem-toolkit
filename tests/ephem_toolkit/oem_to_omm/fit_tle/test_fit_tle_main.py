"""Tests for oem_to_omm/fit_tle.py — TLE mean element fitting with SGP4-compatible propagation."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from ephem_toolkit.oem_to_omm import fit_tle_main as fit_tle


def test_fit_tle_module_imports() -> None:
    """Should successfully import the fit_tle module."""
    assert fit_tle is not None


def test_fit_tle_function_exists() -> None:
    """Should have fit_tle function."""
    assert hasattr(fit_tle, "fit_tle")
    assert callable(fit_tle.fit_tle)


def test_compute_tle_propagation_comparison_exists() -> None:
    """Should have compute_tle_propagation_comparison function."""
    assert hasattr(fit_tle, "compute_tle_propagation_comparison")
    assert callable(fit_tle.compute_tle_propagation_comparison)


def test_format_tle_output_exists() -> None:
    """Should have format_tle_output function."""
    assert hasattr(fit_tle, "format_tle_output")
    assert callable(fit_tle.format_tle_output)


def test_cartesian_to_tle_mean_elements_exists() -> None:
    """Should have cartesian_to_tle_mean_elements function."""
    assert hasattr(fit_tle, "cartesian_to_tle_mean_elements")
    assert callable(fit_tle.cartesian_to_tle_mean_elements)


def test_cartesian_to_tle_exists() -> None:
    """Should have cartesian_to_tle function."""
    assert hasattr(fit_tle, "cartesian_to_tle")
    assert callable(fit_tle.cartesian_to_tle)


def test_verify_tle_epoch_position_exists() -> None:
    """Should have verify_tle_epoch_position function."""
    assert hasattr(fit_tle, "verify_tle_epoch_position")
    assert callable(fit_tle.verify_tle_epoch_position)


def test_compute_tle_propagation_comparison_matches_nearby_states(monkeypatch) -> None:
    propagated_epochs = []

    class FakePropagator:
        def __init__(self, _tle):
            pass

        def propagate_to(self, epoch):
            propagated_epochs.append(epoch)
            return epoch, np.zeros(6)

    monkeypatch.setattr(fit_tle, "Sgp4Propagator", FakePropagator)
    tle_object = SimpleNamespace(
        mean_motion_rev_per_day=15.0,
        eccentricity=0.01,
        inclination_deg=51.0,
        arg_perigee_deg=20.0,
        raan_deg=30.0,
        mean_anomaly_deg=40.0,
    )
    states = [
        (100.0, np.array([1, 2, 3, 4, 5, 6], dtype=float)),
        (160.0, np.array([2, 3, 4, 5, 6, 7], dtype=float)),
        (220.0, np.array([3, 4, 5, 6, 7, 8], dtype=float)),
    ]

    comparison = fit_tle.compute_tle_propagation_comparison(
        tle_object, states, mu_m3_s2=1.0, fit_span_s=120.0, interval_s=60.0
    )

    assert [record.elapsed_s for record in comparison] == [0.0, 60.0, 120.0]
    assert propagated_epochs == [100.0, 160.0, 220.0]
    assert comparison[0].pos_err_km == pytest.approx(np.sqrt(14) / 1000)


def test_cartesian_to_tle_mean_elements_stops_when_epoch_position_matches(
    monkeypatch,
) -> None:
    from datetime import datetime

    state = np.array([7.0e6, 0.0, 0.0, 0.0, 7.5e3, 100.0])
    monkeypatch.setattr(
        fit_tle.time_utils, "tt_s_to_datetime", lambda _epoch: datetime(2025, 1, 1)
    )
    monkeypatch.setattr(fit_tle.tle, "datetime_to_tle_epoch", lambda _epoch: (25, 1.0))
    monkeypatch.setattr(fit_tle, "_sgp4_position", lambda *_args: state[:3].copy())

    elements = fit_tle.cartesian_to_tle_mean_elements(state, epoch_timestamp=0.0)

    assert elements.shape == (6,)
    assert elements[0] > 6.0e6
    assert 0.0 <= elements[1] < 1.0


def test_cartesian_to_tle_mean_elements_refines_with_line_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_elements = np.array([7.0e6, 0.01, 0.5, 0.1, 0.2, 0.3])
    initial_mean_anomaly = fit_tle._true_to_mean_anomaly(
        initial_elements[5], initial_elements[1]
    )
    monkeypatch.setattr(
        fit_tle,
        "_cartesian_to_osculating_keplerian",
        lambda *_args: initial_elements.copy(),
    )
    monkeypatch.setattr(
        fit_tle.time_utils, "tt_s_to_datetime", lambda _epoch: datetime(2026, 1, 1)
    )
    monkeypatch.setattr(fit_tle.tle, "datetime_to_tle_epoch", lambda _epoch: (26, 1.0))
    monkeypatch.setattr(
        fit_tle,
        "_sgp4_position",
        lambda *_args: (
            np.array([5.0, 0.0, 0.0])
            if abs(_args[5] - (initial_mean_anomaly + 0.1)) < 1e-10
            else np.zeros(3)
        ),
    )
    solve_calls = []

    def solve(_matrix, _vector):
        solve_calls.append(None)
        correction = np.zeros(6)
        if len(solve_calls) == 1:
            correction[5] = 0.1
        return correction

    monkeypatch.setattr(np.linalg, "solve", solve)

    elements = fit_tle.cartesian_to_tle_mean_elements(
        np.array([10.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
        epoch_timestamp=0.0,
        position_tolerance_m=0.1,
        max_iterations=2,
    )

    assert elements[5] == pytest.approx(initial_mean_anomaly + 0.1)
    assert len(solve_calls) == 2


def test_cartesian_to_tle_mean_elements_rejects_invalid_state_shape() -> None:
    with pytest.raises(ValueError, match=r"must have shape \(6,\)"):
        fit_tle.cartesian_to_tle_mean_elements(np.zeros(5), epoch_timestamp=0.0)


def test_cartesian_to_tle_builds_tle_and_verifies_epoch_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fit_tle,
        "cartesian_to_tle_mean_elements",
        lambda *_args, **_kwargs: np.array([7.0e6, 0.01, 0.5, 0.1, 0.2, 0.3]),
    )
    monkeypatch.setattr(
        fit_tle.convert_tle, "_parse_object_id", lambda _value: (98, 67, "A")
    )
    monkeypatch.setattr(
        fit_tle.time_utils, "tt_s_to_datetime", lambda _epoch: datetime(2026, 1, 1)
    )
    monkeypatch.setattr(fit_tle.tle, "datetime_to_tle_epoch", lambda _epoch: (26, 1.0))
    monkeypatch.setattr(
        fit_tle.convert_tle, "_float_to_tle_exponential", lambda _value: "00000+0"
    )
    monkeypatch.setattr(fit_tle.tle, "Tle", lambda **fields: SimpleNamespace(**fields))

    class FakePropagator:
        def __init__(self, _tle):
            pass

        def get_initial_epoch_s(self):
            return 0.0

        def propagate_to(self, epoch_s):
            return epoch_s, np.array([2.0, 3.0, 4.0, 0.0, 0.0, 0.0])

    monkeypatch.setattr(fit_tle, "Sgp4Propagator", FakePropagator)
    tle_object = fit_tle.cartesian_to_tle(
        np.ones(6), epoch_timestamp=0.0, object_name="TEST", object_id="1998-067A"
    )
    position_error, position_delta = fit_tle.verify_tle_epoch_position(
        tle_object, np.array([5.0, 3.0, 8.0])
    )

    assert tle_object.object_name == "TEST"
    assert tle_object.int_designator_year == 98
    assert tle_object.epoch_year == 26
    assert position_error == pytest.approx(5.0)
    np.testing.assert_array_equal(position_delta, [3.0, 0.0, 4.0])


def test_verify_tle_epoch_position_rejects_invalid_position_shape() -> None:
    with pytest.raises(ValueError, match=r"must have shape \(3,\)"):
        fit_tle.verify_tle_epoch_position(object(), np.zeros(2))


def test_compute_tle_propagation_comparison_skips_distant_samples(monkeypatch) -> None:
    class FakePropagator:
        def __init__(self, _tle):
            pass

        def propagate_to(self, epoch_s):
            return epoch_s, np.zeros(6)

    monkeypatch.setattr(fit_tle, "Sgp4Propagator", FakePropagator)
    states = [(0.0, np.ones(6)), (100.0, np.full(6, 2.0))]

    comparison = fit_tle.compute_tle_propagation_comparison(
        SimpleNamespace(
            mean_motion_rev_per_day=15.0,
            eccentricity=0.01,
            inclination_deg=51.0,
            arg_perigee_deg=20.0,
            raan_deg=30.0,
            mean_anomaly_deg=40.0,
        ),
        states,
        mu_m3_s2=1.0,
        fit_span_s=100.0,
        interval_s=40.0,
    )

    assert [record.elapsed_s for record in comparison] == [0.0, 100.0, 100.0]


@pytest.mark.parametrize(
    ("refinement_method", "use_state_match", "expected_refiner"),
    [
        ("none", False, None),
        ("keplerian", True, "keplerian"),
        ("cartesian", True, "cartesian"),
    ],
)
def test_fit_tle_routes_refinement_modes_and_builds_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    refinement_method: str,
    use_state_match: bool,
    expected_refiner: str | None,
) -> None:
    estimated = SimpleNamespace(
        state_match_iterations=2,
        state_match_position_error_m=3.0,
        state_match_velocity_error_m_s=0.25,
    )
    tle_object = object()
    estimation_calls = []
    refinement_calls = []
    built_args = []

    def estimate_fields(states, use_state_match):
        estimation_calls.append((states, use_state_match))
        return estimated

    monkeypatch.setattr(fit_tle.estimation, "estimate_tle_fields", estimate_fields)
    monkeypatch.setattr(
        fit_tle.estimation, "estimate_bstar_from_arc", lambda *_args: estimated
    )
    monkeypatch.setattr(
        fit_tle.refinement,
        "refine_estimated_fields_keplerian_match",
        lambda args, _estimated, _states: refinement_calls.append("keplerian")
        or _estimated,
    )
    monkeypatch.setattr(
        fit_tle.refinement,
        "refine_estimated_fields_to_match_epoch_state",
        lambda args, _estimated, _state: refinement_calls.append("cartesian")
        or _estimated,
    )
    monkeypatch.setattr(
        fit_tle.convert_tle, "_parse_object_id", lambda _value: (98, 67, "A")
    )

    def build_tle_data(args, _estimated):
        built_args.append(args)
        return tle_object

    monkeypatch.setattr(fit_tle.tle_builder, "build_tle_data", build_tle_data)

    class FakePropagator:
        def __init__(self, _tle):
            pass

        def get_initial_epoch_s(self):
            return 100.0

        def propagate_to(self, epoch_s):
            if epoch_s == 105.0:
                raise RuntimeError("sample unavailable")
            return epoch_s, np.zeros(6)

    monkeypatch.setattr(fit_tle, "Sgp4Propagator", FakePropagator)
    states = [
        (100.0, np.zeros(6)),
        (105.0, np.ones(6)),
        (115.0, np.ones(6)),
    ]

    result_tle, diagnostics = fit_tle.fit_tle(
        states,
        fit_span_s=10.0,
        refinement_method=refinement_method,
        object_id="1998-067A",
    )

    assert result_tle is tle_object
    assert estimation_calls == [(states, use_state_match)]
    assert refinement_calls == ([] if expected_refiner is None else [expected_refiner])
    assert built_args[0].int_designator_year == 98
    assert diagnostics.iterations == 2
    assert diagnostics.n_records == 2
    assert diagnostics.span_s == 15.0
    assert diagnostics.epoch_pos_delta_m == 3.0
    assert diagnostics.epoch_vel_delta_m_s == 0.25
    assert diagnostics.rms_position_m == 0.0


def test_format_tle_output_renders_comparison_and_summary() -> None:
    tle_object = SimpleNamespace(
        mean_motion_rev_per_day=15.5,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=120.0,
        arg_perigee_deg=45.0,
        mean_anomaly_deg=30.0,
        bstar="00000+0",
        mean_motion_first_derivative=0.0,
        mean_motion_second_derivative="00000+0",
    )
    diagnostics = SimpleNamespace(
        n_records=3,
        span_s=120.0,
        iterations=2,
        fit_method="tle_cartesian",
        rms_position_m=25.0,
        epoch_vel_delta_m_s=0.1,
    )
    comparison = [
        SimpleNamespace(elapsed_min=0.0, pos_err_km=0.01, vel_err_m_s=0.2),
        SimpleNamespace(elapsed_min=2.0, pos_err_km=0.02, vel_err_m_s=0.4),
    ]

    text = fit_tle.format_tle_output(
        datetime(2026, 5, 20, tzinfo=timezone.utc),
        tle_object,
        diagnostics,
        comparison,
    )

    assert "TLE mean elements (SGP4-compatible)" in text
    assert "epoch Δ|v0|" in text
    assert "Derived quantities" in text
    assert "Propagation comparison" in text
    assert "Position |Δr|:  min = 0.010000 km" in text
    assert "Velocity |Δv|" in text
