# tudatpy-utils

Propagation utilities for OEM-like Cartesian states and TLEs.

## Available scripts

- `propagation/propagate_orbit.py`
- `propagation/plot_dependent_variables.py`
- `propagation/propagate_tle.py`

## `propagation/propagate_orbit.py`

Propagates a perturbed satellite orbit around Earth using TudatPy. The script reads a single OEM-like state line containing epoch plus Cartesian position and velocity, then propagates it forward under a configurable set of perturbations including spherical-harmonic Earth gravity, third-body gravity, aerodynamic drag, and solar radiation pressure.

### Synopsis

```bash
python propagation/propagate_orbit.py [-h] [-i <oem_state_line>] [-d <value[s|m|h|d]>] [--oem <file|->]
  [--raw <file|->] [--dep-vars <file>] [--oem-step-size <value[s|m]>] [--name <name>] [--mass <kg>]
  [--integrator <rk_3|rk_4|rkf_45|rkf_56|rkf_78|rkf_89|rkf_108|rkf_1210|rkf_1412|rkdp_87|rkv_89>]
  [--integrator-step-size <fixed|init,max|init,min,max>] [--earth-gravity <DxO>] [--drag-area <m^2>]
  [--srp <on|off>] [--srp-coeff <coefficient>] [--drag <on|off>] [--drag-coeff <coefficient>]
  [--moon-gravity <on|off>] [--sun-gravity <on|off>] [--venus-gravity <on|off>] [--mars-gravity <on|off>]
```

### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | none |
| `-i`, `--initial-state` | One OEM-like state line provided directly on the command line. If omitted, one line is read from stdin. | stdin when piped |
| `-d`, `--duration` | Simulation duration in `s`, `m`, `h`, or `d` units | `1d` |
| `--oem` | Write propagated state history in CCSDS OEM format to a file, or `-` for stdout | no OEM export |
| `--raw` | Write propagated state history as raw state-vector lines to a file, or `-` for stdout | no raw export |
| `--dep-vars` | Write dependent variables to a CSV file | `dep_vars.csv` only when no other output option is provided |
| `--oem-step-size` | OEM output sampling step size in `s` or `m` units | `10m` |
| `--name` | Name of the propagated satellite body | `Satellite` |
| `--mass` | Satellite mass in kg | `30` |
| `--integrator` | Integrator method identifier | `rkdp_87` |
| `--integrator-step-size` | One, two, or three comma-separated step-size values in seconds | `10,1,300` |
| `--earth-gravity` | Earth spherical-harmonic gravity degree/order in `DxO` format | `5x5` |
| `--drag-area` | Drag area / average projection area in m² | `0.18` |
| `--srp` | Enable or disable solar radiation pressure | `on` |
| `--srp-coeff` | Solar radiation pressure coefficient | `1.2` |
| `--drag` | Enable or disable aerodynamic drag | `on` |
| `--drag-coeff` | Drag coefficient | `2.2` |
| `--moon-gravity` | Enable or disable Moon point-mass gravity | `on` |
| `--sun-gravity` | Enable or disable Sun point-mass gravity | `on` |
| `--venus-gravity` | Enable or disable Venus point-mass gravity | `on` |
| `--mars-gravity` | Enable or disable Mars point-mass gravity | `on` |

### Integrator step-size forms

The current parser accepts:

- `<fixed>`
- `<initial_and_minimum>,<maximum>`
- `<initial>,<minimum>,<maximum>`

Examples:

- `10`
- `0.001,1000`
- `30,0.001,1000`

### Input format

The script expects exactly one OEM-like state line:

```text
<ISO-8601 epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

Notes:

- **Epoch**: ISO 8601 timestamp such as `2026-05-29T00:00:00.000000`
- **Position**: X, Y, Z in km
- **Velocity**: VX, VY, VZ in km/s
- Input is taken from `--initial-state` if provided; otherwise one line is read from stdin.
- If neither source is available, the script exits with an error.

### Output

The script always prints a pre-propagation configuration summary to stdout.

If `--oem` is provided, it writes propagated state history in CCSDS OEM format.
If `--raw` is provided, it writes propagated state history as raw state-vector lines:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

For both `--oem` and `--raw`, using `-` writes the selected output stream to stdout.

If `--dep-vars <file>` is provided, dependent variables are written to a CSV file.
If no output option is provided at all, the script preserves its default behavior by writing dependent variables to `dep_vars.csv`.

The pre-propagation summary includes:

1. selected force-model and integrator options
2. initial epoch
3. initial position vector
4. initial velocity vector
5. simulation duration and end epoch
6. configured output destinations when export is enabled

### Propagation model

Current force-model behavior from the source:

- Earth spherical-harmonic gravity is always included
- Sun point-mass gravity is optional
- Moon point-mass gravity is optional
- Venus point-mass gravity is optional
- Mars point-mass gravity is optional
- Aerodynamic drag is optional
- Solar radiation pressure is optional

Environment/body setup behavior:

- `Sun` and `Earth` are always created
- `Moon`, `Mars`, and `Venus` are created only when their gravity perturbations are enabled
- The global frame is Earth-centered `J2000`

Additional implementation notes:

- the propagated satellite mass is configurable with `--mass`
- the drag area is reused as the cannonball reference area for SRP in the current implementation
- fixed-step integration is used when one step-size value is provided
- variable-step integration is used when two or three step-size values are provided
- the default integrator setup is variable-step Dormand-Prince 8(7) with step sizes (initial=10, minimum=1, maximum=300) seconds

### Usage

**Propagate from inline state for 1 day:**

```bash
python propagation/propagate_orbit.py \
  -d 1d \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Propagate from stdin for 2 hours:**

```bash
echo "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217" \
  | python propagation/propagate_orbit.py -d 2h
```

**Disable drag and SRP:**

```bash
python propagation/propagate_orbit.py \
  -d 1d --drag off --srp off \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Use custom satellite properties:**

```bash
python propagation/propagate_orbit.py \
  -d 12h --name MySat --mass 500 --drag-coeff 2.5 --drag-area 0.5 --srp-coeff 1.5 \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Export propagated state history as CCSDS OEM:**

```bash
python propagation/propagate_orbit.py \
  -d 6h --oem propagated.oem \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Write raw propagated state history to stdout:**

```bash
python propagation/propagate_orbit.py \
  -d 30m --raw - \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Write dependent variables to CSV:**

```bash
python propagation/propagate_orbit.py \
  -d 6h --dep-vars dep_vars.csv \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Plot dependent variables from CSV:**

```bash
python propagation/plot_dependent_variables.py dep_vars.csv
```

**Use a variable-step RKF 7(8) integrator:**

```bash
python propagation/propagate_orbit.py \
  -d 12h --integrator rkf_78 --integrator-step-size 30,0.001,1000 --earth-gravity 8x8 \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Show help:**

```bash
python propagation/propagate_orbit.py -h
```

### Dependencies

- TudatPy
- NumPy
- Matplotlib
- local helper modules `common.common`, `common.time_utils`

The script loads these SPICE kernels from TudatPy's SPICE kernel directory:

- `naif0012.tls`
- `pck00011.tpc`
- `gm_de431.tpc`
- `earth_200101_990825_predict.bpc`
- `tudat_merged_spk_kernel.bsp`

## `propagation/plot_dependent_variables.py`

Plots dependent-variable histories from a saved Tudat CSV file. The script reads the dependent-variable CSV produced by `propagate_orbit.py` and recreates the standard dependent-variable plots, including total acceleration, ground track, Keplerian elements, acceleration-component norms, and animated 3D trajectory views.

### Synopsis

```bash
python propagation/plot_dependent_variables.py [-h] [--name <name>] [-d <duration>] <dep_vars_csv>
```

### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | none |
| `<dep_vars_csv>` | Path to the dependent-variable CSV file produced by `propagate_orbit.py` | none |
| `--name` | Satellite name used in plot labels and CSV header filtering. Auto-detected from CSV if not provided. | `Satellite` |
| `-d`, `--duration` | Duration to plot in format `<number>[s\|m\|h\|d]` (e.g., `1h`, `30m`, `3600s`). If not specified, plots all data. | all data |

### Input format

The script expects a dependent-variable CSV file whose first header column is:

```text
epoch_tdb_s
```

All remaining columns are dependent-variable data columns encoded using slash-separated metadata fields written by `propagate_orbit.py`.

Validation rules:

- the CSV file must not be empty
- the header row must be present
- the first header column must be `epoch_tdb_s`
- each non-empty data row must have the same number of columns as the header
- all data values must be numeric

### Output

The script opens Matplotlib figures and animations for the loaded dependent-variable history.

Current plots generated from the CSV are:

1. total acceleration norm over time
2. ground track
3. Keplerian elements over time
4. acceleration-component norms by source/type
5. animated 3D trajectory in Earth-fixed coordinates
6. animated 3D relative trajectory around Earth

The script does not write new files. It reads the CSV, creates figures, and displays them with Matplotlib.

### Usage

**Plot dependent variables from a CSV file:**

```bash
python propagation/plot_dependent_variables.py dep_vars.csv
```

**Plot using a custom satellite name for labels/header filtering:**

```bash
python propagation/plot_dependent_variables.py --name MySat dep_vars.csv
```

**Plot only the first hour of data:**

```bash
python propagation/plot_dependent_variables.py -d 1h dep_vars.csv
```

**Plot only the first 30 minutes:**

```bash
python propagation/plot_dependent_variables.py -d 30m dep_vars.csv
```

**Plot with custom satellite name and duration:**

```bash
python propagation/plot_dependent_variables.py --name ISS_prop -d 2h dep_vars.csv
```

**Generate the CSV and then plot it:**

```bash
python propagation/propagate_orbit.py \
  -d 6h --dep-vars dep_vars.csv \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
python propagation/plot_dependent_variables.py dep_vars.csv
```

**Show help:**

```bash
python propagation/plot_dependent_variables.py -h
```

### Dependencies

- NumPy
- Matplotlib
- Python standard library

## `propagation/propagate_tle.py`

Propagates a TLE-derived orbit using TudatPy's SGP4 TLE ephemeris and prints state vectors in OEM-like text format. Input can be provided as a TLE file path or as raw TLE text from stdin.

### Synopsis

```bash
python propagation/propagate_tle.py [-h] [-d <value[s|m|h|d]>] [-s <value[s|m]>] [--oem] [<tle_file>]
```

### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | none |
| `<tle_file>` | Path to a TLE file. If omitted, TLE text is read from stdin. | stdin when piped |
| `-d`, `--duration` | Propagation duration in `s`, `m`, `h`, or `d` units | `1d` |
| `-s`, `--step` | Output interval in `s` or `m` units | `15m` |
| `--oem` | Print an OEM metadata header before the state lines | off |

### Input format

The script uses the final two non-empty lines of the input source as the TLE pair.

Accepted sources:

1. A positional TLE file path
2. Raw TLE text from stdin

Validation rules:

- the selected pair must start with `1 ` and `2 ` respectively
- at least two non-empty lines must be present

For file input, the object name used in OEM metadata is the file stem.
For stdin input, the object name is `TLE_STDIN`.

### Output

Without `--oem`, the script prints only state lines:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

With `--oem`, the script prepends an OEM-like metadata block containing fields such as:

- `CCSDS_OEM_VERS`
- `CREATION_DATE`
- `ORIGINATOR`
- `OBJECT_NAME`
- `OBJECT_ID`
- `CENTER_NAME`
- `REF_FRAME`
- `TIME_SYSTEM`
- `START_TIME`
- `STOP_TIME`

Current implementation details:

- `REF_FRAME = EME2000`
- `TIME_SYSTEM = UTC`
- epochs are printed with a trailing `Z`
- position is printed in km
- velocity is printed in km/s

### Usage

**Propagate from a sample TLE file in `test/`:**

```bash
python propagation/propagate_tle.py test/ISS-ZARYA_1998-067A.tle
```

**Propagate from stdin for 2 hours with 1-minute output step:**

```bash
cat test/ISS-ZARYA_1998-067A.tle | python propagation/propagate_tle.py -d 2h -s 1m
```

**Propagate for 30 minutes with 10-second output step:**

```bash
python propagation/propagate_tle.py test/ISS-ZARYA_1998-067A.tle -d 30m -s 10s
```

**Print OEM metadata header plus state lines:**

```bash
python propagation/propagate_tle.py test/ISS-ZARYA_1998-067A.tle --oem
```

**Show help:**

```bash
python propagation/propagate_tle.py -h
```

### Dependencies

- TudatPy
- Python standard library
- local helper modules `common.common`, `common.time_utils`

The script loads these SPICE kernels via TudatPy data paths:

- `naif0012.tls`
- `pck00011.tpc`
