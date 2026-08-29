# TudatPy frame-conversion API notes

The command-line frame-conversion entry point is `xform-oem`. It calls
`core.frame_utils.convert_frame`, which normalizes equivalent inertial frame
names and applies the appropriate TudatPy transformation for each supported
source and target pair.

See [XFORM_OEM.md](XFORM_OEM.md) for complete command-line usage.

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
time-dependent rotation. `core.frame_utils.convert_frame` accepts states in
metres and metres per second; `xform-oem` handles conversion to and from OEM
km and km/s.

## Earth rotation models

`convert_frame()` uses the following TudatPy rotation models for Earth-fixed
transformations:

- `tudat_spice_rotation_model()`: a SPICE model between `J2000` and `ITRF93`
- `tudat_iau2006_rotation_model()`: an IAU 2006 GCRS-to-ITRS model exposed by
  the repository as `J2000` and `ITRF`

The kernel files loaded by these models are documented in the TudatPy Earth-rotation reference material used by this project.

### SPICE model

`tudat_spice_rotation_model()` creates one Earth rotation model using:

- original inertial orientation: `J2000`
- target body-fixed orientation: `ITRF93`
- TudatPy settings: `environment_setup.rotation_model.spice()`

The model uses the loaded SPICE Earth-orientation kernels to evaluate the
Earth-fixed rotation at each requested epoch. The model is constructed lazily
and stored in `_tudat_spice_rotation_model`; later calls return the same model.

### IAU 2006 model

`tudat_iau2006_rotation_model()` creates one Earth rotation model using:

- global frame orientation: `GCRS`
- TudatPy settings: `environment_setup.rotation_model.gcrs_to_itrs()`
- conventions: `IAUConventions.iau_2006`

The public `Frame` enum calls the corresponding inertial and terrestrial frames
`J2000` and `ITRF`, respectively. This is the repository's API naming; the
underlying TudatPy model is configured as GCRS-to-ITRS. It is also constructed
lazily and cached in `_tudat_iau2006_rotation_model`.

### State conversion and velocity terms

The rotation-model helpers transform complete Cartesian states, not just
positions. For an inertial-to-body-fixed conversion, let $R$ be TudatPy's
inertial-to-body-fixed rotation, $\boldsymbol{\omega}_b$ the angular velocity
expressed in the body-fixed frame, and $\mathbf{r}_b = R\mathbf{r}_i$. The
implementation evaluates:

$$
\mathbf{r}_b = R\mathbf{r}_i,
\qquad
\mathbf{v}_b = R\mathbf{v}_i - \boldsymbol{\omega}_b \times \mathbf{r}_b.
$$

For the inverse body-fixed-to-inertial conversion, it uses the corresponding
body-fixed-to-inertial rotation and inertial-frame angular velocity:

$$
\mathbf{r}_i = R\mathbf{r}_b,
\qquad
\mathbf{v}_i = R\mathbf{v}_b + \boldsymbol{\omega}_i \times \mathbf{r}_i.
$$

The cross-product terms are the rotating-frame transport terms. Omitting them
would produce a correct-looking position transformation but an incorrect
velocity for a time-dependent Earth-fixed frame.

### Dispatch and epoch handling

`convert_frame()` normalizes `EME2000`, `ICRF`, and `GCRF` to its canonical
`J2000` path. `TEME` is first converted to or from `J2000` using TudatPy's
TEME helper, and conversions between `ITRF93` and `ITRF` pass through the
canonical inertial path:

```text
TEME <-> J2000 <-> ITRF93
                  <-> ITRF
```

Each state is evaluated at its own epoch. The dispatcher accepts epochs named
`epoch_tt_s` (TT seconds since J2000) and passes that value to TudatPy's
rotation-model methods, which use ephemeris-time seconds for their evaluation.
State vectors are expected in metres and metres per second at this layer; the
OEM command-line adapter handles conversion to and from its kilometre-based
units.

The conversion code loads the required SPICE kernels on first use and caches
both the kernel-load state and each rotation model for the lifetime of the
Python process. The cache is module-global, so separate calls to
`convert_frame()` reuse the already-created model.

## Related API notes

The lower-level helpers also expose TEME/J2000 conversion functions and TudatPy
rotation-model operations such as inertial-to-body-fixed and body-fixed-to-
inertial rotation. See `core/frame_utils.py` for the supported frame enum and
conversion dispatch.
