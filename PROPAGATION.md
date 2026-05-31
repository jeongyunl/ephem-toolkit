# tudatpy-utils

Utility scripts for working with TudatPy.

## Propagation

### Available Scripts

- [propagation/propagate_satellite_orbit.py](#propagationpropagate_satellite_orbitpy)
- [propagation/propagate_tle.py](#propagationpropagate_tlepy)

### `propagation/propagate_satellite_orbit.py`

Propagates a perturbed satellite orbit around Earth using TudatPy. The script reads a single OEM-style state line (epoch + Cartesian position/velocity) and propagates it forward in time under a configurable set of perturbations including spherical-harmonic gravity, third-body gravity (Sun, Moon, Mars, Venus), aerodynamic drag, and solar radiation pressure (SRP). Post-propagation plots of total acceleration, ground track, Keplerian elements, and individual acceleration contributions are displayed automatically.

#### Synopsis

```
python3 propagation/propagate_satellite_orbit.py [-h] [-i <oem_state_line>] [-d <value[s|m|h|d]>] [-o <file|->]
  [--name <name>] [--mass <kg>]
  [--integrator <rk_3|rk_4|rkf_45|rkf_56|rkf_78|rkf_89|rkf_108|rkf_1210|rkf_1412|rkdp_87|rkv_89>]
  [--integrator-step-size <fixed|init,max|init,min,max>] [--earth-gravity <DxO>] [--drag-area <m^2>]
  [--srp <on|off>] [--srp-coeff <coefficient>] [--drag <on|off>] [--drag-coeff <coefficient>]
  [--moon-gravity <on|off>] [--sun-gravity <on|off>] [--venus-gravity <on|off>] [--mars-gravity <on|off>]
```

#### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | None |
| `-i`, `--initial-state` | One OEM-style state line provided directly on the command line. If omitted, one line is read from stdin. | stdin (when piped) |
| `-d`, `--duration` | Simulation duration. Accepts a number optionally followed by a unit suffix: `s` (seconds, default), `m` (minutes), `h` (hours), `d` (days). E.g. `90`, `90s`, `2m`, `1.5h`, `1d`. | `1d` |
| `-o`, `--output` | Write propagated state history in OEM-like format. Use `-` to write to stdout; otherwise provide a file path. If omitted, no state-history output is written. | None |
| `--name` | Name of the propagated satellite body. | `Satellite` |
| `--mass` | Mass of the satellite in kilograms. | `30` |
| `--integrator` | Integrator method identifier. Supported methods: `rk_3`, `rk_4`, `rkf_45`, `rkf_56`, `rkf_78`, `rkf_89`, `rkf_108`, `rkf_1210`, `rkf_1412`, `rkdp_87`, `rkv_89`. | `rk_4` |
| `--integrator-step-size` | Integrator step size specification in seconds as one token. Forms: `<fixed>`, `<init,max>`, or `<init,min,max>`. | `10` |
| `--earth-gravity` | Earth spherical harmonic gravity degree/order in `DxO` format (e.g. `5x5`, `8x6`). | `5x5` |
| `--drag-area` | Drag / average projection area of the satellite in m² (based on a 3U CubeSat). | `0.18` |
| `--srp` | Enable or disable solar radiation pressure acceleration. | `on` |
| `--srp-coeff` | Solar radiation pressure coefficient Cr of the satellite. | `1.2` |
| `--drag` | Enable or disable aerodynamic drag acceleration. Accepts `on`/`off`, `true`/`false`, `yes`/`no`, `enable`/`disable`. | `on` |
| `--drag-coeff` | Drag coefficient Cd of the satellite. | `2.2` |
| `--moon-gravity` | Enable or disable Moon point-mass gravity perturbation. | `on` |
| `--sun-gravity` | Enable or disable Sun point-mass gravity perturbation. | `on` |
| `--venus-gravity` | Enable or disable Venus point-mass gravity perturbation. | `on` |
| `--mars-gravity` | Enable or disable Mars point-mass gravity perturbation. | `on` |

#### Input Format

The script reads exactly one OEM-style state record with 7 whitespace-separated fields:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

- **Epoch**: ISO 8601 timestamp (e.g., `2026-05-29T00:00:00.000000`).
- **Position**: X, Y, Z in **kilometres**.
- **Velocity**: VX, VY, VZ in **km/s**.

The state is provided either via the `--initial-state`/`-i` option or piped through stdin.

#### Output

The script prints a pre-propagation configuration summary to stdout and, after
propagation, displays five matplotlib plots.

When `-o/--output` is provided, the propagated state history is also exported in
OEM-like text format:

```
<ISO-8601 UTC epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

`--output -` writes this export to stdout.

The pre-propagation summary includes:

1. Selected force-model and integrator options.
2. Initial epoch.
3. Initial position vector `[m]`.
4. Initial velocity vector `[m/s]`.
5. Simulation duration and end epoch.

The plots are:

1. **Total acceleration norm** over time.
2. **Ground track** (latitude vs. longitude) for the first 3 hours.
3. **Keplerian elements** (semi-major axis, eccentricity, inclination, argument of periapsis, RAAN, true anomaly) over time.
4. **Acceleration components** (norms by type and source body, log scale) over time.
5. **3D state history** (cartesian trajectory around an Earth sphere).

#### Propagation Model

- **Central body gravity**: Earth spherical harmonics with configurable degree/order (`--earth-gravity`, default `5x5`).
- **Third-body gravity**: Sun, Moon, Mars, Venus point-mass gravity (each individually toggleable).
- **Aerodynamic drag**: Earth atmosphere drag using a constant drag coefficient and reference area (toggleable).
- **Solar radiation pressure**: Cannonball SRP model with Earth as an occulting body (toggleable).
- **Integrator**: Configurable Runge-Kutta method (`--integrator`) with fixed-step or variable-step size (`--integrator-step-size`).
- **Default integrator setup**: Fixed-step RK4 with a 10 s step size.
- **Reference frame**: J2000 inertial, centred on Earth.

#### Usage

**Propagate from inline state for 1 day (all perturbations on by default):**

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

**Propagate with drag and SRP disabled:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 1d --drag off --srp off \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Propagate with custom satellite properties:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 12h --name MySat --mass 500 --drag-coeff 2.5 --drag-area 0.5 --srp-coeff 1.5 \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Propagate with a variable-step RKF 7(8) integrator and custom Earth gravity:**

```bash
python propagation/propagate_satellite_orbit.py \
  -d 12h --integrator rkf_78 --integrator-step-size 30,0.001,1000 --earth-gravity 8x8 \
  -i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Show help:**

```bash
python propagation/propagate_satellite_orbit.py -h
```

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy
- Matplotlib

The script automatically loads the required SPICE kernels (`naif0012.tls`, `pck00011.tpc`, `gm_de431.tpc`, `earth_200101_990825_predict.bpc`, and `tudat_merged_spk_kernel.bsp`) from the TudatPy data directory.

### `propagation/propagate_tle.py`

Propagates a TLE-derived orbit using TudatPy's SGP4 TLE ephemeris and prints
state vectors in OEM-like text format. Input can be provided as a TLE file
path or as raw TLE text from stdin.

#### Synopsis

```
python3 propagation/propagate_tle.py [-h] [-d <value[s|m|h|d]>] [-s <value[s|m]>] [--oem] [<tle_file>]
```

#### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | None |
| `<tle_file>` | Path to a TLE file. If omitted, TLE text is read from stdin. | stdin (when piped) |
| `-d`, `--duration` | Propagation duration. Accepts a number optionally followed by `s` (seconds, default), `m` (minutes), `h` (hours), or `d` (days). E.g. `90`, `90s`, `2m`, `1.5h`, `1d`. | `1d` |
| `-s`, `--step` | Output interval. Accepts a number optionally followed by `s` (seconds, default) or `m` (minutes). E.g. `60`, `60s`, `15m`. | `15m` |
| `--oem` | Print OEM metadata header before state lines. If omitted, only propagated state lines are printed. | off |

#### Input Format

The script consumes one TLE line pair (`line 1` and `line 2`) as follows:

1. If `<tle_file>` is provided, the final two non-empty lines of the file are used.
2. If `<tle_file>` is omitted, stdin is read and the final two non-empty lines are used.

The selected pair must start with `1 ` and `2 ` respectively.

#### Output

By default, the script prints only propagated state lines:

```
<ISO-8601 UTC epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

- Epoch is printed as an ISO-like UTC timestamp (without a trailing `Z`).
- Position is in kilometres.
- Velocity is in km/s.

When `--oem` is provided, an OEM metadata header is printed before the state
lines.

#### Usage

**Propagate from a TLE file for 1 day with 15-minute output step (defaults):**

```bash
python propagation/propagate_tle.py tle/ISS-(ZARYA)_1998-067A.tle
```

**Propagate from stdin TLE content for 2 hours with 1-minute step:**

```bash
cat tle/ISS-(ZARYA)_1998-067A.tle | python propagation/propagate_tle.py -d 2h -s 1m
```

**Propagate for 30 minutes with 10-second output step:**

```bash
python propagation/propagate_tle.py tle/ISS-(ZARYA)_1998-067A.tle -d 30m -s 10s
```

**Print full OEM-style output including header:**

```bash
python propagation/propagate_tle.py tle/ISS-(ZARYA)_1998-067A.tle --oem
```

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)

The script loads required SPICE kernels (`naif0012.tls` and `pck00011.tpc`)
from the TudatPy data directory.

---
