# TudatPy frame-conversion API notes

## Context

The current frame-conversion scripts in this repository use two main approaches:

- direct SPICE frame rotation calls in `bin/gcrf_to_itrf_spice.py`
- TudatPy Earth rotation models in `bin/gcrf_to_itrf_rot_model.py`

This note lists relevant TudatPy APIs that were useful during implementation and investigation.

## APIs directly relevant to the current scripts

### SPICE rotation matrices

Used by `gcrf_to_itrf_spice.py`:

- `tudatpy.interface.spice.compute_rotation_matrix_between_frames(...)`
- `tudatpy.interface.spice.compute_rotation_matrix_derivative_between_frames(...)`

These are combined in the script into a 6x6 state transformation matrix so both position and velocity are transformed consistently.

### Rotation-model-based frame conversion

Used by `gcrf_to_itrf_rot_model.py`:

- `tudatpy.dynamics.environment_setup.rotation_model.spice(...)`
- `tudatpy.dynamics.environment_setup.rotation_model.gcrs_to_itrs(...)`
- `tudatpy.dynamics.environment.RotationalEphemeris.inertial_to_body_fixed_rotation(...)`
- `tudatpy.dynamics.environment.RotationalEphemeris.body_fixed_to_inertial_rotation(...)`
- `tudatpy.dynamics.environment.RotationalEphemeris.angular_velocity_in_body_fixed_frame(...)`
- `tudatpy.dynamics.environment.RotationalEphemeris.angular_velocity_in_inertial_frame(...)`

## Other related TudatPy APIs noted during exploration

### Rotation matrices

- `tudatpy.astro.element_conversion.teme_to_j2000(...)`
- `tudatpy.astro.element_conversion.j2000_to_teme(...)`
- `tudatpy.dynamics.environment.AerodynamicAngleCalculator.get_rotation_matrix_between_frames(...)`
- `tudatpy.dynamics.environment.Body.inertial_to_body_fixed_frame`
- `tudatpy.dynamics.environment.Body.body_fixed_to_inertial_frame`
- `tudatpy.dynamics.environment.Body.inertial_to_body_fixed_frame_derivative`
- `tudatpy.dynamics.environment.Body.body_fixed_to_inertial_frame_derivative`
- `tudatpy.dynamics.environment.GroundStationState.rotation_matrix_body_fixed_to_topocentric`

### Rotation-matrix derivatives

- `tudatpy.dynamics.environment.RotationalEphemeris.time_derivative_body_fixed_to_inertial_rotation(...)`
- `tudatpy.dynamics.environment.RotationalEphemeris.time_derivative_inertial_to_body_fixed_rotation(...)`
- `tudatpy.interface.spice.compute_rotation_matrix_derivative_between_frames(...)`

### Angular velocity

- `tudatpy.dynamics.environment.RotationalEphemeris.angular_velocity_in_body_fixed_frame(...)`
- `tudatpy.dynamics.environment.RotationalEphemeris.angular_velocity_in_inertial_frame(...)`
- `tudatpy.dynamics.environment.Body.inertial_angular_velocity`
- `tudatpy.dynamics.environment.Body.body_fixed_angular_velocity`
- `tudatpy.interface.spice.get_angular_velocity_vector_of_frame_in_original_frame(...)`

## Repository-specific takeaway

For the current repository code:

- use the SPICE matrix + derivative approach when you want an explicit state transformation between named SPICE frames
- use the rotation-model approach when you want Tudat-managed Earth rotation models such as `gcrs_to_itrs`, `spice_itrf93`, or `spice_iau_earth`

The top-level user documentation for these scripts is maintained in:

- `FRAME_CONVERSION.md`
