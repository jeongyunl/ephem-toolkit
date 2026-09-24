"""Tests for numerical OEM output provenance."""

import csv
from types import SimpleNamespace

import numpy as np

from ephem_toolkit.propagate_orbit.output_handling import (
    print_pre_propagation_summary,
    write_dependent_variables_csv,
    write_state_history_oem,
)


def test_write_state_history_oem_records_propagation_configuration(tmp_path) -> None:
    config = SimpleNamespace(
        satellite_name="TEST",
        integrator_method="rkdp_87",
        integrator_step_size_values_s=(1.0, 10.0, 300.0),
        earth_spherical_harmonic_gravity_degree=5,
        earth_spherical_harmonic_gravity_order=5,
        is_earth_drag_on=True,
        is_srp_on=False,
        is_moon_gravity_on=True,
        is_sun_gravity_on=False,
        is_venus_gravity_on=False,
        is_mars_gravity_on=True,
    )
    output = tmp_path / "propagated.oem"

    write_state_history_oem(
        {0.0: np.zeros(6), 60.0: np.ones(6)},
        str(output),
        config,
        data_only=False,
    )

    text = output.read_text(encoding="utf-8")
    assert (
        "EPHEMERIS_PROVENANCE: source=OPM; transformation=propagation; target_model=numerical"
        in text
    )
    assert (
        "EPHEMERIS_PROPAGATION: integrator=rkdp_87; step_size_s=(1.0, 10.0, 300.0); earth_gravity=5x5; drag=on; srp=off; moon=on; sun=off; venus=off; mars=on"
        in text
    )


def test_write_dependent_variables_csv_formats_scalar_and_vector_columns(
    tmp_path,
) -> None:
    scalar_setting = SimpleNamespace(
        dependent_variable_type=SimpleNamespace(name="relative_speed_type"),
        associated_body="ISS",
        secondary_body="Earth",
        component_index=-1,
    )
    vector_setting = SimpleNamespace(
        dependent_variable_type=SimpleNamespace(name="relative_position_type"),
        acceleration_model_type=SimpleNamespace(name="point_mass_gravity_type"),
        associated_body="ISS",
        secondary_body="Earth",
        component_index=-1,
    )

    class FakeDependentVariables:
        time_history = [0.0, 60.0]

        def asarray(self, setting):
            if setting is scalar_setting:
                return np.array([7.5, 7.4])
            return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    destination = tmp_path / "dep_vars.csv"
    write_dependent_variables_csv(
        str(destination), FakeDependentVariables(), [scalar_setting, vector_setting]
    )

    with destination.open(newline="", encoding="utf-8") as file_handle:
        rows = list(csv.reader(file_handle))
    assert rows[0] == [
        "epoch_tt_s",
        "relative_speed//ISS/Earth//",
        "relative_position/point_mass_gravity/ISS/Earth//0",
        "relative_position/point_mass_gravity/ISS/Earth//1",
        "relative_position/point_mass_gravity/ISS/Earth//2",
    ]
    assert rows[1] == ["0.0", "7.5", "1.0", "2.0", "3.0"]


def test_print_pre_propagation_summary_reports_optional_outputs(
    monkeypatch, capsys
) -> None:
    import ephem_toolkit.propagate_orbit.output_handling as output_handling

    monkeypatch.setattr(
        output_handling.time_utils, "tt_s_to_datetime", lambda epoch: epoch
    )
    monkeypatch.setattr(
        output_handling.time_utils,
        "datetime_to_iso8601",
        lambda epoch: f"epoch-{epoch}",
    )
    config = SimpleNamespace(
        satellite_name="ISS",
        satellite_mass_kg=420.0,
        integrator_method="rkdp_87",
        integrator_step_size_values_s=(10.0, 1.0, 100.0),
        earth_spherical_harmonic_gravity_degree=8,
        earth_spherical_harmonic_gravity_order=6,
        satellite_drag_area_m2=2.0,
        is_srp_on=True,
        srp_coefficient=1.2,
        is_earth_drag_on=True,
        satellite_drag_coefficient=2.2,
        is_moon_gravity_on=True,
        is_sun_gravity_on=False,
        is_venus_gravity_on=False,
        is_mars_gravity_on=True,
    )
    initial_state = SimpleNamespace(epoch_s=10.0, state_m_m_s=np.arange(6.0) * 1000.0)

    print_pre_propagation_summary(
        config,
        initial_state,
        target_epoch_s=70.0,
        input_source="stdin",
        output_oem_path="-",
        dep_var_csv_path="dep_vars.csv",
    )

    captured = capsys.readouterr().out
    assert "Integrator mode: variable-step size" in captured
    assert "Solar radiation pressure coefficient: 1.2" in captured
    assert "Drag coefficient: 2.2" in captured
    assert "OEM output: stdout" in captured
    assert "Dependent variables CSV output: dep_vars.csv" in captured
