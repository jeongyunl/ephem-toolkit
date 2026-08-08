# TudatPy frame-conversion API notes

The command-line frame-conversion entry point is `bin/xform_oem.py`. It calls
`common.frame_utils.convert_frame`, which normalizes equivalent inertial frame
names and applies the appropriate TudatPy transformation for each supported
source and target pair.

## APIs used by the current implementation

The implementation uses:

- `tudatpy.astro.element_conversion.teme_to_j2000`
- `tudatpy.dynamics.environment_setup.rotation_model`
- `tudatpy.interface.spice`
- `tudatpy.dynamics.environment.RotationalEphemeris`
- `tudatpy.interface.spice.compute_state_rotation_matrix_between_frames`
  when available
- `tudatpy.interface.spice.compute_rotation_matrix_between_frames` and
  `compute_rotation_matrix_derivative_between_frames` as the SPICE fallback

The state transformation includes the velocity contribution from the
time-dependent rotation. `common.frame_utils.convert_frame` accepts states in
metres and metres per second; `xform_oem.py` handles conversion to and from OEM
km and km/s.

## Related API notes

The lower-level helpers also expose TEME/J2000 conversion functions and TudatPy
rotation-model operations such as inertial-to-body-fixed and body-fixed-to-
inertial rotation. See `common/frame_utils.py` for the supported frame enum and
conversion dispatch.

For command-line usage, see `FRAME_CONVERSION.md`.