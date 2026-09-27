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
- **Carried forward**: `OBJECT_NAME` and `OBJECT_ID` (unless overridden or absent); OEM metadata comments are copied to OMM comments
- **Generated/set by current implementation**: header, `MEAN_ELEMENT_THEORY`, `CENTER_NAME=EARTH`, `REF_FRAME=ICRF` for Brouwer/DSST or `TEME` for SGP4, `TIME_SYSTEM=UTC`, and fitted mean elements
- **Not copied**: source `CENTER_NAME`, `REF_FRAME`, `REF_FRAME_EPOCH`, `TIME_SYSTEM`, `START_TIME`, `STOP_TIME`, usable time bounds, interpolation settings, Cartesian state vectors, acceleration, and covariance
- **Covariance caveat**: `CcsdsOem` can parse OEM covariance, but `oem-to-omm` does not copy it into the fitted OMM. Both formats can represent covariance, so this is a conversion capability gap.
- **Input frame requirement**: no state transformation is applied; the fitter accepts only `J2000`, `EME2000`, `ICRF`, or `GCRF` source frames (treated as equivalent) and rejects other frame labels
- **SGP4 frame semantics**: the OMM records SGP4 mean elements in `TEME`; TudatPy converts propagated SGP4 states to `J2000` for arc scoring

### OEM → OPM
- Extract single epoch from time series
- Two-body conversion uses the first state; numerical fitting may produce a fitted initial state
- **Carried forward**: `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`; OEM metadata comments are moved to OPM header comments
- **Generated/transformed**: OPM header and `EPOCH`; Cartesian state may be fitted, and optional Keplerian elements are emitted only for two-body fitting
- **Not copied**: `REF_FRAME_EPOCH`, OEM coverage/interpolation fields, remaining time series, covariance, spacecraft parameters, and other unsupported optional fields
- **Covariance caveat**: although OPM supports covariance, the OEM-to-OPM fitter does not copy parsed OEM covariance into the fitted OPM. This is a conversion capability gap, not a format limitation.

### OEM → TLE
- Requires orbit fitting to mean elements + TLE formatting
- Multi-step process (OEM → OMM → TLE)
- **Preserved**: `OBJECT_NAME`, `EPOCH` (from fitted span)
- **Lost from TLE**: Time series, interpolation, and CCSDS metadata/comments; source comments are retained in the companion fit report
- **Generated**: SGP4-fit elements and TLE checksums

### OMM → OEM
- Requires propagation using mean element theory
- **Carried forward**: `OBJECT_NAME`, `OBJECT_ID`, `CLASSIFICATION`, `MESSAGE_ID`, and OMM comments as OEM metadata comments
- **Generated/set by current implementation**: OEM `ORIGINATOR` and `CREATION_DATE`, `CENTER_NAME=EARTH`, `REF_FRAME=EME2000`, `TIME_SYSTEM=UTC`, coverage times, and a propagation provenance comment
- **DSST inputs**: `MASS`, `DRAG_AREA`, and `DRAG_COEFF` configure drag only when all three are present; `SOLAR_RAD_AREA` and `SOLAR_RAD_COEFF` configure SRP when both are present. Kepler fallback does not use spacecraft parameters; SGP4 uses the OMM's TLE parameters instead.
- **Not copied to OEM metadata**: source OMM `CCSDS_OMM_VERS`, `CREATION_DATE`, `ORIGINATOR`, frame/time labels, reference-frame epoch, mean elements and theory, TLE parameters, spacecraft parameters, and user-defined fields
- **Covariance behavior**: full OEM output carries the OMM covariance at its source epoch only when that epoch falls within the emitted state interval, using the declared `COV_REF_FRAME` or OMM `REF_FRAME` when omitted. Covariance is not evolved across the output arc; `--data-only` omits it.
- **Frame assumption**: treat Earth-centered `EME2000`, `J2000`, `ICRF`, and `GCRF` labels as equivalent for this comparison
- **SGP4 frame handling**: TudatPy converts the raw TEME SGP4 solution to J2000; the runtime ephemeris reports Earth/J2000. The output `EME2000` label is accepted under the stated inertial-frame equivalence assumption

### OMM → OPM
- Composed propagation to an intermediate OEM followed by numerical OPM fitting
- **Carried forward**: `OBJECT_NAME`, `OBJECT_ID`, and OMM comments (as OPM header comments); the output epoch is derived from the generated OEM
- **Generated/set by current implementation**: OPM header and the context supplied by the intermediate OEM (`EARTH`, `EME2000`, `UTC`)
- **Not copied to final OPM**: other source OMM header fields, original frame/time labels, reference-frame epoch, mean-element theory and values, TLE parameters, covariance, spacecraft parameters, and user-defined fields
- **Propagation inputs**: DSST uses complete OMM drag (`MASS`, `DRAG_AREA`, `DRAG_COEFF`) and SRP (`SOLAR_RAD_AREA`, `SOLAR_RAD_COEFF`) parameter groups during the intermediate propagation; Kepler ignores spacecraft parameters and SGP4 uses TLE parameters. These inputs are not copied into the final OPM.
- **Covariance gap**: when the source epoch falls within the intermediate OEM state interval, that OEM carries the source OMM covariance at its source epoch; the OEM-to-OPM fitter does not copy it into the final OPM. Covariance evolution/frame handling is not implemented in this composed route.
- **SGP4 frame handling**: the intermediate TudatPy ephemeris converts TEME to J2000, so its generated OEM/OPM `EME2000` label is accepted under the stated inertial-frame equivalence assumption

### OMM → TLE
- Generates standard 2-line format
- Checksums computed automatically
- **Preserved**: `NORAD_CAT_ID`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `CLASSIFICATION_TYPE`, `EPHEMERIS_TYPE`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`
- **Lost**: `CCSDS_OMM_VERS`, `CREATION_DATE`, `ORIGINATOR`, `CLASSIFICATION`, `MESSAGE_ID`, `COMMENT`, `CENTER_NAME`, `REF_FRAME`, `REF_FRAME_EPOCH`, `TIME_SYSTEM`, `MEAN_ELEMENT_THEORY`, covariance matrix, spacecraft parameters, `USER_DEFINED_*`
- For non-SGP4 OMMs, the refit path propagates OMM→OEM and fits a new SGP4 TLE. DSST propagates with DSST; current 2B/Brouwer-Lyddane routes use the labeled two-body Kepler fallback. Source comments and fit provenance belong in the companion report/intermediate OEM because TLE cannot encode them

### OPM → OEM
- Requires orbit propagation over time span
- Generates ephemeris time series from single epoch
- Propagator selection affects accuracy
- Step size determines output density
- **`propagate-kepler`**: carries `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, `REF_FRAME`, `TIME_SYSTEM`, and source OPM header comments; output header and coverage times are generated
- **`propagate-orbit`**: in full OEM output, carries source `OBJECT_NAME` (unless overridden by `--name`), `OBJECT_ID`, OPM header comments, `CLASSIFICATION`, and `MESSAGE_ID`; accepts only `CENTER_NAME=EARTH`, `REF_FRAME=J2000`, and `TIME_SYSTEM=UTC`, rejecting other or missing context instead of silently relabeling it. `--data-only` omits all metadata
- **Generated/not copied**: OEM `ORIGINATOR`, `CREATION_DATE`, and coverage are generated; other OPM header fields, `REF_FRAME_EPOCH`, Keplerian elements, spacecraft parameters, maneuvers, and other OPM-only fields are not copied
- **Covariance behavior**: both `propagate-kepler` and `propagate-orbit` preserve OPM covariance at the input epoch without evolving it across the output arc. `propagate-kepler` retains the covariance's declared frame; `propagate-orbit` accepts only J2000-equivalent covariance frames and rejects other frames. `--data-only` omits covariance with the metadata.
- **Propagation inputs**: explicit CLI values override OPM physical parameters; omitted values use matching OPM fields, then defaults. `--drag-area` sets both drag and SRP area; without it, OPM `DRAG_AREA` and `SOLAR_RAD_AREA` are used independently, with SRP area falling back to resolved drag area if absent. A serialized-input regression test verifies this precedence.

### OPM → OMM
- Requires conversion from osculating to mean elements
- Not directly supported (requires orbit fitting)
- Composed OPM propagation to OEM followed by OMM fitting
- **Carried forward**: `OBJECT_NAME`, `OBJECT_ID`, and OPM header comments through both Kepler and numerical propagation to the fitted OMM
- **Generated/set by current implementation**: OMM header, output epoch, and target mean-element theory; `CENTER_NAME=EARTH` and `TIME_SYSTEM=UTC`; `REF_FRAME=ICRF` for Brouwer/DSST and `TEME` for SGP4 fitting
- **Not copied**: other source OPM header fields, source frame labels, osculating elements, spacecraft parameters, maneuvers, and covariance

### OPM → TLE
- Requires osculating-to-mean conversion + TLE formatting
- Not directly supported (requires orbit fitting)
- **Preserved**: `OBJECT_NAME`, `EPOCH`
- **Lost**: Most OPM metadata, Keplerian elements (converted), spacecraft parameters

### TLE → OEM
- Propagate TLE using SGP4 over time span
- **Carried forward**: `OBJECT_NAME` and `OBJECT_ID` (from the TLE designator)
- **Generated/set by current implementation**: `CENTER_NAME=EARTH`, `REF_FRAME=EME2000`, `TIME_SYSTEM=UTC`, coverage times, and propagation provenance
- **Lost**: All TLE-specific parameters, mean elements, `BSTAR`, `ELEMENT_SET_NO`
- **SGP4 frame handling**: TudatPy converts the raw TLE/TEME solution to J2000 before OEM serialization; `EME2000` is accepted as equivalent under the stated assumption

### TLE → OMM
- Direct conversion supported
- OMM maps the TLE-representable identity, orbital, and TLE-parameter fields; raw line formatting and checksums are not retained
- The CLI generates `CREATION_DATE` and `ORIGINATOR`; direct library calls to `tle_to_omm` should supply these arguments because their defaults are empty
- The converter currently writes `CCSDS_OMM_VERS=2.0`
- **Preserved**: `NORAD_CAT_ID`, `CLASSIFICATION_TYPE`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`
- Serialized conversion tests verify identity, context, and all TLE-specific parameters; the core converter's creation date, originator, and comments remain empty unless supplied by the calling CLI or library arguments.

### TLE → OPM
- Composed SGP4 propagation to OEM followed by numerical OPM fitting
- **Carried forward**: `OBJECT_NAME` and `OBJECT_ID` (from the TLE designator)
- **Generated/set by current implementation**: OPM header, epoch, `CENTER_NAME=EARTH`, `REF_FRAME=EME2000`, `TIME_SYSTEM=UTC`; OPM header comments contain generated SGP4 propagation and fit provenance
- **Lost**: TLE parameters such as `BSTAR`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, and `CLASSIFICATION_TYPE`; TLE has no source comment field
- **SGP4 frame handling**: the intermediate TudatPy ephemeris converts TEME to J2000 before the OPM fit; the generated `EME2000` label is accepted under the stated assumption
