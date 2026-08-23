# Orbit-Difference Plotting Utility

The `plot-orbit-deltas` utility plots multiple orbit trajectories and compares them using orbit views and RTN coordinates.

## Synopsis

```bash
plot-orbit-deltas <input_oem> [<input_oem> ...] [OPTIONS]
```

The first input file is the reference orbit. One or more additional files may be supplied for comparison.

## Overview

This utility provides several views for comparing orbit trajectories:

- **Trajectory views**: Plot all input orbits in multiple Cartesian projections.
- **Cartesian deltas**: Show relative position and velocity differences by component.
- **RTN deltas**: Show relative differences in the radial-transverse-normal frame.
- **Duration filtering**: Analyze the full history or only an initial interval.
- **Flexible display**: Show figures interactively or save them using an output path.

## Options

| Option | Description |
|--------|-------------|
| `<input_oem> ...` | One or more OEM or raw-state files. The first file is the reference orbit. |
| `-o`, `--output <output_plot>` | Output path for saving the figure. |
| `-d`, `--duration <duration>` | Duration to analyze from the start, such as `1h`, `30m`, or `3600s`. |
| `--time-unit {m,minute,minutes,h,hour,hours}` | Time unit for time-series plots. Defaults to `hours`. |
| `-h`, `--help` | Show the help message and exit. |

## Examples

```bash
plot-orbit-deltas reference.oem
plot-orbit-deltas reference.oem comparison1.oem comparison2.oem
plot-orbit-deltas reference.oem comparison.oem -o orbits.png
plot-orbit-deltas reference.oem comparison.oem -d 2h --time-unit minutes
```

## Behavior

- Reads one or more OEM or raw-state files.
- Treats the first file as the reference orbit.
- Treats remaining files as comparison orbits.
- Generates multiple plots comparing the trajectories in Cartesian and RTN coordinates.
- Supports optional duration filtering and time-unit selection.

## Input Data

Inputs may be CCSDS OEM files or raw state files supported by the plotting implementation. The first file establishes the reference trajectory; subsequent files are plotted for comparison.

Raw state-vector files use the following format:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

## Output Behavior

Without `--output`, figures are displayed interactively. With an output path, the generated figure is saved using that path. The `--duration` option limits the analyzed history from the first state.

The generated views include:

1. **3D Orbit Trajectory**.
2. **XY Plane**.
3. **XZ Plane**.
4. **YZ Plane**.
5. **Relative Position Delta (Cartesian)**.
6. **Relative Velocity Delta (Cartesian)**.
7. **Relative Position Delta (RTN)**.
8. **Relative Velocity Delta (RTN)**.
9. **Relative Position Delta: Radial-Transverse**.
10. **Relative Position Delta: Radial-Normal**.
11. **Relative Velocity Delta: Radial-Transverse**.
12. **Relative Velocity Delta: Radial-Normal**.

When `--output` is provided, figures are saved with diagnostic suffixes, such as `orbits_relative_rtn_timeseries.png`. Otherwise, they are displayed interactively.

## Usage

**Plot a single orbit:**

```bash
plot-orbit-deltas reference.oem
```

**Plot reference and comparison orbits:**

```bash
plot-orbit-deltas reference.oem comparison1.oem comparison2.oem
```

**Save output to files:**

```bash
plot-orbit-deltas reference.oem comparison.oem -o orbits.png
```

**Analyze only the first two hours:**

```bash
plot-orbit-deltas reference.oem comparison.oem -d 2h
```

**Use minutes for time-series axes:**

```bash
plot-orbit-deltas reference.oem comparison.oem --time-unit minutes
```

**Show help:**

```bash
plot-orbit-deltas -h
```

## Dependencies

- NumPy.
- Matplotlib.
- `ephem_toolkit.core.common`.
- `ephem_toolkit.core.time_utils`.
- `ephem_toolkit.core.ccsds.oem`.
- `ephem_toolkit.core.interpolator.lagrange`.

## Related Tools

- `diff-oem` - Report numerical differences between two OEM histories.
- `plot-orbit` - Produce diagnostic plots for one OEM orbit.
- `slice-oem` - Extract a subset of an OEM history.

See [MISC.md](MISC.md) for the grouped orbit-analysis utilities.
