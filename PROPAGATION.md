# tudatpy-utils

Propagation utilities for OEM-like Cartesian states and TLEs.

## Available scripts

- `propagation/propagate_satellite_orbit.py`
- `propagation/propagate_tle.py`

## `propagation/propagate_satellite_orbit.py`

Propagates a perturbed satellite orbit around Earth using TudatPy. The script reads a single OEM-like state line containing epoch plus Cartesian position and velocity, then propagates it forward under a configurable set of perturbations including spherical-harmonic Earth gravity, third-body gravity, aerodynamic drag, and solar radiation pressure. Post-propagation plots are displayed automatically.

### Synopsis

```bash
python propagation/propagate_satellite_orbit.py [-h] [-i <oem_state_line>] [-d <value[s|m|h|d]>] [-o <file|->]
  [--name <name>] [--mass <kg>]
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
| `-o`, `--output` | Write propagated state history in OEM-like format to a file, or `-` for stdout | no export |
| `--name` | Name of the propagated satellite body | `Satellite` |
| `--mass` | Satellite mass in kg | `30` |
| `--integrator` | Integrator method identifier | `rk_4` |
| `--integrator-step-size` | One, two, or three comma-separated step-size values in seconds | `10` |
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

If `-o/--output` is provided, it also writes propagated state history in OEM-like text format:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

If `--output -` is used, the state history is written to stdout.

The pre-propagation summary includes:

1. selected force-model and integrator options
2. initial epoch
3. initial position vector
4. initial velocity vector
5. simulation duration and end epoch
6. output destination when state-history export is enabled

After propagation, the script displays plots using Matplotlib. The current source generates:

1. Total acceleration norm over time
2. Ground track
3. Keplerian elements over time
4. Acceleration-component norms by source/type
5. Animated 3D trajectory in Earth-fixed coordinates
6. Static 3D state history in the inertial frame

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
- the default integrator setup is fixed-step RK4 with a 10 s step size

### Usage

**Propagate from inline state for 1 day:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 1d \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Propagate from stdin for 2 hours:**

```bash
echo "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217" \
  | python propagation/propagate_satellite_orbit.py -d 2h
```

**Disable drag and SRP:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 1d --drag off --srp off \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Use custom satellite properties:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 12h --name MySat --mass 500 --drag-coeff 2.5 --drag-area 0.5 --srp-coeff 1.5 \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Export propagated state history to a file:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 6h -o propagated.oem \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Write propagated state history to stdout:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 30m -o - \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Use a variable-step RKF 7(8) integrator:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 12h --integrator rkf_78 --integrator-step-size 30,0.001,1000 --earth-gravity 8x8 \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Show help:**

```bash
python propagation/propagate_satellite_orbit.py -h
```

### Dependencies

- TudatPy
- NumPy
- Matplotlib
- local helper module `common.common`

The script loads these SPICE kernels from TudatPy's SPICE kernel directory:

- `naif0012.tls`
- `pck00011.tpc`
- `gm_de431.tpc`
- `earth_200101_990825_predict.bpc`
- `tudat_merged_spk_kernel.bsp`

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

The script loads these SPICE kernels via TudatPy data paths:

- `naif0012.tls`
- `pck00011.tpc`
