"""Integration tests for DSST propagation via propagate-omm CLI."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.propagate_omm as propagate_omm_main
import ephem_toolkit.propagate_omm.propagation as propagation
from ephem_toolkit.core.consts import EARTH_GRAVITATIONAL_PARAMETER_M3_S2
from ephem_toolkit.core.propagator.dsst import (
    DSSTPropagator,
    osculating_to_dsst_mean,
)
from ephem_toolkit.core.propagator import KeplerianState, OutputMode
from ephem_toolkit.core.propagator.kepler import (
    cartesian_to_keplerian,
    keplerian_to_cartesian,
    KeplerPropagator,
)
import ephem_toolkit.core.ccsds.omm as omm_mod
import ephem_toolkit.core.tle as tle_mod
import ephem_toolkit.core.time_utils as time_utils

_MU = EARTH_GRAVITATIONAL_PARAMETER_M3_S2
_propagate_omm_main_globals = propagate_omm_main.main.__globals__

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


@pytest.mark.parametrize(
    ("reader_name", "message"),
    [
        ("read_tle_input", "Input not provided"),
        ("read_omm_input", "OMM input not provided"),
    ],
)
def test_input_readers_reject_interactive_stdin(monkeypatch, reader_name, message):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))

    with pytest.raises(ValueError, match=message):
        getattr(propagation, reader_name)("-")


@pytest.mark.parametrize(
    ("reader_name", "message"),
    [
        ("read_tle_input", "Empty stdin input"),
        ("read_omm_input", "Empty stdin input"),
    ],
)
def test_input_readers_reject_empty_stdin(monkeypatch, reader_name, message):
    monkeypatch.setattr(sys, "stdin", StringIO(" \n"))

    with pytest.raises(ValueError, match=message):
        getattr(propagation, reader_name)(None)


def _make_dsst_state(epoch_s: float = 0.0) -> KeplerianState:
    mean = osculating_to_dsst_mean(_ISS_OSCULATING, epoch_s)
    return KeplerianState(elements=mean, epoch_s=epoch_s)


def _make_dsst_omm(epoch_s: float = 0.0, theory: str = "DSST") -> omm_mod.CcsdsOmm:
    """Create a minimal DSST OMM from ISS-like elements."""
    from ephem_toolkit.core.propagator.kepler import semi_major_axis_to_mean_motion

    mean = osculating_to_dsst_mean(_ISS_OSCULATING, epoch_s)
    epoch_dt = time_utils.tt_s_to_datetime(epoch_s)

    return omm_mod.CcsdsOmm(
        version=3.0,
        creation_date="2024-01-01T00:00:00.000",
        originator="test",
        object_name="ISS",
        object_id="1998-067A",
        center_name="EARTH",
        ref_frame="J2000",
        time_system="UTC",
        mean_element_theory=theory,
        epoch=time_utils.datetime_to_iso8601(epoch_dt, fractional_second_places=6),
        mean_motion=semi_major_axis_to_mean_motion(mean[0]),
        eccentricity=float(mean[1]),
        inclination=float(np.degrees(mean[2])),
        arg_of_pericenter=float(np.degrees(mean[3])),
        ra_of_asc_node=float(np.degrees(mean[4])),
        mean_anomaly=float(np.degrees(mean[5])),
    )


# ===================================================================
# Unit tests for propagate_omm_dsst function
# ===================================================================


def test_propagate_omm_dsst_produces_states(tmp_path):
    """propagate_omm_dsst writes OEM with state vectors."""
    omm_data = _make_dsst_omm()
    start = time_utils.tt_s_to_datetime(0.0)
    stop = time_utils.tt_s_to_datetime(3600.0)
    output_path = str(tmp_path / "dsst.oem")

    propagate_omm_main.propagate_omm_dsst(
        omm_data=omm_data,
        start_time=start,
        stop_time=stop,
        step_s=600.0,
        data_only=False,
        output_path=output_path,
    )

    content = Path(output_path).read_text()
    assert "CCSDS_OEM_VERS" in content
    assert len(content.strip().splitlines()) > 5


def test_propagate_omm_dsst_state_count(tmp_path):
    """propagate_omm_dsst produces correct number of state lines."""
    omm_data = _make_dsst_omm()
    start = time_utils.tt_s_to_datetime(0.0)
    stop = time_utils.tt_s_to_datetime(3600.0)
    output_path = str(tmp_path / "dsst.oem")

    propagate_omm_main.propagate_omm_dsst(
        omm_data=omm_data,
        start_time=start,
        stop_time=stop,
        step_s=600.0,
        data_only=True,
        output_path=output_path,
    )

    lines = [l for l in Path(output_path).read_text().strip().splitlines() if l.strip()]
    # 0, 600, 1200, 1800, 2400, 3000, 3600 = 7 states
    assert len(lines) == 7


def test_propagate_omm_dsst_matches_manual_propagation():
    """propagate_omm_dsst output matches manual DSSTPropagator at t=3600s."""
    omm_data = _make_dsst_omm(epoch_s=0.0)
    start = time_utils.tt_s_to_datetime(0.0)
    stop = time_utils.tt_s_to_datetime(3600.0)

    # Capture stdout
    import io as _io

    old_stdout = sys.stdout
    sys.stdout = buf = _io.StringIO()
    propagate_omm_main.propagate_omm_dsst(
        omm_data=omm_data,
        start_time=start,
        stop_time=stop,
        step_s=3600.0,
        data_only=True,
        output_path="-",
    )
    sys.stdout = old_stdout
    lines = [l for l in buf.getvalue().strip().splitlines() if l.strip()]

    # Parse last state line
    parts = lines[-1].split()
    pos_oem = (
        np.array([float(parts[1]), float(parts[2]), float(parts[3])]) * 1e3
    )  # km→m

    # Manual propagation
    state = _make_dsst_state(epoch_s=0.0)
    prop = DSSTPropagator(initial_state=state)
    _, cart = prop.propagate_to(3600.0, output=OutputMode.FINAL)

    np.testing.assert_allclose(pos_oem, cart[:3], rtol=1e-6)


def test_propagate_omm_dsst_invalid_time_window():
    """propagate_omm_dsst raises ValueError when stop < start."""
    omm_data = _make_dsst_omm()
    start = time_utils.tt_s_to_datetime(3600.0)
    stop = time_utils.tt_s_to_datetime(0.0)

    with pytest.raises(ValueError, match="stop epoch must be >= start"):
        propagate_omm_main.propagate_omm_dsst(
            omm_data=omm_data,
            start_time=start,
            stop_time=stop,
            step_s=60.0,
            data_only=True,
            output_path="-",
        )


def test_propagate_omm_dsst_with_spacecraft_parameters(tmp_path):
    """propagate_omm_dsst configures drag from OMM spacecraft parameters."""
    omm_data = _make_dsst_omm()
    omm_data.spacecraft_parameters = omm_mod.OmmSpacecraftParameters(
        mass=420000.0,
        drag_area=2500.0,
        drag_coeff=2.2,
    )
    start = time_utils.tt_s_to_datetime(0.0)
    stop = time_utils.tt_s_to_datetime(3600.0)
    output_path = str(tmp_path / "dsst_drag.oem")

    propagate_omm_main.propagate_omm_dsst(
        omm_data=omm_data,
        start_time=start,
        stop_time=stop,
        step_s=600.0,
        data_only=True,
        output_path=output_path,
    )

    lines = [l for l in Path(output_path).read_text().strip().splitlines() if l.strip()]
    assert len(lines) == 7


# ===================================================================
# Integration tests: DSST vs Kepler comparison
# ===================================================================


def test_dsst_vs_kepler_raan_drift():
    """DSST propagation shows RAAN drift vs Kepler (J2 effect)."""
    state = _make_dsst_state(epoch_s=0.0)
    period_s = 2.0 * np.pi * np.sqrt(state.elements[0] ** 3 / _MU)

    # DSST propagation
    dsst_prop = DSSTPropagator(initial_state=state)
    _, dsst_cart = dsst_prop.propagate_to(period_s, output=OutputMode.FINAL)
    dsst_kep = cartesian_to_keplerian(dsst_cart, _MU)

    # Kepler propagation (no J2)
    kepler_state = KeplerianState(
        elements=keplerian_to_cartesian(_ISS_OSCULATING, _MU),
        epoch_s=0.0,
    )
    # Use osculating elements directly for Kepler
    osc_elements = _ISS_OSCULATING.copy()
    from ephem_toolkit.core.propagator.kepler import (
        true_to_mean_anomaly,
    )

    kepler_mean = osc_elements.copy()
    kepler_mean[5] = true_to_mean_anomaly(osc_elements[5], osc_elements[1])
    kepler_state2 = KeplerianState(elements=kepler_mean, epoch_s=0.0)
    kepler_prop = KeplerPropagator(initial_state=kepler_state2)
    _, kepler_cart = kepler_prop.propagate_to(period_s, output=OutputMode.FINAL)
    kepler_kep = cartesian_to_keplerian(kepler_cart, _MU)

    # DSST RAAN should differ from Kepler RAAN (J2 causes nodal regression)
    raan_diff = abs(dsst_kep[4] - kepler_kep[4])
    if raan_diff > np.pi:
        raan_diff = 2 * np.pi - raan_diff
    assert raan_diff > 1e-6, "DSST should show RAAN drift vs Kepler"


def test_dsst_propagation_finite_states():
    """DSST propagation produces finite Cartesian states over 1 day."""
    state = _make_dsst_state(epoch_s=0.0)
    prop = DSSTPropagator(initial_state=state)

    for t in np.linspace(0, 86400, 20):
        _, cart = prop.propagate_to(float(t), output=OutputMode.FINAL)
        assert np.isfinite(cart).all(), f"Non-finite state at t={t:.0f}s"


# ===================================================================
# CLI dispatch integration test
# ===================================================================


def test_main_dispatches_dsst_for_dsst_theory(monkeypatch, tmp_path):
    """main() dispatches to propagate_omm_dsst when MEAN_ELEMENT_THEORY=DSST."""
    omm_data = _make_dsst_omm()
    output_path = tmp_path / "dsst_cli.oem"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        omm_mod.CcsdsOmm,
        "from_source",
        lambda *_: omm_data,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "propagate-omm",
            "input.omm",
            "--stop",
            "1h",
            "--step",
            "600s",
            "-o",
            str(output_path),
        ],
    )

    propagate_omm_main.main()

    assert output_path.exists()
    content = output_path.read_text()
    assert len(content.strip()) > 0
    assert (
        "EPHEMERIS_PROVENANCE: source=OMM/DSST; transformation=propagation; "
        "target_model=DSST" in content
    )


def test_main_labels_sgp4_omm_output_as_omm_source(tmp_path: Path) -> None:
    """An SGP4-compatible OMM retains OMM source provenance in its OEM."""
    source = Path(__file__).parents[2] / "data/ISS-ZARYA_1998-067A.omm"
    output_path = tmp_path / "sgp4-omm.oem"

    assert (
        propagate_omm_main.main(
            [
                str(source),
                "--duration",
                "15m",
                "--step",
                "15m",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    text = output_path.read_text(encoding="utf-8")
    assert (
        "EPHEMERIS_PROVENANCE: source=OMM; transformation=propagation; target_model=SGP4"
        in text
    )


@pytest.mark.parametrize("theory", ["KEPLER", "BROUWER", "BROUWER-LYDDANE"])
def test_main_dispatches_kepler_for_non_dsst_theory(monkeypatch, tmp_path, theory):
    """main() uses the documented Kepler fallback for non-DSST theories."""
    omm_data = _make_dsst_omm(theory=theory)
    output_path = tmp_path / "kepler_cli.oem"

    monkeypatch.setattr(Path, "exists", lambda *_: True)
    monkeypatch.setattr(
        omm_mod.CcsdsOmm,
        "from_source",
        lambda *_: omm_data,
    )

    dispatched_to = []

    original_kepler = propagate_omm_main.propagate_omm_kepler

    def mock_kepler(*args, **kwargs):
        dispatched_to.append("kepler")
        return original_kepler(*args, **kwargs)

    monkeypatch.setitem(
        _propagate_omm_main_globals, "propagate_omm_kepler", mock_kepler
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "propagate-omm",
            "input.omm",
            "--stop",
            "1h",
            "--step",
            "600s",
            "-o",
            str(output_path),
        ],
    )

    propagate_omm_main.main()

    assert "kepler" in dispatched_to
    assert (
        f"EPHEMERIS_PROVENANCE: source=OMM/{theory}; "
        "transformation=propagation (fallback); target_model=two-body-kepler"
        in output_path.read_text()
    )


@pytest.mark.parametrize(
    ("is_tle", "reader_name", "message"),
    [
        (True, "read_tle_input", "TLE input did not produce TLE data"),
        (False, "read_omm_input", "OMM input did not produce OMM data"),
    ],
)
def test_main_rejects_missing_input_data(monkeypatch, is_tle, reader_name, message):
    args = SimpleNamespace(
        is_tle=is_tle,
        input_file="input",
        duration_s=60.0,
        start=None,
        stop=None,
        step=10.0,
        data_only=False,
        output_oem="-",
    )
    monkeypatch.setitem(_propagate_omm_main_globals, "parse_arguments", lambda *_: args)
    monkeypatch.setitem(_propagate_omm_main_globals, reader_name, lambda *_: None)

    with pytest.raises(ValueError, match=message):
        propagate_omm_main.main([])


def test_main_rejects_nonpositive_step(monkeypatch):
    args = SimpleNamespace(
        is_tle=False,
        input_file="input",
        duration_s=60.0,
        start=None,
        stop=None,
        step=0.0,
        data_only=False,
        output_oem="-",
    )
    data = SimpleNamespace(
        epoch="2026-01-01T00:00:00.000000",
        tle_parameters=None,
        mean_element_theory="KEPLER",
    )
    monkeypatch.setitem(_propagate_omm_main_globals, "parse_arguments", lambda *_: args)
    monkeypatch.setitem(_propagate_omm_main_globals, "read_omm_input", lambda *_: data)

    with pytest.raises(ValueError, match="--step must be > 0"):
        propagate_omm_main.main([])


def test_cli_forwards_to_shared_runner(monkeypatch):
    calls = []
    monkeypatch.setattr(
        core_cli,
        "run_cli",
        lambda main, argv: calls.append((main, argv)) or 7,
    )

    assert propagate_omm_main.cli(["input.omm"]) == 7
    assert calls == [(propagate_omm_main.main, ["input.omm"])]


def test_main_dispatches_raw_tle_to_sgp4(monkeypatch):
    tle_data = SimpleNamespace(epoch_year=26, epoch_day=1.0)
    epoch = time_utils.tt_s_to_datetime(0.0)
    calls = []
    monkeypatch.setitem(
        _propagate_omm_main_globals, "read_tle_input", lambda *_: tle_data
    )
    monkeypatch.setitem(
        _propagate_omm_main_globals,
        "propagate_tle_sgp4",
        lambda *args: calls.append(args),
    )
    monkeypatch.setattr(tle_mod, "tle_epoch_to_datetime", lambda *_: epoch)

    result = propagate_omm_main.main(
        ["--tle", "input.tle", "--duration", "1h", "--step", "15m", "--output", "-"]
    )

    assert result == 0
    assert len(calls) == 1
    assert calls[0][0] is tle_data
    assert calls[0][1] == epoch
