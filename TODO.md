# To-do list

1. Improve CLI interface
    1. Unify CLI usage, options
        1. OEM input either file name or - for stdin
        2. Output file option (-o, --output, --output-oem ?)
        1. --start, --stop, --step options for OEM slicing and propagation
            1. --duration aliases to --stop
    1. ?

1. Merge kepler/TLE tools?

1. OEM
    1. `diff_oem.py`
        1. More comparison options.
            1. Osculating keplerian elements
            1. Mean Keplerian element comparisons (for x minutes of sliding window).
        1. More output format options, for example showing the differences in a table or CSV format.
    1. `slice_oem.py`
        1. Further improvements?
    1. `xform_oem.py`
        1. Apply arbitrary matrix?

1. Propagation tools
    1. Add fixed-step resampling / interpolation for propagated state histories so OEM-like exports can be generated at user-selected output intervals.

1. TLE / OMM / OEM tools
    1. Continue improving TLE <-> OMM workflows.
    1. Continue improving TLE <-> OEM workflows.
        1. More options, for example selecting the TLE epoch explicitly.
        
1. Documentation
    1. Keep top-level and nested Markdown files aligned with the current source tree and CLI behavior.
