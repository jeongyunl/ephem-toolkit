# Metadata Comparison: TLE, OPM, OMM, OEM

Comparison of mandatory (M), optional (O), and conditional (C) metadata items across orbital data formats.

---

## Header Metadata

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Format Version** | - | M | M | M |
| **Creation Date** | - | M | M | M |
| **Originator** | - | M | M | M |
| **Classification** | M | O | O | O |
| **Message ID** | - | O | O | O |
| **Comments** | - | O | O | O |

---

## Object Identification

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Object Name** | O | M | M | M |
| **Object ID** | M (NORAD) | M | M | M |
| **International Designator** | M | - | - | - |

---

## Reference Frame & Time

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Center Name** | Implicit (EARTH) | M | M | M |
| **Reference Frame** | Implicit (TEME) | M | M | M |
| **Reference Frame Epoch** | - | C | C | C |
| **Time System** | Implicit (UTC) | M | M | M |

---

## Epoch & Time Range

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Epoch** | M | M | M | - |
| **Start Time** | - | - | - | M |
| **Stop Time** | - | - | - | M |
| **Useable Start Time** | - | - | - | O |
| **Useable Stop Time** | - | - | - | O |

---

## State Vector (Cartesian)

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Position (X, Y, Z)** | - | M | - | M (data) |
| **Velocity (X_DOT, Y_DOT, Z_DOT)** | - | M | - | M (data) |
| **Acceleration (X_DDOT, Y_DDOT, Z_DDOT)** | - | - | - | O (data) |

---

## Keplerian Elements

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Semi-Major Axis** | - | C | M* | - |
| **Mean Motion** | M | - | M* | - |
| **Eccentricity** | M | C | M | - |
| **Inclination** | M | C | M | - |
| **RAAN** | M | C | M | - |
| **Argument of Perigee** | M | C | M | - |
| **Mean Anomaly** | M | - | M | - |
| **True Anomaly** | - | C | - | - |
| **GM** | - | C | O | - |

*OMM: Either SEMI_MAJOR_AXIS or MEAN_MOTION required (MEAN_MOTION for SGP/SGP4)

---

## Mean Element Theory

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Mean Element Theory** | Implicit (SGP4) | - | M | - |
| **Ephemeris Type** | M | - | O | - |

---

## Drag & Perturbation Parameters

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **BSTAR / BTERM** | M | - | C | - |
| **Mean Motion Dot** | M | - | C | - |
| **Mean Motion DDot / AGOM** | M | - | C | - |

---

## Spacecraft Physical Parameters

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Mass** | - | C | O | - |
| **Solar Radiation Area** | - | O | O | - |
| **Solar Radiation Coefficient** | - | O | O | - |
| **Drag Area** | - | O | O | - |
| **Drag Coefficient** | - | O | O | - |

---

## TLE-Specific Parameters

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Element Set Number** | M | - | O | - |
| **Revolution Number at Epoch** | M | - | O | - |
| **Classification Type** | M | - | O | - |
| **NORAD Catalog ID** | M | - | O | - |

---

## Covariance Matrix

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Covariance Reference Frame** | - | C | C | C |
| **Position Covariance (CX_X, CY_Y, CZ_Z, etc.)** | - | C | C | C |
| **Velocity Covariance (CX_DOT_X_DOT, etc.)** | - | C | C | C |
| **Cross Covariance (CX_DOT_X, etc.)** | - | C | C | C |

Note: All covariance elements are conditional—if any are provided, all must be provided.

---

## Maneuver Parameters

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Maneuver Epoch Ignition** | - | O | - | - |
| **Maneuver Duration** | - | O | - | - |
| **Maneuver Delta Mass** | - | O | - | - |
| **Maneuver Reference Frame** | - | O | - | - |
| **Maneuver Delta-V (3 components)** | - | O | - | - |

Note: OPM supports multiple maneuvers; OMM does not accommodate maneuvers.

---

## Interpolation (OEM Only)

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **Interpolation Method** | - | - | - | O |
| **Interpolation Degree** | - | - | - | O |

---

## User-Defined Parameters

| Item | TLE | OPM | OMM | OEM |
|------|-----|-----|-----|-----|
| **USER_DEFINED_x** | - | O | O | - |

Note: Must be documented in Interface Control Document (ICD).

---

## Key Differences Summary

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

## Conversion Notes

### OEM → OMM
- Requires orbit fitting to mean elements
- Fit span typically 2 hours
- Theory selection (SGP4, DSST) affects accuracy
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`
- **Lost**: `START_TIME`, `STOP_TIME`, `INTERPOLATION`, `INTERPOLATION_DEGREE`, Cartesian state vectors, acceleration data

### OEM → OPM
- Extract single epoch from time series
- First state typically used
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `REF_FRAME_EPOCH`, `TIME_SYSTEM`, `EPOCH`, `X`, `Y`, `Z`, `X_DOT`, `Y_DOT`, `Z_DOT`
- **Lost**: `START_TIME`, `STOP_TIME`, `USEABLE_START_TIME`, `USEABLE_STOP_TIME`, `INTERPOLATION`, `INTERPOLATION_DEGREE`, time series data

### OEM → TLE
- Requires orbit fitting to mean elements + TLE formatting
- Multi-step process (OEM → OMM → TLE)
- **Preserved**: `OBJECT_NAME`, `EPOCH` (from fitted span)
- **Lost**: Time series, interpolation, all OEM-specific metadata

### OMM → OEM
- Requires propagation using mean element theory
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`
- **Lost**: `MEAN_ELEMENT_THEORY`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`/`BTERM`, `NORAD_CAT_ID`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `MASS`, `SOLAR_RAD_AREA`, `DRAG_AREA`

### OMM → OPM
- Converts mean to osculating elements
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`, `EPOCH`
- **Lost**: `MEAN_ELEMENT_THEORY`, `BSTAR`/`BTERM`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`/`AGOM`, `NORAD_CAT_ID`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`, `EPHEMERIS_TYPE`

### OMM → TLE
- Generates standard 2-line format
- Checksums computed automatically
- **Preserved**: `NORAD_CAT_ID`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`, `EPHEMERIS_TYPE`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`
- **Lost**: `CCSDS_OMM_VERS`, `CREATION_DATE`, `ORIGINATOR`, `MESSAGE_ID`, `COMMENT`, `MEAN_ELEMENT_THEORY`, covariance matrix, `USER_DEFINED_*`

### OPM → OEM
- Requires orbit propagation over time span
- Generates ephemeris time series from single epoch
- Propagator selection affects accuracy
- Step size determines output density
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`
- **Lost**: `SEMI_MAJOR_AXIS`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `TRUE_ANOMALY`/`MEAN_ANOMALY`, `MASS`, `SOLAR_RAD_AREA`, `SOLAR_RAD_COEFF`, `DRAG_AREA`, `DRAG_COEFF`, `MAN_*` (maneuvers), covariance matrix

### OPM → OMM
- Requires conversion from osculating to mean elements
- Not directly supported (requires orbit fitting)
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`, `EPOCH`
- **Lost**: Osculating Keplerian elements, `MASS`, spacecraft parameters, maneuvers, covariance

### OPM → TLE
- Requires osculating-to-mean conversion + TLE formatting
- Not directly supported (requires orbit fitting)
- **Preserved**: `OBJECT_NAME`, `EPOCH`
- **Lost**: Most OPM metadata, Keplerian elements (converted), spacecraft parameters

### TLE → OEM
- Propagate TLE using SGP4 over time span
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID` (from NORAD ID), `CENTER_NAME` (EARTH), `REF_FRAME` (TEME), `TIME_SYSTEM` (UTC)
- **Lost**: All TLE-specific parameters, mean elements, `BSTAR`, `ELEMENT_SET_NO`

### TLE → OMM
- Direct conversion supported
- OMM preserves all TLE fields
- OMM adds CCSDS metadata structure
- **Preserved**: `NORAD_CAT_ID`, `CLASSIFICATION_TYPE`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`

### TLE → OPM
- Converts mean to osculating elements (J2 correction)
- **Preserved**: `OBJECT_NAME`, `OBJECT_ID` (from NORAD ID), `EPOCH`, `CENTER_NAME` (EARTH), `REF_FRAME` (TEME), `TIME_SYSTEM` (UTC)
- **Lost**: `BSTAR`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`
