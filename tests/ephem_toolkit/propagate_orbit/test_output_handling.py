"""Tests for numerical OEM output provenance."""

from types import SimpleNamespace

import numpy as np

from ephem_toolkit.propagate_orbit.output_handling import write_state_history_oem


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
    assert "EPHEMERIS_PROVENANCE: source=OPM; transformation=propagation; target_model=numerical" in text
    assert "EPHEMERIS_PROPAGATION: integrator=rkdp_87; step_size_s=(1.0, 10.0, 300.0); earth_gravity=5x5; drag=on; srp=off; moon=on; sun=off; venus=off; mars=on" in text
