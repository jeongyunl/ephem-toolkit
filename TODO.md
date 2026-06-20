# To-do list

1. OEM file tools
    1. ~~Query & retrieve ephemeris/ephemerides~~
        1. ~~Index or time range~~
        1. ~~Start/stop times.~~ Useable start/stop times
    1. Calculate interpolated ephemeris
        1. Index or ~~time range~~
        1. ~~Step size~~
1. Implement a more robust interpolation method
    1. Solve Runge's phenomenon towards the end of OEM data
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
