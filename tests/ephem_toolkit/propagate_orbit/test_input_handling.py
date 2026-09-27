"""Tests for propagate_orbit/input_handling.py.

Verifies that build_propagation_inputs returns the correct split types
(NumericalPropagatorConfig, NumericalInitialState, target_epoch_s)
and that all fields are mapped correctly from CLI args.
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from ephem_toolkit.core.propagator.numerical import (
    NumericalInitialState,
    NumericalPropagatorConfig,
)
from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.core.ccsds.opm import (
    CcsdsOpm,
    OpmCovariance,
    OpmHeader,
    OpmKeplerianElements,
    OpmManeuver,
    OpmSpacecraftParameters,
    OpmStateVector,
)
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.propagate_orbit.input_handling import build_propagation_inputs
import ephem_toolkit.propagate_orbit.propagation as propagation
from ephem_toolkit.propagate_orbit.constants import (
    DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
    DEFAULT_SATELLITE_DRAG_COEFFICIENT,
    DEFAULT_SATELLITE_MASS_KG,
    DEFAULT_SATELLITE_NAME,
    DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT,
)
import ephem_toolkit.propagate_orbit.input_handling as input_handling

# ===================================================================
# Shared fixtures
# ===================================================================

_EPOCH_UTC = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
_STATE_M_M_S = np.array(
    [-2700816.14, -3314092.80, 5266346.42, 5168.606550, -5597.546618, -2131.981798],
    dtype=float,
)


def _make_cli_args(**overrides) -> argparse.Namespace:
    """Return a minimal valid argparse.Namespace for build_propagation_inputs."""
    defaults = dict(
        input_opm="input.opm",
        name="TestSat",
        mass=None,
        integrator="rkdp_87",
        integrator_step_size=[10.0, 1.0, 300.0],
        earth_gravity=(5, 5),
        drag_area=None,
        srp=False,
        srp_coeff=None,
        drag=False,
        drag_coeff=None,
        moon_gravity=False,
        sun_gravity=False,
        venus_gravity=False,
        mars_gravity=False,
        duration=3600.0,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _patch_opm_reader(
    state=_STATE_M_M_S,
    epoch=_EPOCH_UTC,
    object_id="2024-001A",
    object_name="",
    source_comments=("SOURCE_COMMENT: input",),
    covariance=None,
):
    """Patch the OPM reader to return fixed state, epoch, and identity."""
    return patch(
        "ephem_toolkit.propagate_orbit.input_handling"
        ".read_initial_state_from_opm_file_or_stdin",
        return_value=(
            state,
            epoch,
            object_id,
            object_name,
            source_comments,
            None,
            covariance,
        ),
    )


# ===================================================================
# Return type
# ===================================================================


def test_build_propagation_inputs_returns_three_tuple() -> None:
    """build_propagation_inputs returns (config, initial_state, target_epoch_s)."""
    with _patch_opm_reader():
        result = build_propagation_inputs(_make_cli_args())

    assert isinstance(result, tuple)
    assert len(result) == 3
    config, initial_state, target_epoch_s = result
    assert isinstance(config, NumericalPropagatorConfig)
    assert isinstance(initial_state, NumericalInitialState)
    assert isinstance(target_epoch_s, float)


# ===================================================================
# NumericalPropagatorConfig fields
# ===================================================================


def test_config_satellite_name() -> None:
    """Config satellite_name matches CLI --name."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(name="MySat"))
    assert config.satellite_name == "MySat"


def test_config_defaults_name_to_opm_object_name() -> None:
    """The source object name is used unless --name overrides it."""
    with _patch_opm_reader(object_name="SourceSat"):
        config, _, _ = build_propagation_inputs(_make_cli_args(name=None))

    assert config.satellite_name == "SourceSat"


def test_config_empty_name_uses_default() -> None:
    """Empty satellite name falls back to DEFAULT_SATELLITE_NAME."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(name=""))
    assert config.satellite_name == DEFAULT_SATELLITE_NAME


def test_config_whitespace_name_uses_default() -> None:
    """Whitespace-only satellite name falls back to DEFAULT_SATELLITE_NAME."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(name="   "))
    assert config.satellite_name == DEFAULT_SATELLITE_NAME


def test_config_mass() -> None:
    """Config satellite_mass_kg matches CLI --mass."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(mass=75.0))
    assert config.satellite_mass_kg == 75.0


def test_config_integrator_method() -> None:
    """Config integrator_method matches CLI --integrator."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(integrator="rkf_78"))
    assert config.integrator_method == "rkf_78"


def test_config_integrator_step_size_values() -> None:
    """Config integrator_step_size_values_s is a tuple from CLI --integrator-step-size."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(
            _make_cli_args(integrator_step_size=[30.0])
        )
    assert config.integrator_step_size_values_s == (30.0,)


def test_config_earth_gravity() -> None:
    """Config earth gravity degree/order match CLI --earth-gravity."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(earth_gravity=(8, 8)))
    assert config.earth_spherical_harmonic_gravity_degree == 8
    assert config.earth_spherical_harmonic_gravity_order == 8


def test_config_drag_area() -> None:
    """Config satellite_drag_area_m2 matches CLI --drag-area."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(drag_area=0.1))
    assert config.satellite_drag_area_m2 == 0.1


def test_config_perturbation_flags() -> None:
    """Config perturbation flags match CLI flags."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(
            _make_cli_args(
                srp=True,
                drag=True,
                moon_gravity=True,
                sun_gravity=True,
                venus_gravity=True,
                mars_gravity=True,
            )
        )
    assert config.is_srp_on is True
    assert config.is_earth_drag_on is True
    assert config.is_moon_gravity_on is True
    assert config.is_sun_gravity_on is True
    assert config.is_venus_gravity_on is True
    assert config.is_mars_gravity_on is True


def test_config_srp_coefficient() -> None:
    """Config srp_coefficient matches CLI --srp-coeff."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(srp_coeff=1.5))
    assert config.srp_coefficient == 1.5


def test_config_drag_coefficient() -> None:
    """Config satellite_drag_coefficient matches CLI --drag-coeff."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(drag_coeff=2.5))
    assert config.satellite_drag_coefficient == 2.5


def test_config_uses_defaults_when_opm_physical_parameters_are_absent() -> None:
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args())

    assert config.satellite_mass_kg == DEFAULT_SATELLITE_MASS_KG
    assert config.satellite_drag_area_m2 == DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2
    assert config.satellite_srp_area_m2 == DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2
    assert config.satellite_drag_coefficient == DEFAULT_SATELLITE_DRAG_COEFFICIENT
    assert config.srp_coefficient == DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT


def test_opm_physical_parameters_are_used_unless_cli_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_path = tmp_path / "physical-parameters.opm"
    covariance_matrix = np.eye(6)
    source_parameters = OpmSpacecraftParameters(
        mass=450.0,
        solar_rad_area=20.0,
        solar_rad_coeff=1.9,
        drag_area=14.0,
        drag_coeff=2.7,
    )
    CcsdsOpm(
        header=OpmHeader(
            version=3.0,
            creation_date="2026-05-20T00:00:00.000",
            originator="test",
        ),
        metadata={
            "OBJECT_NAME": "PARAMETER TEST SAT",
            "OBJECT_ID": "2024-001A",
            "CENTER_NAME": "EARTH",
            "REF_FRAME": "J2000",
            "TIME_SYSTEM": "UTC",
        },
        state_vector=OpmStateVector(
            epoch="2026-05-20T12:00:00.000",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
        ),
        spacecraft_parameters=source_parameters,
        covariance=OpmCovariance(covariance_matrix, ref_frame="J2000"),
    ).to_file(source_path)

    parsed_opm = CcsdsOpm.from_source(source_path)
    assert parsed_opm.spacecraft_parameters == source_parameters
    assert parsed_opm.covariance is not None
    np.testing.assert_array_equal(parsed_opm.covariance.matrix, covariance_matrix)

    fallback_args = _make_cli_args(
        input_opm=str(source_path),
        mass=None,
        drag_area=None,
        drag_coeff=None,
        srp_coeff=None,
    )
    config, _, _ = build_propagation_inputs(fallback_args)
    assert config.satellite_mass_kg == 450.0
    assert config.satellite_drag_area_m2 == 14.0
    assert config.satellite_srp_area_m2 == 20.0
    assert config.satellite_drag_coefficient == 2.7
    assert config.srp_coefficient == 1.9

    cli_args = _make_cli_args(
        input_opm=str(source_path),
        mass=81.0,
        drag_area=0.12,
        drag_coeff=2.4,
        srp_coeff=1.6,
        srp=True,
        drag=True,
    )
    config, initial_state, target_epoch_s = build_propagation_inputs(cli_args)

    assert config.satellite_mass_kg == 81.0
    assert config.satellite_drag_area_m2 == 0.12
    assert config.satellite_srp_area_m2 == 0.12
    assert config.satellite_drag_coefficient == 2.4
    assert config.srp_coefficient == 1.6
    assert initial_state.covariance_matrix_si is not None
    np.testing.assert_array_equal(
        initial_state.covariance_matrix_si, covariance_matrix * 1e6
    )

    class FakeNumericalPropagator:
        def __init__(self, _config, _initial_state):
            self.dependent_variable_dictionary = {}
            self.dependent_variable_save_settings = []

        def propagate_to(self, _target_epoch_s, output):
            return [
                (initial_state.epoch_s, initial_state.state_m_m_s),
                (initial_state.epoch_s + 60.0, initial_state.state_m_m_s),
            ]

    monkeypatch.setattr(propagation, "NumericalPropagator", FakeNumericalPropagator)
    output_path = tmp_path / "propagated.oem"
    propagation.run_propagation(
        config,
        initial_state,
        target_epoch_s,
        str(output_path),
        None,
        False,
    )
    generated_oem = CcsdsOem.read(output_path)
    assert len(generated_oem.states) == 2
    assert len(generated_oem.covariances) == 1
    assert (
        time_utils.iso8601_to_datetime(generated_oem.covariances[0].epoch) == _EPOCH_UTC
    )
    assert generated_oem.covariances[0].ref_frame == "J2000"
    np.testing.assert_array_equal(
        generated_oem.covariances[0].matrix, covariance_matrix
    )

    data_only_path = tmp_path / "propagated-data-only.oem"
    propagation.run_propagation(
        config,
        initial_state,
        target_epoch_s,
        str(data_only_path),
        None,
        True,
    )
    assert "COVARIANCE_START" not in data_only_path.read_text(encoding="utf-8")


def test_opm_omits_keplerian_elements_and_maneuvers_from_oem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_path = tmp_path / "optional-opm-fields.opm"
    CcsdsOpm(
        header=OpmHeader(
            version=3.0,
            creation_date="2026-05-20T00:00:00.000",
            originator="test",
            comments=["SOURCE_COMMENT: optional OPM fields"],
        ),
        metadata={
            "OBJECT_NAME": "OPM METADATA SAT",
            "OBJECT_ID": "2024-001A",
            "CENTER_NAME": "EARTH",
            "REF_FRAME": "J2000",
            "TIME_SYSTEM": "UTC",
        },
        state_vector=OpmStateVector(
            epoch="2026-05-20T12:00:00.000",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
        ),
        keplerian_elements=OpmKeplerianElements(
            semi_major_axis=7000.0,
            eccentricity=0.01,
            inclination=51.6,
            ra_of_asc_node=45.0,
            arg_of_pericenter=30.0,
            gm=398600.4418,
            true_anomaly=10.0,
        ),
        spacecraft_parameters=OpmSpacecraftParameters(mass=500.0),
        maneuvers=[
            OpmManeuver(
                man_epoch_ignition="2026-05-20T12:10:00.000",
                man_duration=60.0,
                man_delta_mass=-1.0,
                man_ref_frame="RTN",
                man_dv_1=0.001,
                man_dv_2=0.002,
                man_dv_3=0.003,
            )
        ],
    ).to_file(source_path)

    parsed_opm = CcsdsOpm.from_source(source_path)
    assert parsed_opm.keplerian_elements is not None
    assert len(parsed_opm.maneuvers) == 1
    args = _make_cli_args(input_opm=str(source_path), name="OPM METADATA SAT")
    config, initial_state, target_epoch_s = build_propagation_inputs(args)

    class FakeNumericalPropagator:
        def __init__(self, _config, _initial_state):
            self.dependent_variable_dictionary = {}
            self.dependent_variable_save_settings = []

        def propagate_to(self, _target_epoch_s, output):
            return [
                (initial_state.epoch_s, initial_state.state_m_m_s),
                (initial_state.epoch_s + 60.0, initial_state.state_m_m_s),
            ]

    monkeypatch.setattr(propagation, "NumericalPropagator", FakeNumericalPropagator)
    output_path = tmp_path / "propagated.oem"
    propagation.run_propagation(
        config, initial_state, target_epoch_s, str(output_path), None, False
    )

    generated_oem = CcsdsOem.read(output_path)
    assert generated_oem.meta.object_name == "OPM METADATA SAT"
    assert generated_oem.meta.object_id == "2024-001A"
    assert "SOURCE_COMMENT: optional OPM fields" in generated_oem.meta.comments
    serialized = output_path.read_text(encoding="utf-8")
    for field in (
        "SEMI_MAJOR_AXIS",
        "TRUE_ANOMALY",
        "MAN_EPOCH_IGNITION",
        "MAN_DURATION",
        "MAN_DELTA_MASS",
        "MAN_DV_1",
        "MASS",
    ):
        assert field not in serialized


def test_read_initial_state_rejects_non_equivalent_covariance_frame(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "rtn-covariance.opm"
    CcsdsOpm(
        header=OpmHeader(
            version=3.0,
            creation_date="2026-05-20T00:00:00.000",
            originator="test",
        ),
        metadata={
            "OBJECT_NAME": "PARAMETER TEST SAT",
            "OBJECT_ID": "2024-001A",
            "CENTER_NAME": "EARTH",
            "REF_FRAME": "J2000",
            "TIME_SYSTEM": "UTC",
        },
        state_vector=OpmStateVector(
            epoch="2026-05-20T12:00:00.000",
            x=7000.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=7.5,
            z_dot=0.0,
        ),
        covariance=OpmCovariance(np.eye(6), ref_frame="RTN"),
    ).to_file(source_path)

    with pytest.raises(SystemExit):
        build_propagation_inputs(_make_cli_args(input_opm=str(source_path)))

    assert "J2000-equivalent" in capsys.readouterr().err


# ===================================================================
# NumericalInitialState fields
# ===================================================================


def test_initial_state_vector() -> None:
    """initial_state.state_m_m_s matches OPM-derived state vector."""
    with _patch_opm_reader(state=_STATE_M_M_S):
        _, initial_state, _ = build_propagation_inputs(_make_cli_args())
    np.testing.assert_array_equal(initial_state.state_m_m_s, _STATE_M_M_S)


def test_initial_state_epoch_is_tt_seconds() -> None:
    """initial_state.epoch_s is TT seconds from OPM epoch datetime."""
    with _patch_opm_reader(epoch=_EPOCH_UTC):
        _, initial_state, _ = build_propagation_inputs(_make_cli_args())
    expected_epoch_s = time_utils.datetime_to_tt_s(_EPOCH_UTC)
    assert initial_state.epoch_s == pytest.approx(expected_epoch_s)


# ===================================================================
# target_epoch_s
# ===================================================================


def test_target_epoch_s_equals_epoch_plus_duration() -> None:
    """target_epoch_s == initial_state.epoch_s + cli_args.duration."""
    duration = 7200.0
    with _patch_opm_reader(epoch=_EPOCH_UTC):
        _, initial_state, target_epoch_s = build_propagation_inputs(
            _make_cli_args(duration=duration)
        )
    assert target_epoch_s == pytest.approx(initial_state.epoch_s + duration)


def test_target_epoch_s_zero_duration() -> None:
    """target_epoch_s equals epoch_s when duration is 0."""
    with _patch_opm_reader(epoch=_EPOCH_UTC):
        _, initial_state, target_epoch_s = build_propagation_inputs(
            _make_cli_args(duration=0.0)
        )
    assert target_epoch_s == pytest.approx(initial_state.epoch_s)


@pytest.mark.parametrize("input_opm", ["-", "input.opm"])
def test_read_initial_state_parses_stdin_and_file_sources(
    monkeypatch: pytest.MonkeyPatch, input_opm: str
) -> None:
    input_state_km = np.arange(1.0, 7.0)
    message = SimpleNamespace(
        header=SimpleNamespace(comments=["SOURCE_COMMENT: input"]),
        metadata={
            "OBJECT_ID": "2024-001A",
            "OBJECT_NAME": "SourceSat",
            "CENTER_NAME": "EARTH",
            "REF_FRAME": "J2000",
            "TIME_SYSTEM": "UTC",
        },
        state_vector=SimpleNamespace(
            epoch="2026-05-20T12:00:00Z", values=input_state_km
        ),
        spacecraft_parameters=None,
    )
    sources = []

    def parse_source(source):
        sources.append(source)
        return message

    monkeypatch.setattr(input_handling.opm.CcsdsOpm, "from_source", parse_source)
    monkeypatch.setattr(
        input_handling.time_utils,
        "iso8601_to_datetime",
        lambda _epoch: _EPOCH_UTC,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("OPM input"))

    (
        state_m_m_s,
        epoch,
        object_id,
        object_name,
        source_comments,
        spacecraft_parameters,
        covariance,
    ) = input_handling.read_initial_state_from_opm_file_or_stdin(
        argparse.Namespace(input_opm=input_opm)
    )

    np.testing.assert_array_equal(state_m_m_s, input_state_km * 1000.0)
    assert epoch is _EPOCH_UTC
    assert object_id == "2024-001A"
    assert object_name == "SourceSat"
    assert source_comments == ("SOURCE_COMMENT: input",)
    assert spacecraft_parameters is None
    assert covariance is None
    if input_opm == "-":
        assert isinstance(sources[0], io.StringIO)
    else:
        assert sources[0].name == input_opm


def test_read_initial_state_rejects_tty_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "stdin",
        SimpleNamespace(isatty=lambda: True, read=lambda: ""),
    )

    with pytest.raises(SystemExit) as error:
        input_handling.read_initial_state_from_opm_file_or_stdin(
            argparse.Namespace(input_opm="-")
        )

    assert error.value.code == 1
    assert "requires OPM content from stdin" in capsys.readouterr().err


def test_read_initial_state_reports_stdin_and_file_parse_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("bad OPM"))
    monkeypatch.setattr(
        input_handling.opm.CcsdsOpm,
        "from_source",
        lambda _source: (_ for _ in ()).throw(ValueError("invalid message")),
    )

    with pytest.raises(SystemExit) as stdin_error:
        input_handling.read_initial_state_from_opm_file_or_stdin(
            argparse.Namespace(input_opm="-")
        )
    assert stdin_error.value.code == 1
    assert "invalid stdin OPM input" in capsys.readouterr().err

    with pytest.raises(SystemExit) as file_error:
        input_handling.read_initial_state_from_opm_file_or_stdin(
            argparse.Namespace(input_opm="missing.opm")
        )
    assert file_error.value.code == 1
    assert "failed to read OPM file 'missing.opm'" in capsys.readouterr().err


def test_read_initial_state_reports_invalid_epoch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    message = SimpleNamespace(
        metadata={
            "CENTER_NAME": "EARTH",
            "REF_FRAME": "J2000",
            "TIME_SYSTEM": "UTC",
        },
        state_vector=SimpleNamespace(epoch="invalid", values=np.zeros(6)),
    )
    monkeypatch.setattr(
        input_handling.opm.CcsdsOpm, "from_source", lambda _source: message
    )
    monkeypatch.setattr(
        input_handling.time_utils,
        "iso8601_to_datetime",
        lambda _epoch: (_ for _ in ()).throw(ValueError("bad epoch")),
    )

    with pytest.raises(SystemExit) as error:
        input_handling.read_initial_state_from_opm_file_or_stdin(
            argparse.Namespace(input_opm="input.opm")
        )

    assert error.value.code == 1
    assert "invalid OPM EPOCH value" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("CENTER_NAME", "MOON", "CENTER_NAME=EARTH"),
        ("REF_FRAME", "TOD", "REF_FRAME=J2000"),
        ("TIME_SYSTEM", "TAI", "TIME_SYSTEM=UTC"),
    ],
)
def test_read_initial_state_rejects_unsupported_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: str,
    expected: str,
) -> None:
    metadata = {
        "OBJECT_NAME": "SAT",
        "OBJECT_ID": "2024-001A",
        "CENTER_NAME": "EARTH",
        "REF_FRAME": "J2000",
        "TIME_SYSTEM": "UTC",
    }
    metadata[field] = value
    message = SimpleNamespace(
        metadata=metadata,
        state_vector=SimpleNamespace(epoch="2026-05-20T12:00:00", values=np.zeros(6)),
    )
    monkeypatch.setattr(
        input_handling.opm.CcsdsOpm, "from_source", lambda _source: message
    )
    monkeypatch.setattr(
        input_handling.time_utils,
        "iso8601_to_datetime",
        lambda _epoch: _EPOCH_UTC,
    )

    with pytest.raises(SystemExit) as error:
        input_handling.read_initial_state_from_opm_file_or_stdin(
            argparse.Namespace(input_opm="input.opm")
        )

    assert error.value.code == 1
    assert expected in capsys.readouterr().err
