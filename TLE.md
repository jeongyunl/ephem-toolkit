# tudatpy-utils

TLE-related utilities for building, estimating, and converting orbital data.

## Overview

Current TLE-related scripts in this repository include:

- `tle/build_tle.py`
- `tle/download_tle.py`
- `tle/omm_to_tle.py`
- `tle/tle_to_omm.py`
- `tle/tle_info.py`
- `common/convert_tle.py`

This document focuses on the primary user-facing tools and the current repository context around them.

## `tle/build_tle.py`

This script estimates a TLE from an OEM-like Cartesian arc rather than from explicit TLE fields. It uses `common.tle.write_tle()` directly to format and write the resulting TLE.

That script is documented separately in:

- [`tle/build_tle.md`](tle/build_tle.md)

## Related conversion utilities

Additional scripts currently present in the repository:

- `tle/omm_to_tle.py` — convert OMM input to TLE output
- `tle/tle_to_omm.py` — convert TLE input to OMM output
- `tle/download_tle.py` — download TLE data
- `tle/tle_info.py` — inspect TLE information
- `common/convert_tle.py` — shared conversion helper script

## Common library

The `common/tle.py` module provides the shared `Tle` dataclass and the `read_tle()` / `write_tle()` functions used by all TLE-related scripts.

## Dependencies

### `tle/build_tle.py`

- Python standard library
- local helper module `common.tle`
- TudatPy (optional, for SGP4 state-match refinement and B* estimation)

### Other TLE-related scripts

Dependencies vary by script. Some use only the standard library and local helpers, while others may rely on TudatPy for propagation or conversion workflows.
