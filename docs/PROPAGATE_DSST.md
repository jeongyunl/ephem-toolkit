# DSST Propagator

## Overview

The DSST (Draper Semi-analytical Satellite Theory) propagator implements semi-analytical orbit propagation using mean Keplerian elements. It provides higher fidelity than two-body Kepler propagation while remaining significantly faster than full numerical integration.

**Algorithm:** Danielson et al. (1995) formulation  
**Coordinate Frame:** J2000  
**Element Type:** Classical Keplerian mean elements `[a, e, i, ω, Ω, M]`

---

## Mean Element Definition

DSST mean elements are **not interchangeable** with other mean element theories:

| Theory | Mean Element Definition |
|--------|------------------------|
| **DSST** | Averaged over short-period terms using J2, J3, J4 |
| Brouwer | Averaged using J2 short-period corrections only |
| SGP4/TLE | Empirically fitted to observations |
| Osculating | Instantaneous Keplerian elements |

Element ordering (same as tudatpy `element_conversion`):

| Index | Name | Units |
|-------|------|-------|
| 0 | a — Semi-major axis | m |
| 1 | e — Eccentricity | dimensionless |
| 2 | i — Inclination | rad |
| 3 | ω — Argument of periapsis | rad |
| 4 | Ω — RAAN | rad |
| 5 | M — Mean anomaly | rad |

---

## Perturbation Models

### Zonal Harmonics (J2, J3, J4)

Secular rates for Ω, ω, and M from Earth's oblateness:

- **J2** (default: enabled): Primary oblateness effect. Nodal regression, apsidal precession.
- **J3** (default: disabled): Odd zonal harmonic. Eccentricity-dependent corrections to ω and M.
- **J4** (default: disabled): Even zonal harmonic. Additional corrections to Ω, ω, and M.

### Atmospheric Drag

Exponential atmosphere model (King-Hele secular approximation):

- **Model:** `ρ = ρ₀ × exp(-(r - r₀) / H)`
  - Scale height H = 8500 m
  - Reference density ρ₀ = 2.62×10⁻¹⁰ kg/m³ at 400 km
- **Secular effects:** Semi-major axis decay (da/dt) and circularization (de/dt)
- **Ballistic coefficient:** B* = (Cd × A) / (2m)
- **Required parameters:** `drag_coeff`, `drag_area_m2`, `mass_kg`

### Validity Ranges

| Orbit Regime | Altitude | J2-only Accuracy | J2+J3+J4 Accuracy |
|-------------|----------|-----------------|-------------------|
| LEO | 400–2000 km | < 1 km/day | < 100 m/day |
| MEO | 2000–35000 km | < 500 m/day | < 200 m/day |
| GEO | ~35786 km | < 100 m/day | < 50 m/day |
| HEO | varies | varies by e | varies by e |

> **Note:** Accuracy degrades for near-circular (e < 1e-6) and near-equatorial (i < 1°) orbits due to classical element singularities.

---

## Python API

### DsstPerturbations

```python
from ephem_toolkit.core.propagator import DsstPerturbations

# J2-only (default)
pert = DsstPerturbations()

# J2 + J3 + J4
pert = DsstPerturbations(include_j2=True, include_j3=True, include_j4=True)

# With drag (ISS-like)
pert = DsstPerturbations(
    include_j2=True,
    include_drag=True,
    drag_coeff=2.2,
    drag_area_m2=2500.0,
    mass_kg=420000.0,
)
```

### DSSTPropagator

```python
import numpy as np
from ephem_toolkit.core.propagator import DSSTPropagator, DsstPerturbations, KeplerianState

# Define DSST mean elements at epoch
mean_elements = np.array([
    6778e3,           # a (m)
    0.0005,           # e
    np.radians(51.6), # i (rad)
    np.radians(30.0), # omega (rad)
    np.radians(45.0), # RAAN (rad)
    np.radians(10.0), # M (rad)
])
epoch_tt_s = 0.0  # TT seconds since J2000

state = KeplerianState(elements=mean_elements, epoch_s=epoch_tt_s)
pert = DsstPerturbations(include_j2=True, include_j3=True)

prop = DSSTPropagator(initial_state=state, perturbations=pert)

# Propagate to target epoch
target_tt_s = 3600.0
epoch, cartesian = prop.propagate_to(target_tt_s)
# cartesian: [x, y, z, vx, vy, vz] in m and m/s
```

### Conversion Functions

```python
from ephem_toolkit.core.propagator import dsst_mean_to_osculating, osculating_to_dsst_mean

# Osculating → DSST mean
mean = osculating_to_dsst_mean(osculating_elements, epoch_s=0.0)

# DSST mean → Osculating
osculating = dsst_mean_to_osculating(mean_elements, epoch_s=0.0)
```

---

## CLI Usage (propagate-omm)

DSST propagation is automatically selected when `MEAN_ELEMENT_THEORY = DSST` in the OMM file.

### Example OMM with DSST Elements

```
CCSDS_OMM_VERS = 3.0
CREATION_DATE  = 2024-01-01T00:00:00.000
ORIGINATOR     = ephem-toolkit

OBJECT_NAME    = ISS
OBJECT_ID      = 1998-067A
CENTER_NAME    = EARTH
REF_FRAME      = J2000
TIME_SYSTEM    = UTC
MEAN_ELEMENT_THEORY = DSST

EPOCH          = 2024-01-01T00:00:00.000000
MEAN_MOTION    = 15.49 [rev/day]
ECCENTRICITY   = 0.0005
INCLINATION    = 51.6 [deg]
RA_OF_ASC_NODE = 45.0 [deg]
ARG_OF_PERICENTER = 30.0 [deg]
MEAN_ANOMALY   = 10.0 [deg]

MASS           = 420000.0 [kg]
DRAG_AREA      = 2500.0 [m**2]
DRAG_COEFF     = 2.2
```

### Propagate Command

```bash
propagate-omm iss_dsst.omm --stop 1d --step 300s -o iss_dsst.oem
```

Spacecraft parameters (`MASS`, `DRAG_AREA`, `DRAG_COEFF`) are automatically parsed from the OMM to configure drag perturbations.

---

## Comparison with Other Propagators

| Propagator | Fidelity | Speed | Use Case |
|-----------|---------|-------|----------|
| Kepler | Low | Fastest | Short arcs, GEO |
| Brouwer | Medium | Fast | LEO, J2 effects |
| **DSST** | **Medium-High** | **Fast** | **LEO/MEO, J2+J3+J4+drag** |
| SGP4 | Medium | Fast | TLE-based, LEO |
| Numerical | High | Slow | High-fidelity, all regimes |

### When to Use DSST

- Need higher fidelity than Brouwer (J3/J4 effects matter)
- Have DSST mean elements from an orbit determination system
- Want drag effects without full numerical integration
- Propagating LEO satellites over days to weeks

### When NOT to Use DSST

- Near-circular orbits (e < 1e-6): use equinoctial elements
- Near-equatorial orbits (i < 1°): use equinoctial elements
- Need covariance propagation: use numerical + STM
- Have TLE data: use SGP4

---

## References

1. Danielson, D.A., et al. "Semianalytic Satellite Theory", Naval Research Laboratory, 1995.
2. Vallado, D.A. "Fundamentals of Astrodynamics and Applications", 4th ed., Ch. 9.
3. King-Hele, D.G. "Satellite Orbits in an Atmosphere", 1987.
4. CCSDS 502.0-B-3 "Orbit Mean-Elements Message (OMM)", 2023-04.
