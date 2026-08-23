# To-do list

1. Propagators
    1. Propagator interface/class hierarchy
    1. Keplerian propagator
    1. DSST propagator
    1. USM propagator
    1. Numerical propagator (Tudat wrapper)
    1. ?

1. ODM meta data
    1. Strict ODM meta data validation
        1. REF_FRAME
        1. TIME_SYSTEM
        1. CENTER_NAME
    1. Utilize
        1. SOLAR_RAD_AREA, SOLAR_RAD_COEFF
        1. DRAG_AREA, DRAG_COEFF
        1. GM
        1. MEAN_ELEMENT_THEORY
    1. Use units in ODM meta data (e.g., [km], [m/s], etc.) instead of assuming SI units

1. [`propagate-omm`](docs/PROPAGATE_OMM.md)
    1. Adopt more analytical propagators (e.g., DSST, USM, etc.) to support OMM propagation in the future

1. [`propagate-tle`](docs/PROPAGATE_TLE.md)
    1. Keep it or obsolete it? (maybe keep it for now?)

1. Better OPM support
    1. ?

1. [`propagate-orbit']
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

1. Improve CLI interface
    1. ?

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

1. TLE / OMM / OEM tools
    1. Continue improving TLE <-> OMM workflows.
    1. Continue improving TLE <-> OEM workflows.
        1. More options, for example selecting the TLE epoch explicitly.
        
1. Documentation
    1. Keep top-level and nested Markdown files aligned with the current source tree and CLI behavior.
