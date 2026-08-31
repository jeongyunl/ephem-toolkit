
# Orbit File Conversion Guide

This document provides guidance for converting between different orbit file formats: TLE, OEM, OMM, and OPM. It covers conversion methods, metadata handling, available tools, and known limitations.

---

## Format Characteristics

### TLE
- **Fixed format**: 2-line ASCII with checksums
- **Implicit frame**: TEME of Date, Earth-centered, UTC
- **Mean elements**: SGP4 propagation model
- **No covariance**: No uncertainty information
- **No maneuvers**: Single epoch state only

### OPM (Orbit Parameter Message)
- **Osculating elements**: Instantaneous Keplerian state
- **Cartesian state**: Position and velocity vectors (mandatory)
- **Maneuver support**: Multiple maneuvers with delta-V
- **Covariance**: Optional 6×6 position/velocity covariance
- **Flexible frames**: Multiple reference frames supported

### OMM (Orbit Mean-Elements Message)
- **Mean elements**: Designed for TLE compatibility
- **Theory-specific**: Requires MEAN_ELEMENT_THEORY (SGP4, DSST, etc.)
- **TLE parameters**: Includes BSTAR, element set number, etc.
- **No maneuvers**: Not supported
- **Covariance**: Optional 6×6 position/velocity covariance

### OEM (Orbit Ephemeris Message)
- **Time series**: Multiple state vectors over time range
- **Cartesian only**: No Keplerian elements
- **Interpolation**: Supports various interpolation methods
- **Covariance**: Optional position/velocity covariance matrices
- **Acceleration**: Optional acceleration data
- **No maneuvers**: State history only

---

## Format Selection Guide

| Use Case | Recommended Format |
|----------|-------------------|
| Space Surveillance Network data | TLE |
| High-precision orbit determination | OPM |
| Mean element propagation | OMM |
| Ephemeris time series | OEM |
| Maneuver planning | OPM |
| Uncertainty propagation | OPM or OMM (with covariance) |
| Legacy system compatibility | TLE |
| Interpolation between states | OEM |

---

## Conversion Reference

### To OEM (Orbit Ephemeris Message)

#### OMM -> OEM
> ⚠️ **Accuracy**: SGP4 errors grow with propagation time; DSST is more accurate for long arcs.

**Conversion Method**:
- **SGP4**: `propagate-omm` (automatic based on `MEAN_ELEMENT_THEORY=SGP4`)
- **DSST**: `propagate-omm` (automatic based on `MEAN_ELEMENT_THEORY=DSST`)

**Options**: `--duration DURATION`, `--step SECONDS`

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`
- **Lost**: `MEAN_ELEMENT_THEORY`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`/`BTERM`, `NORAD_CAT_ID`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `MASS`, `SOLAR_RAD_AREA`, `DRAG_AREA`

#### OPM -> OEM
> ⚠️ **Accuracy**: Kepler (two-body) ignores all perturbations; errors grow rapidly for LEO. Use `propagate-orbit` for higher fidelity.

**Conversion Method**:
- **Kepler (two-body)**: `propagate-kepler` with `-d/--duration` and `-s/--step`
- **Numerical (with perturbations)**: `propagate-orbit` with `--duration`

**Options**: `--duration DURATION`, `--step SECONDS`

**TODO**: Propagation accuracy varies significantly based on propagator choice

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`
- **Lost**: `SEMI_MAJOR_AXIS`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `TRUE_ANOMALY`/`MEAN_ANOMALY`, `MASS`, `SOLAR_RAD_AREA`, `SOLAR_RAD_COEFF`, `DRAG_AREA`, `DRAG_COEFF`, `MAN_*` (maneuvers), covariance matrix

#### TLE -> OEM
> ⚠️ **Accuracy**: SGP4 is a simplified model; errors grow with propagation time (km-level after days for LEO).

**Conversion Method**:
- **SGP4**: `propagate-tle` with `--duration` and `--step`
- **Via OMM**: `tle-to-omm` -> `propagate-omm` (uses `MEAN_ELEMENT_THEORY` from OMM)

**Options**: `--duration DURATION`, `--step SECONDS`

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID` (from NORAD ID), `CENTER_NAME` (EARTH), `REF_FRAME` (TEME), `TIME_SYSTEM` (UTC)
- **Lost**: All TLE-specific parameters, mean elements, `BSTAR`, `ELEMENT_SET_NO`

### To OMM (Orbit Mean-Elements Message)

#### OEM -> OMM
> ⚠️ **Accuracy**: Fit quality depends on arc length and theory; short arcs or noisy data reduce accuracy.

**Conversion Method**:
- **SGP4 fitting**: `oem-to-omm --mode tle` with optional `--fit-span`
- **Brouwer-Lyddane fitting**: `oem-to-omm --mode brouwer` with optional `--fit-span`

**Options**: `--mode {tle|brouwer}`, `--fit-span DURATION`

**TODO**: Orbit fitting accuracy depends on fit span and theory selection


**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`
- **Lost**: `START_TIME`, `STOP_TIME`, `INTERPOLATION`, `INTERPOLATION_DEGREE`, Cartesian state vectors, acceleration data

#### OPM -> OMM
> ⚠️ **Accuracy**: Multi-step process introduces compounded errors; propagation + fitting both approximate.

**Conversion Method**:
- **Via OEM (two-body)**: `propagate-kepler` -> `oem-to-omm`
- **Via OEM (numerical)**: `propagate-orbit` -> `oem-to-omm`

**TODO**: Not directly supported; osculating-to-mean conversion is complex

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`, `EPOCH`
- **Lost**: Osculating Keplerian elements, `MASS`, spacecraft parameters, maneuvers, covariance

#### TLE -> OMM
**Conversion Method**:
- **Direct conversion**: `tle-to-omm`

**Metadata**:
- **Preserved**: `NORAD_CAT_ID`, `CLASSIFICATION_TYPE`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`, `OBJECT_NAME` (3-line TLE only)

### To OPM (Orbit Parameter Message)

#### OEM -> OPM
> ⚠️ **Accuracy**: Two-body Keplerian fit; ignores perturbations. Fitted elements are approximate, not true osculating elements.

**Conversion Method**:
- **Osculating Keplerian fit**: `oem-to-opm` — fits a two-body Keplerian orbit to the OEM arc; output preserves the first Cartesian state and includes fitted Keplerian elements at that epoch

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `REF_FRAME_EPOCH`, `TIME_SYSTEM`, `EPOCH`, `X`, `Y`, `Z`, `X_DOT`, `Y_DOT`, `Z_DOT`
- **Added**: `SEMI_MAJOR_AXIS`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `TRUE_ANOMALY` (fitted)
- **Lost**: `START_TIME`, `STOP_TIME`, `USEABLE_START_TIME`, `USEABLE_STOP_TIME`, `INTERPOLATION`, `INTERPOLATION_DEGREE`, time series data

#### OMM -> OPM
> ⚠️ **Accuracy**: Multi-step; SGP4 propagation errors compound with two-body Keplerian fitting errors.

**Conversion Method**:
- **Via OEM**: `propagate-omm` -> `oem-to-opm`

**TODO**: No direct tool; accuracy depends on propagator and fit quality

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`, `EPOCH`
- **Lost**: `MEAN_ELEMENT_THEORY`, `BSTAR`/`BTERM`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`/`AGOM`, `NORAD_CAT_ID`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`, `EPHEMERIS_TYPE`

#### TLE -> OPM
> ⚠️ **Accuracy**: Multi-step; SGP4/J2-only errors compound with two-body Keplerian fitting errors.

**Conversion Method**:
- **Via OMM**: `tle-to-omm` -> `oem-to-opm`
- **Via OEM**: `propagate-tle` -> `oem-to-opm`

**TODO**: Not directly supported; uses only J2 correction via OMM intermediate — could benefit from higher-order perturbation models

**Metadata**:
- **Preserved**: `OBJECT_NAME` (3-line TLE), `OBJECT_ID` (from NORAD ID), `EPOCH`, `CENTER_NAME` (EARTH), `REF_FRAME` (TEME), `TIME_SYSTEM` (UTC)
- **Lost**: `BSTAR`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`

### To TLE (Two-Line Element Set)

#### OEM -> TLE
> ⚠️ **Accuracy**: Orbit fitting introduces approximation errors; TLE format has limited precision (fixed-width fields).

**Conversion Method**: Orbit fitting + direct conversion
- Requires orbit fitting to mean elements + TLE formatting
- Multi-step process (OEM -> OMM -> TLE)
- **Tool**: [`oem-to-omm`](./OEM_TO_OMM.md) `--mode tle input.oem -o output.omm &&` [`omm-to-tle`](./OMM_TO_TLE.md) `output.omm -o output.tle`

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `EPOCH` (from fitted span)
- **Lost**: Time series, interpolation, all OEM-specific metadata

#### OMM -> TLE
**Conversion Method**:
- **Direct conversion**: `omm-to-tle`


**Metadata**:
- **Preserved**: `NORAD_CAT_ID`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`, `EPHEMERIS_TYPE`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`
- **Lost**: `CCSDS_OMM_VERS`, `CREATION_DATE`, `ORIGINATOR`, `MESSAGE_ID`, `COMMENT`, `MEAN_ELEMENT_THEORY`, covariance matrix, `USER_DEFINED_*`

#### OPM -> TLE
> ⚠️ **Accuracy**: Multi-step; propagation + orbit fitting errors compound; TLE format has limited precision.

**Conversion Method**:
- **Multi-step (two-body)**: `propagate-kepler` -> `oem-to-omm --mode tle` -> `omm-to-tle`
- **Multi-step (numerical)**: `propagate-orbit` -> `oem-to-omm --mode tle` -> `omm-to-tle`

**TODO**: Not directly supported, multi-step process needed

**Metadata**:
- **Preserved**: `OBJECT_NAME`, `EPOCH`
- **Lost**: Most OPM metadata, Keplerian elements (converted), spacecraft parameters
