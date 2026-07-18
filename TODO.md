# To-do list

1. Improve CLI interface
    1. Unify CLI usage, options
        1. OEM input either file name or - for stdin
    1. ?
1. OEM
    1. `slice_oem.py`
        1. ?
    1. OEM frame conversions

1. Propagation tools
    1. Add fixed-step resampling / interpolation for propagated state histories so OEM-like exports can be generated at user-selected output intervals.
1. C++ propagation examples
    1. Recreate the Python propagation example behavior using Tudat's C++ API as a reference for C++ users and integration work.
1. Frame-conversion examples
    1. Add C++ frame-conversion examples comparable to the current Python scripts.
    1. Universal frame conversion scripts
1. TLE / OMM / OEM tools
    1. Continue improving TLE <-> OMM workflows.
    1. Continue improving TLE <-> OEM workflows.
        1. More options, for example selecting the TLE epoch explicitly.
1. Documentation
    1. Keep top-level and nested Markdown files aligned with the current source tree and CLI behavior.
