from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

import ephem_toolkit.core.ccsds.opm as opm
from ephem_toolkit.oem_to_opm import oem_to_opm


class DummyMeta:
    object_name = "SAT"
    object_id = "2024-001A"
    center_name = "EARTH"
    ref_frame = "ICRF"
    time_system = "UTC"


class DummyOemData:
    def __init__(self) -> None:
        self.states = [
            (
                0.0,
                np.array([7.0e6, 1.0e6, -2.0e6, 100.0, 7500.0, -200.0], dtype=float),
            ),
            (
                600.0,
                np.array([7.0e6, 1.0e6, -2.0e6, 100.0, 7500.0, -200.0], dtype=float),
            ),
        ]
        self.meta = DummyMeta()


def test_main_writes_initial_state_and_osculating_elements_to_opm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The OEM-to-OPM command should serialize its initial state and fit."""
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem_to_opm.oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(),
    )
    monkeypatch.setattr(
        oem_to_opm.fit_osculating_kepler,
        "fit_osculating_kepler",
        lambda *_args, **_kwargs: (
            np.array([7.1e6, 0.01, 0.2, 0.3, 0.4, 0.5]),
            {"status": "ok"},
        ),
    )
    monkeypatch.setattr(
        oem_to_opm.fit_osculating_kepler,
        "compute_kepler_propagation_comparison",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        oem_to_opm.fit_osculating_kepler,
        "format_kepler_output",
        lambda *_args, **_kwargs: "KEPLER_OUTPUT",
    )

    output_path = tmp_path / "out.opm"
    monkeypatch.setattr(
        sys, "argv", ["oem-to-opm", "input.oem", "-o", str(output_path)]
    )

    oem_to_opm.main()

    header, metadata, data = opm.read_opm(output_path)
    assert header["CCSDS_OPM_VERS"] == pytest.approx(3.0)
    assert header["ORIGINATOR"] == "oem_to_opm"
    assert metadata == {
        "OBJECT_NAME": "SAT",
        "OBJECT_ID": "2024-001A",
        "CENTER_NAME": "EARTH",
        "REF_FRAME": "ICRF",
        "TIME_SYSTEM": "UTC",
    }
    assert data["X"] == pytest.approx(7000.0)
    assert data["Y"] == pytest.approx(1000.0)
    assert data["Z_DOT"] == pytest.approx(-0.2)
    assert data["SEMI_MAJOR_AXIS"] == pytest.approx(7100.0)
    assert data["ECCENTRICITY"] == pytest.approx(0.01)
    assert data["INCLINATION"] == pytest.approx(np.degrees(0.2))
    assert data["RA_OF_ASC_NODE"] == pytest.approx(np.degrees(0.4))
    assert data["ARG_OF_PERICENTER"] == pytest.approx(np.degrees(0.3))
    assert data["TRUE_ANOMALY"] == pytest.approx(np.degrees(0.5))
    assert data["GM"] == pytest.approx(398600.4418)
