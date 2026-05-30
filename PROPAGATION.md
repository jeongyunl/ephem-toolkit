# tudatpy-utils

Utility scripts for working with TudatPy.

## Propagation

### `propagation/propagate_satellite_orbit.py`

Propagates a perturbed satellite orbit around Earth using TudatPy. The script reads a single OEM-style state line (epoch + Cartesian position/velocity) and propagates it forward in time under a configurable set of perturbations including spherical-harmonic gravity, third-body gravity (Sun, Moon, Mars, Venus), aerodynamic drag, and solar radiation pressure (SRP). Post-propagation plots of total acceleration, ground track, Keplerian elements, and individual acceleration contributions are displayed automatically.

#### Synopsis

```
python propagation/propagate_satellite_orbit.py [-h] [-i INITIAL_STATE] -d DURATION
    [--name NAME] [--mass MASS] [--drag on|off] [--drag-coeff CD] [--drag-area AREA]
    [--sun-gravity on|off] [--moon-gravity on|off] [--mars-gravity on|off]
    [--venus-gravity on|off] [--srp on|off] [--srp-coeff CR]
```

#### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-i`, `--initial-state` | One OEM-style state line provided directly on the command line. If omitted, one line is read from stdin. |
| `-d`, `--duration` | Simulation duration (required). Accepts a number optionally followed by a unit suffix: `s` (seconds, default), `m` (minutes), `h` (hours), `d` (days). E.g. `90`, `90s`, `2m`, `1.5h`, `1d`. |
| `--name` | Name of the propagated satellite body (default: `Satellite`). |
| `--mass` | Mass of the satellite in kilograms (default: `30`). |
| `--drag` | Enable or disable aerodynamic drag acceleration. Accepts `on`/`off`, `true`/`false`, `yes`/`no`, `enable`/`disable` (default: `on`). |
| `--drag-coeff` | Drag coefficient Cd of the satellite (default: `2.2`). |
| `--drag-area` | Drag / average projection area of the satellite in m² (default: `0.18`, based on a 3U CubeSat). |
| `--sun-gravity` | Enable or disable Sun point-mass gravity perturbation (default: `on`). |
| `--moon-gravity` | Enable or disable Moon point-mass gravity perturbation (default: `on`). |
| `--mars-gravity` | Enable or disable Mars point-mass gravity perturbation (default: `on`). |
| `--venus-gravity` | Enable or disable Venus point-mass gravity perturbation (default: `on`). |
| `--srp` | Enable or disable solar radiation pressure acceleration (default: `on`). |
| `--srp-coeff` | Solar radiation pressure coefficient Cr of the satellite (default: `1.2`). |

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

The script prints a pre-propagation configuration summary to stdout and, after propagation, displays four matplotlib plots:

1. **Total acceleration norm** over time.
2. **Ground track** (latitude vs. longitude) for the first 3 hours.
3. **Keplerian elements** (semi-major axis, eccentricity, inclination, argument of periapsis, RAAN, true anomaly) over time.
4. **Acceleration components** (norms by type and source body, log scale) over time.

#### Propagation Model

- **Central body gravity**: Earth spherical harmonics up to degree and order 5.
- **Third-body gravity**: Sun, Moon, Mars, Venus point-mass gravity (each individually toggleable).
- **Aerodynamic drag**: Earth atmosphere drag using a constant drag coefficient and reference area (toggleable).
- **Solar radiation pressure**: Cannonball SRP model with Earth as an occulting body (toggleable).
- **Integrator**: Fixed-step RK4 with a 10 s step size.
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

**Show help:**

```bash
python propagation/propagate_satellite_orbit.py -h
```

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy
- Matplotlib

The script automatically loads the required SPICE kernels (`naif0012.tls`, `pck00011.tpc`, `gm_de431.tpc`, `earth_200101_990825_predict.bpc`, and `tudat_merged_spk_kernel.bsp`) from the TudatPy data directory.

---
