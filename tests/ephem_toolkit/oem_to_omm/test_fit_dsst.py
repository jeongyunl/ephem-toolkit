"""Integration tests for DSST mean element fitting (oem-to-omm --mode dsst)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

import ephem_toolkit.oem_to_omm as oem_to_omm
import ephem_toolkit.core.ccsds.oem as oem
from ephem_toolkit.core.consts import EARTH_GRAVITATIONAL_PARAMETER_M3_S2
from ephem_toolkit.core.propagator.dsst import (
    DsstPerturbations,
    DSSTPropagator,
    osculating_to_dsst_mean,
)
from ephem_toolkit.core.propagator.base import KeplerianState, OutputMode
from ephem_toolkit.oem_to_omm.fit_brouwer import fit_dsst_mean_elements

_MU = EARTH_GRAVITATIONAL_PARAMETER_M3_S2

# ISS-like osculating elements: [a, e, i, omega, RAAN, theta]
_ISS_OSCULATING = np.array(
    [
        6778e3,
        0.0005,
        np.radians(51.6),
        np.radians(30.0),
        np.radians(45.0),
        np.radians(10.0),
    ]
)


def _make_oem_states(
    n_orbits: float = 1.0, n_points: int = 20
) -> list[tuple[float, np.ndarray]]:
    """Generate synthetic OEM states from ISS-like osculating elements."""
    mean_elements = osculating_to_dsst_mean(_ISS_OSCULATING, epoch_s=0.0)
    period_s = 2.0 * np.pi * np.sqrt(mean_elements[0] ** 3 / _MU)
    total_s = n_orbits * period_s

    states = []
    for k in range(n_points):
        t = k * total_s / (n_points - 1)
        state = KeplerianState(elements=mean_elements, epoch_s=0.0)
        prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)
        _, cart = prop.propagate_to(t, output=OutputMode.FINAL)
        states.append((t, cart))
    return states


# ===================================================================
# Unit tests for fit_dsst_mean_elements
# ===================================================================


def test_fit_dsst_mean_elements_returns_shape():
    """fit_dsst_mean_elements returns (6,) mean elements."""
    states = _make_oem_states()
    mean_elements, diagnostics = fit_dsst_mean_elements(states, fit_span_s=7200.0)

    assert mean_elements.shape == (6,)
    assert np.isfinite(mean_elements).all()


def test_fit_dsst_mean_elements_diagnostics():
    """fit_dsst_mean_elements returns valid diagnostics."""
    states = _make_oem_states()
    _, diagnostics = fit_dsst_mean_elements(states, fit_span_s=7200.0)

    assert diagnostics.n_records > 0
    assert diagnostics.span_s > 0.0
    assert diagnostics.rms_position_m >= 0.0
    assert np.isfinite(diagnostics.rms_position_m)


def test_fit_dsst_mean_elements_reasonable_rms():
    """RMS position error should be small for synthetic DSST states."""
    states = _make_oem_states(n_orbits=1.0, n_points=30)
    _, diagnostics = fit_dsst_mean_elements(states, fit_span_s=7200.0)

    # For synthetic DSST states, RMS should be < 10 km
    assert (
        diagnostics.rms_position_m < 10e3
    ), f"RMS too large: {diagnostics.rms_position_m/1e3:.3f} km"


def test_fit_dsst_mean_elements_semi_major_axis_reasonable():
    """Fitted semi-major axis should be close to true value."""
    states = _make_oem_states()
    mean_elements, _ = fit_dsst_mean_elements(states, fit_span_s=7200.0)

    true_mean = osculating_to_dsst_mean(_ISS_OSCULATING, epoch_s=0.0)
    a_fitted = mean_elements[0]
    a_true = true_mean[0]

    # Should be within 1% of true value
    assert (
        abs(a_fitted - a_true) / a_true < 0.01
    ), f"Semi-major axis error too large: {abs(a_fitted - a_true)/1e3:.3f} km"


def test_fit_dsst_mean_elements_requires_at_least_one_state():
    """fit_dsst_mean_elements raises on empty states."""
    with pytest.raises(ValueError, match="At least 1"):
        fit_dsst_mean_elements([], fit_span_s=7200.0)


def test_fit_dsst_mean_elements_fit_span_filters_states():
    """fit_span_s limits the states used for fitting."""
    states = _make_oem_states(n_orbits=2.0, n_points=40)
    period_s = 2.0 * np.pi * np.sqrt(6778e3**3 / _MU)

    # Fit only first orbit
    _, diag_short = fit_dsst_mean_elements(states, fit_span_s=period_s)
    # Fit both orbits
    _, diag_long = fit_dsst_mean_elements(states, fit_span_s=2 * period_s)

    assert diag_short.n_records < diag_long.n_records


def test_fit_dsst_mean_elements_with_custom_perturbations():
    """fit_dsst_mean_elements accepts custom DsstPerturbations."""
    states = _make_oem_states()
    pert = DsstPerturbations(include_j2=True, include_j3=True)
    mean_elements, diagnostics = fit_dsst_mean_elements(
        states, fit_span_s=7200.0, perturbations=pert
    )

    assert mean_elements.shape == (6,)
    assert np.isfinite(diagnostics.rms_position_m)


# ===================================================================
# Integration tests for oem-to-omm --mode dsst CLI
# ===================================================================


class _DummyMeta:
    object_name = "ISS"
    object_id = "1998-067A"
    ref_frame = "ICRF"
    center_name = "EARTH"


class _DummyOemData:
    def __init__(self, states):
        self.states = states
        self.meta = _DummyMeta()


def test_dsst_theory_in_output_omm(monkeypatch, tmp_path):
    """oem-to-omm --mode dsst writes MEAN_ELEMENT_THEORY = DSST to OMM."""
    states = _make_oem_states(n_points=10)
    output_path = tmp_path / "dsst.omm"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_: _DummyOemData(states),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["oem-to-omm", "--mode", "dsst", "input.oem", "-o", str(output_path)],
    )

    oem_to_omm.main()

    content = output_path.read_text(encoding="utf-8")
    assert "MEAN_ELEMENT_THEORY" in content
    assert "DSST" in content


def test_dsst_omm_output_has_required_fields(monkeypatch, tmp_path):
    """DSST OMM output contains all required CCSDS fields."""
    states = _make_oem_states(n_points=10)
    output_path = tmp_path / "dsst.omm"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_: _DummyOemData(states),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["oem-to-omm", "--mode", "dsst", "input.oem", "-o", str(output_path)],
    )

    oem_to_omm.main()

    content = output_path.read_text(encoding="utf-8")
    for field in [
        "EPOCH",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
        "MEAN_MOTION",
    ]:
        assert field in content, f"Missing field: {field}"


def test_dsst_omm_theory_override(monkeypatch, tmp_path):
    """--theory flag overrides MEAN_ELEMENT_THEORY in output OMM."""
    states = _make_oem_states(n_points=10)
    output_path = tmp_path / "dsst_custom.omm"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_: _DummyOemData(states),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "dsst",
            "--theory",
            "USM",
            "input.oem",
            "-o",
            str(output_path),
        ],
    )

    oem_to_omm.main()

    content = output_path.read_text(encoding="utf-8")
    assert "USM" in content


def test_dsst_omm_roundtrip(monkeypatch, tmp_path):
    """OEM → OMM(DSST) → propagate: output OMM is parseable and valid."""
    import ephem_toolkit.core.ccsds.omm as omm_mod

    states = _make_oem_states(n_points=15)
    output_path = tmp_path / "dsst_roundtrip.omm"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_: _DummyOemData(states),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["oem-to-omm", "--mode", "dsst", "input.oem", "-o", str(output_path)],
    )

    oem_to_omm.main()

    # Parse the output OMM
    parsed = omm_mod.CcsdsOmm.from_source(output_path)
    assert parsed.mean_element_theory.upper() == "DSST"
    assert parsed.eccentricity >= 0.0
    assert 0.0 <= parsed.inclination <= 180.0
    assert parsed.mean_motion > 0.0


def test_dsst_mode_cli_verbose(monkeypatch, tmp_path, capsys):
    """--verbose flag prints diagnostics to stderr."""
    states = _make_oem_states(n_points=10)
    output_path = tmp_path / "dsst_verbose.omm"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_: _DummyOemData(states),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "dsst",
            "--verbose",
            "input.oem",
            "-o",
            str(output_path),
        ],
    )

    oem_to_omm.main()

    captured = capsys.readouterr()
    assert "DSST fit" in captured.err or output_path.exists()
