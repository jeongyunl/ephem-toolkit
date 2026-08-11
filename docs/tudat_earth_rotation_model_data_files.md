# Earth rotation model data files

Earth-rotation data used by the frame-conversion implementation is supplied by
the installed TudatPy/Tudat SPICE resource directory. This document lists the
files loaded directly by `core/frame_utils.py` and related resources that may
be used by TudatPy. For the frame-conversion APIs and rotation-model behavior,
see [tudatpy_frame_conversion.md](tudatpy_frame_conversion.md).

## Kernel loading

`frame_utils.py` loads kernels through `core.spice_utils.load_kernel()` in
`_load_spice_kernels()`. The repository does not contain copies of these
files, and their absolute paths are determined by the installed TudatPy/Tudat
SPICE resource directory.

The implementation requests these kernel filenames:

- `naif0012.tls`: leap-seconds kernel
- `pck00011.tpc`: planetary constants kernel
- `earth_200101_990825_predict.bpc`: Earth rotation prediction kernel

The load is cached for the process, so the kernels are loaded once before the
first conversion that needs a TudatPy rotation model.

## Related Tudat resources

Other Earth-orientation files may be present in a particular Tudat
installation, including `earth_fixed.tf`,
`eopc04_14_IAU2000.62-now.txt`, `historicalDeltaT.txt`, and polar-motion,
ocean-tide, or libration tables. Their use is managed by TudatPy and depends
on the selected model and installed resource set; they are not loaded
directly by repository code.

For command-line examples and supported frame names, see
[XFORM_OEM.md](XFORM_OEM.md).
