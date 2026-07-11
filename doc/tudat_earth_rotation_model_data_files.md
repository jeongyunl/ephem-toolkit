# Earth rotation model data files used by the frame-conversion scripts

## Context

The frame-conversion scripts in this repository are:

- `bin/gcrf_to_itrf_spice.py`
- `bin/gcrf_to_itrf_rot_model.py`

They load SPICE kernels through TudatPy's configured SPICE kernel directory rather than through hard-coded repository-local files.

In practice, the exact absolute paths depend on the local Tudat / TudatPy installation.

## Kernels used directly by the current scripts

### `bin/gcrf_to_itrf_spice.py`

Loads:

- `naif0012.tls`
- `earth_200101_990825_predict.bpc`

### `bin/gcrf_to_itrf_rot_model.py`

Loads:

- `naif0012.tls`
- `pck00011.tpc`
- `earth_200101_990825_predict.bpc`

## Common Tudat resource files relevant to Earth orientation

Depending on the selected Tudat rotation model and local installation, Earth-orientation support may involve files such as:

- `earth_200101_990825_predict.bpc`
  - long-span Earth orientation prediction kernel
  - commonly used for `ITRF93` / Earth-fixed SPICE frame rotations
- `naif0012.tls`
  - leap-seconds kernel
- `pck00011.tpc`
  - planetary constants kernel
- `earth_fixed.tf`
  - Earth-fixed frame definitions
- `eopc04_14_IAU2000.62-now.txt`
  - Earth orientation parameter data used by some Tudat Earth-orientation workflows
- `historicalDeltaT.txt`
- polar-motion / ocean-tide / libration support tables under Tudat resource directories

## Historical installation-specific paths

On some Linux installations these files may appear under locations similar to:

```text
/usr/share/tudat/resource/spice_kernels/
/usr/share/tudat/resource/earth_orientation/
```

Examples that have been observed in practice:

- `/usr/share/tudat/resource/earth_orientation/eopc04_14_IAU2000.62-now.txt`
- `/usr/share/tudat/resource/spice_kernels/earth_200101_990825_predict.bpc`
- `/usr/share/tudat/resource/spice_kernels/naif0012.tls`
- `/usr/share/tudat/resource/spice_kernels/earth_fixed.tf`

These paths are installation-dependent and should be treated as examples, not guaranteed locations.

## Notes

- `earth_200101_990825_predict.bpc` is a prediction kernel with broad future coverage and lower fidelity than high-accuracy Earth orientation products.
- The exact coverage and file versions depend on the installed Tudat resource set.
- For repository documentation, the script-level kernel filenames are the authoritative reference; absolute filesystem paths are environment-specific.
