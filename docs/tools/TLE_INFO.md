# TLE Inspection Utility

The `tle-info` utility displays TLE parameters and derived orbital elements for one or more TLE files.

## Overview

For each input file, the command loads the TLE using TudatPy's SGP4 support and reports the epoch, TLE parameters, Cartesian state, and osculating Keplerian elements.

## Synopsis

```bash
tle-info <tle_file> [<tle_file> ...]
```

## Options

| Option | Description |
|--------|-------------|
| `<tle_file>` | Path to one or more TLE files to process. |
| `-h`, `--help` | Show the help message and exit. |

## Behavior

- Reads each TLE file and extracts its orbital parameters.
- Loads the TLE through TudatPy's SGP4 ephemeris support.
- Loads SPICE kernels for time conversion and Earth orientation data.
- Converts TLE mean elements to osculating Keplerian elements.
- Computes the Cartesian state at the TLE reference epoch.

## Examples

```bash
tle-info ISS.tle
tle-info ISS.tle NOAA-20.tle
tle-info --help
```

## Output

For each TLE file, the command prints:

- NORAD catalog number.
- Element set number.
- Revolution number at epoch.
- Epoch in ISO 8601 format.
- B-star drag term.
- Inclination, right ascension, argument of perigee, and mean anomaly in degrees.
- Eccentricity.
- Mean motion in degrees per minute and revolutions per day.
- Mean motion first and second derivatives.
- Cartesian state at epoch, with position in kilometers and velocity in kilometers per second.
- Osculating Keplerian elements, including semi-major axis, eccentricity, inclination, and angular elements.

## Usage

**Display TLE information:**

```bash
tle-info tests/data/ISS-ZARYA_1998-067A.tle
```

**Display information for multiple TLE files:**

```bash
tle-info tests/data/ISS-ZARYA_1998-067A.tle tests/data/AMOS-17_2019-050A.tle
```

**Show help:**

```bash
tle-info --help
```

## Requirements

The command requires TudatPy with SGP4 support, SPICE kernels available through
the project utilities, and valid two-line element files.

The implementation uses the local `ephem_toolkit.core.kepler` and
`ephem_toolkit.core.spice_utils` modules.

## Related Tools

- `download-tle` - Download current TLE or OMM data.
- `propagate-tle` - Propagate a TLE history.
- `propagate-omm` - Propagate an OMM or TLE input with automatic SGP4/Kepler selection.
- `tle-to-omm` - Convert TLE data to OMM.

