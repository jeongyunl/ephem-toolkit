# Earth rotation model data files

Frame conversion is implemented in `common/frame_utils.py` and exposed for
CCSDS OEM files by `bin/xform_oem.py`. The `convert_frame()` dispatcher uses
TudatPy rotation models for inertial and Earth-fixed transformations, while
the TEME conversion uses TudatPy's element-conversion helpers.

## Kernel loading

`frame_utils.py` loads kernels through `common.spice_utils.load_kernel()` in
`_load_spice_kernels()`. The repository does not contain copies of these
files, and their absolute paths are determined by the installed TudatPy/Tudat
SPICE resource directory.

The implementation requests these kernel filenames:

- `naif0012.tls`: leap-seconds kernel
- `pck00011.tpc`: planetary constants kernel
- `earth_200101_990825_predict.bpc`: Earth rotation prediction kernel

The load is cached for the process, so the kernels are loaded once before the
first conversion that needs a TudatPy rotation model.

## Rotation models

`convert_frame()` uses the following Earth rotation models:

- `tudat_spice_rotation_model()`: TudatPy's SPICE rotation model between
  `J2000` and `ITRF93`
- `tudat_iau2006_rotation_model()`: TudatPy's IAU 2006 GCRS-to-ITRS model,
  exposed by the repository as `J2000` and `ITRF`

The state conversion includes the rotational transport term in the velocity.
Equivalent inertial frame names (`J2000`, `EME2000`, `ICRF`, and `GCRF`) are
normalized to `J2000` before dispatch. `TEME` is converted through `J2000`.

## Related Tudat resources

Other Earth-orientation files may be present in a particular Tudat
installation, including `earth_fixed.tf`,
`eopc04_14_IAU2000.62-now.txt`, `historicalDeltaT.txt`, and polar-motion,
ocean-tide, or libration tables. Their use is managed by TudatPy and depends
on the selected model and installed resource set; they are not loaded
directly by repository code.

For command-line examples and supported frame names, see
`doc/FRAME_CONVERSION.md`.
