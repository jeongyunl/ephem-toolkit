# Single-Orbit Plotting Utility

The `plot-orbit` utility reads a CCSDS OEM ephemeris and produces diagnostic plots for the orbit, state history, velocity, angular motion, geocentric distance, and WGS84 altitude.

## Overview

This utility provides several views of one OEM orbit:

- **State-vector views**: Plot the Cartesian position trajectory and components
- **RTN deltas**: Show sample-to-sample position and velocity changes in the local radial-transverse-normal frame
- **Motion diagnostics**: Plot velocity magnitude, angular velocity, direction changes, and Euler-angle rates
- **Distance and altitude**: Plot geocentric distance and altitude above the WGS84 ellipsoid
- **Duration filtering**: Analyze the full OEM history or only an initial time interval
- **Flexible display**: Show figures interactively or save each figure using a common output-file prefix

The command is installed as the canonical `plot-orbit` entry point.

## Synopsis

```bash
plot-orbit <input_oem|-> [OPTIONS]
plot-orbit orbit.oem
plot-orbit orbit.oem --duration 6h --time-unit minutes
```

## Options

| Option | Description |
|--------|-------------|
| `<input_oem|->` | Path to the input CCSDS OEM file. The parser accepts `-`, but the current plotting implementation reads a filesystem path. |
| `-o`, `--output <output_plot|->` | Base output image path. A suffix is added for each generated figure. |
| `-d`, `--duration <duration>` | Duration to analyze from the first OEM state, such as `1h`, `30m`, or `3600s`. If omitted, use the full history. |
| `--time-unit {m,minute,minutes,h,hour,hours}` | Unit for elapsed-time axes. Defaults to `hours`. |
| `-h`, `--help` | Show the help message and exit. |

## Input Data

The input must contain CCSDS OEM state vectors with Cartesian position and velocity values. The utility reads the states from a filesystem path, orders them by their source history, and uses the first state as the start of the elapsed-time axis.

The `--duration` value is parsed as a compact duration. Examples include:

- `30s` - 30 seconds
- `5m` - 5 minutes
- `2h` - 2 hours
- `1d` - 1 day
- `1h30m` - 1 hour and 30 minutes

States after the selected interval are excluded. If the interval contains no states, the command reports an error.

## Time Units

The `--time-unit` option controls elapsed-time axes in the generated time-series plots. The following spellings are equivalent:

- Minutes: `m`, `minute`, `minutes`
- Hours: `h`, `hour`, `hours`

The default is `hours`.

## Output Behavior

Without `--output`, the command opens the generated Matplotlib figures interactively. With `--output`, it saves each figure at 150 DPI using the supplied path stem and a diagnostic suffix.

For example:

```bash
plot-orbit orbit.oem -o figures/orbit.png
```

produces files with names like:

```text
figures/orbit_state_vectors.png
figures/orbit_rtn_deltas.png
figures/orbit_velocity_magnitude.png
figures/orbit_angular_velocity.png
figures/orbit_direction_change.png
figures/orbit_geocentric_distance.png
figures/orbit_altitude_wgs84.png
```

The output extension is taken from the supplied base path. Create the destination directory before running the command if it does not already exist.

## Generated Figures

The command generates the following diagnostic views:

1. **State vectors**: Cartesian position trajectory and component histories.
2. **RTN deltas**: Sample-to-sample position and velocity deltas in the local RTN frame.
3. **Velocity magnitude**: Speed in kilometers per second versus elapsed time.
4. **Angular velocity**: Angular-rate diagnostics in degrees per second and radians per second.
5. **Direction change**: Direction-change angles, rates, and Euler-angle-style direction series.
6. **Geocentric distance**: Distance from the geocenter and its change over time.
7. **WGS84 altitude**: Altitude above the WGS84 reference ellipsoid.

The RTN delta view requires more than one state. Short input files may therefore contain fewer samples in that figure than in the other views.

## Examples

**Plot the full orbit interactively:**

```bash
plot-orbit orbit.oem
```

**Analyze the first six hours using minutes on time-series axes:**

```bash
plot-orbit orbit.oem --duration 6h --time-unit minutes
```

**Save all diagnostic figures using an output prefix:**

```bash
plot-orbit orbit.oem --output orbit_plots.png
```

**Save a short analysis:**

```bash
plot-orbit orbit.oem -d 90m -o results/iss_90min.png
```

**Show command help:**

```bash
plot-orbit --help
```

## Requirements

Install the optional plotting dependencies before using the command:

```bash
pip install -e '.[plotting]'
```

The command uses Matplotlib for rendering and NumPy for numerical processing.

## Error Handling

Common failures include:

- The input path does not exist.
- The OEM contains no state data.
- The duration format is invalid.
- Duration filtering removes every state.
- The selected time-unit spelling is not supported.

The command reports input and processing progress on standard output and reports failures on standard error.

## Related Tools

- `plot-orbit-deltas` - Compare multiple orbit trajectories
- `plot-dependent-variables` - Plot dependent-variable histories from a Tudat CSV file
- `slice-oem` - Extract a time or index range from an OEM file
- `propagate-orbit` - Generate OEM data from perturbed orbit propagation

See [MISC.md](MISC.md) for miscellaneous utilities and [PROPAGATION.md](PROPAGATION.md) for propagation workflows.
