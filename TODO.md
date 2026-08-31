# To-do list

1. Better OPM support
    1. improve `oem-to-opm`, `omm-to-opm`
        1. Produce accurate osculating state vector
            1. Batch Least-Squares Differential Correction 


1. Propagators
    1. Propagator interface/class hierarchy
    1. Keplerian propagator
    1. DSST propagator
        1. Orekit accuracy validation (deferred) — compare J2-only < 1 km/day, J2+J3+J4 < 100 m/day for LEO
        1. Lunar/solar long-period corrections (deferred)
        1. Code coverage > 90% for DSST module
        1. Equinoctial elements (Phase 6 optional) — singularity handling for e < 1e-6, i < 1°
        1. Variable fidelity mode (Phase 6 optional) — auto-select J2/J2+J3+J4/full by orbit regime
        1. State transition matrix (Phase 6 optional) — covariance propagation
        1. Batch processing (Phase 6 optional) — vectorized multi-satellite propagation
    1. USM propagator
    1. Numerical propagator (Tudat wrapper)
    1. ?

1. Improve CLI interface
    1. ?

1. Plotting
    1. `plot-orbit` -> `plot-oem`
    1. `plot-orbit-deltas` -> `plot-oem-diff`
        1. Modularize `diff-oem`
    1. add `--plot` option to `diff-oem`, `xform-oem`, `slice-oem`, etc. to generate plots of the results

1. ODM meta data
    1. Strict ODM meta data validation
        1. `REF_FRAME`
        1. `TIME_SYSTEM`
        1. `CENTER_NAME`
    1. Utilize
        1. `SOLAR_RAD_AREA`, `SOLAR_RAD_COEFF`
        1. `DRAG_AREA`, `DRAG_COEFF`
        1. `GM`
        1. `MEAN_ELEMENT_THEORY`
    1. Use units in ODM meta data (e.g., `[km]`, `[m/s]`, etc.) instead of assuming SI units

1. [`propagate-omm`](docs/PROPAGATE_OMM.md)
    1. Adopt more analytical propagators (e.g., `DSST`, `USM`, etc.) to support OMM propagation in the future

1. [`propagate-orbit`](docs/PROPAGATE_ORBIT.md)
    1. give a less generic name
    1. numerical propagator

1. Interpolators
    1. optimize lagrange and chebyshev for state vector interpolation?
        1. clamping since the first derivatives (velocity) are available
    1. clamped cubic spline?
    1. could chebyshev interpolater be more accurate?

1. [`slice-oem`](docs/SLICE_OEM.md)
    1. New stateful OemSlicer class?
        1. or extend CcsdsOem class?
    1. extract_states_by_time
        1. Optionally insert extra data points at boundaries to be interpolator friendly?

1. Improve library API
    1. Streamline file I/O function names and conventions

1. [`diff-oem`](docs/DIFF_OEM.md)
    1. More comparison options.
        1. Osculating keplerian elements
        1. Mean Keplerian element comparisons (for x minutes of sliding window).
    1. More output format options, for example showing the differences in a table or CSV format.
1. [`xform-oem`](docs/XFORM_OEM.md)
    1. Apply arbitrary matrix?


1. Propagation tools
    1. Add fixed-step resampling / interpolation for propagated state histories so OEM-like exports can be generated at user-selected output intervals.
