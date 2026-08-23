# To-do list

1. [`propagate-omm']
    1. propagate mean elements or TLE
    1. replace `propagate-tle`.

1. Better OPM support
    1. ?

1. [`propagate-orbit']
    1. give a less generic name
    1. numerical propagator

1. Propagator classes
    1. Keplerian propagator
    1. DSST propagator
    1. USM propagator
    1. Numerical propagator (Tudat wrapper)
    1. ?

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
