# Core Library - TLE & OMM

This document covers Two-Line Element (TLE) sets, Orbit Mean-Elements Messages (OMM), and TLE/OMM conversions in the `core/` directory.

## Table of Contents

1. [ephem_toolkit.core.tle - Two-Line Element Sets](#ephem_toolkitcoretle---two-line-element-sets)
2. [ephem_toolkit.core.convert_tle - TLE/OMM Conversion](#ephem_toolkitcoreconvert_tle---tleomm-conversion)
3. [ephem_toolkit.core.ccsds.odm - CCSDS Orbit Data Message Definitions](#ephem_toolkitcoreccsdsodm---ccsds-orbit-data-message-definitions)
4. [ephem_toolkit.core.ccsds.omm - Orbit Mean-Elements Message](#ephem_toolkitcoreccsdsomm---orbit-mean-elements-message)
5. [ephem_toolkit.core.ccsds.oem - Orbit Ephemeris Message](#ephem_toolkitcoreccsdsoem---orbit-ephemeris-message)

---

## ephem_toolkit.core.tle - Two-Line Element Sets

**Purpose**: Read, parse, and write NORAD Two-Line Element (TLE) sets.

### Key Dependencies
- `datetime`, `pathlib`, `re`, `dataclasses`, `typing`
- `ephem_toolkit.core.misc`, `ephem_toolkit.core.time_utils`

### Data Structure

#### `class Tle` (dataclass)
Parsed Two-Line Element set data with all fields corresponding to the standard TLE format.

**Key Fields:**
- `name`: Satellite name
- `line1`, `line2`: Raw TLE lines
- `norad_cat_id`: NORAD catalog number
- `classification`: U=Unclassified, C=Classified, S=Secret
- `epoch_year`, `epoch_day`: Epoch (2-digit year + fractional day)
- `mean_motion_first_derivative`: First time derivative (rev/day²)
- `mean_motion_second_derivative`: Second time derivative (TLE exponential format)
- `bstar`: BSTAR drag term (TLE exponential format)
- `inclination_deg`, `raan_deg`, `arg_perigee_deg`, `mean_anomaly_deg`: Orbital elements (degrees)
- `eccentricity`: Eccentricity (0.0 to 1.0)
- `mean_motion_rev_per_day`: Mean motion (rev/day)
- `revolution_number_at_epoch`: Revolution number at epoch

### Functions

#### `read_tle(stream: TextIO) -> Tle`
Parse TLE elements from a text stream. Accepts 2-line or 3-line format (with name).

#### `write_tle(dest: TextIO | str | Path, tle_data: Tle | Mapping[str, object]) -> tuple[str, str]`
Write a TLE to a text stream or file path. Returns the formatted (line1, line2) strings.

#### `datetime_to_tle_epoch(epoch_dt: datetime) -> tuple[int, float]`
Convert a datetime object to TLE epoch components (2-digit year and fractional day).

#### `tle_epoch_to_iso8601(epoch_year: int, epoch_day: float) -> str`
Convert TLE epoch (2-digit year + fractional day) to ISO 8601 datetime string.

#### `iso8601_to_tle_epoch(iso_str: str) -> tuple[int, float]`
Convert ISO 8601 datetime string to TLE epoch (2-digit year + fractional day).

#### `format_tle_strings(tle_data: Tle | Mapping[str, object]) -> tuple[str, str]`
Format TLE data into raw TLE line strings with checksums.

#### `create_tle_from_mean_keplerian(mean_elements, mu_m3_s2, epoch_year, epoch_day, ...) -> Tle`
Construct a TLE dataclass instance from mean Keplerian elements, with optional TLE header fields.

#### `compute_tle_checksum(line_without_checksum: str) -> str`
Return the single-digit TLE checksum character for a TLE line.

---

## ephem_toolkit.core.convert_tle - TLE/OMM Conversion

**Purpose**: Convert between TLE and OMM representations, and TLE to osculating Keplerian elements.

### Key Dependencies
- `numpy`
- `ephem_toolkit.core.kepler`
- `ephem_toolkit.core.mean_kepler`
- `ephem_toolkit.core.ccsds.omm`
- `ephem_toolkit.core.tle`
- `ephem_toolkit.core.consts`

### TLE ↔ OMM Conversion

#### `tle_to_omm(tle_obj: tle.Tle, *, creation_date: str = "", originator: str = "") -> ccsds.omm.CcsdsOmm`
Convert a TLE to a CCSDS OMM.

**Parameters:**
- `tle_obj`: Parsed TLE dataclass instance
- `creation_date`: Optional creation date for the OMM header
- `originator`: Optional originator for the OMM header

**Returns:** The equivalent OMM representation

#### `omm_to_tle(omm_obj: ccsds.omm.CcsdsOmm) -> tle.Tle`
Convert a CCSDS OMM to a TLE.

**Parameters:**
- `omm_obj`: Parsed OMM dataclass instance

**Returns:** The equivalent TLE representation (with empty line1 and line2 fields)

### TLE to Osculating Keplerian

#### `tle_to_osculating_keplerian(tle_obj: tle.Tle, mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2, apply_j2: bool = True) -> np.ndarray`
Extract osculating Keplerian elements at the TLE epoch.

**Parameters:**
- `tle_obj`: Parsed TLE dataclass
- `mu_m3_s2`: Gravitational parameter (m³/s²) (default: Earth WGS-84)
- `apply_j2`: If True, apply Brouwer J2 short-period corrections; if False, use simple two-body conversion

**Returns:** Osculating Keplerian elements [a, e, i, omega, RAAN, theta]

---

## ephem_toolkit.core.ccsds.odm - CCSDS Orbit Data Message Definitions

**Purpose**: Define the reference-frame and time-system identifiers permitted by CCSDS Orbit Data Messages (ODM), including OEM and OMM files.

### Constants

- `REF_FRAME_DESCRIPTIONS`: Mapping of permitted reference-frame identifiers to descriptions
- `REF_FRAME_VALUES`: Immutable set of permitted reference-frame identifiers
- `REF_FRAMES`: Alias for `REF_FRAME_VALUES`
- `TIME_SYSTEM_DESCRIPTIONS`: Mapping of permitted time-system identifiers to descriptions
- `TIME_SYSTEM_VALUES`: Immutable set of permitted time-system identifiers
- `TIME_SYSTEMS`: Alias for `TIME_SYSTEM_VALUES`

---

## ephem_toolkit.core.ccsds.omm - Orbit Mean-Elements Message

**Purpose**: Read, parse, and write CCSDS Orbit Mean-Elements Message (OMM) files.

### Key Dependencies
- `dataclasses`, `pathlib`, `typing`, `datetime`
- `numpy`
- `ephem_toolkit.core.misc`, `ephem_toolkit.core.consts`, `ephem_toolkit.core.time_utils`, `ephem_toolkit.core.kepler`

### Data Structure

#### `class CcsdsOmm` (dataclass)
Parsed CCSDS Orbit Mean-Elements Message. All angular quantities are stored in degrees and mean motion in revolutions per day.

**Key Fields:**
- `version`: CCSDS OMM format version number
- `creation_date`, `originator`: File metadata
- `comments`: List of comment lines
- `object_name`, `object_id`: Satellite identification
- `center_name`, `ref_frame`, `time_system`: Reference frame information
- `mean_element_theory`: Mean element theory used (e.g., DSST, SGP4)
- `epoch`: Epoch time (ISO 8601 format)
- `mean_motion`, `eccentricity`, `inclination`, `ra_of_asc_node`, `arg_of_pericenter`, `mean_anomaly`: Orbital elements
- `tle_parameters`: Optional `TleParameters` object containing TLE-related metadata such as `ephemeris_type`, `classification_type`, `norad_cat_id`, `element_set_no`, `rev_at_epoch`, `bstar`, `mean_motion_dot`, and `mean_motion_ddot`

### Functions

#### `read_omm(source: TextIO | str | Path) -> tuple[dict, dict]`
Read an OMM file and return (header, data) dictionaries.

#### `write_omm(dest: TextIO | str | Path, header: dict, data: dict) -> None`
Write an OMM file from (header, data) dictionaries.

#### `CcsdsOmm.from_source(source: TextIO | str | Path) -> CcsdsOmm`
Construct a CcsdsOmm from a file or stream.

#### `CcsdsOmm.to_file(dest: TextIO | str | Path) -> None`
Write this OMM to a file or stream.

---

## ephem_toolkit.core.ccsds.oem - Orbit Ephemeris Message

**Purpose**: Read, parse, and write CCSDS Orbit Ephemeris Message (OEM) files.

### Unit Convention

OEM files use kilometers (km) and km/s per the CCSDS standard. This module converts state vectors to SI units (meters and m/s) when reading, and converts back to km/km·s⁻¹ when writing. This ensures internal consistency with the project-wide SI unit convention while maintaining CCSDS-compliant file output.

### Key Dependencies
- `numpy`, `datetime`, `pathlib`, `dataclasses`
- `ephem_toolkit.core.misc`, `ephem_toolkit.core.time_utils`

### Constants
- `KILOMETERS_TO_METERS = 1000.0` - Conversion factor from kilometers to meters

### Data Structures

#### `class OemHeader` (dataclass)
File-level header fields for a CCSDS OEM message.

**Fields:**
- `version`: CCSDS OEM format version number
- `comments`: List of comment lines
- `classification`: Optional message classification
- `message_id`: Optional message identifier
- `creation_date`: File creation date (ISO 8601)
- `originator`: Organization that created the file

#### `class OemMeta` (dataclass)
Metadata block fields for a CCSDS OEM segment.

**Fields:**
- `object_name`, `object_id`: Satellite identification
- `center_name`, `ref_frame`, `time_system`: Reference frame information
- `ref_frame_epoch`: Reference-frame epoch, when required
- `start_time`, `stop_time`: Ephemeris time range
- `useable_start_time`, `useable_stop_time`: Recommended usage time range
- `interpolation`, `interpolation_degree`: Interpolation method and degree
- `comments`: List of comment lines

#### `class CcsdsOem`
Structured CCSDS Orbit Ephemeris Message with header, metadata, and states.

**Attributes:**
- `header`: File-level header fields (OemHeader)
- `meta`: Metadata block fields (OemMeta)
- `data_comments`: Comment lines before the ephemeris state data
- `states`: List of (POSIX timestamp, state_vector) tuples, sorted by timestamp in ascending order. State vectors are 6-element arrays [x, y, z, vx, vy, vz] in meters (m) and m/s.

**Properties:**
- `epochs`: Sorted list of epoch POSIX timestamps
- `state_vectors`: State vectors ordered by epoch, shape (N, 6) in meters and m/s

**Class Methods:**
- `CcsdsOem.read(source: TextIO | str | Path) -> CcsdsOem`: Read and construct from a file or stream
- `CcsdsOem.from_states(states, object_name, ref_frame, center_name, time_system) -> CcsdsOem`: Create from a list of states with minimal metadata
- `CcsdsOem.parse_oem_state_line(line: str) -> tuple[float, np.ndarray] | None`: Parse a single OEM-style state line

**Instance Methods:**
- `write(dest: TextIO | str | Path) -> None`: Write this OEM to a file or stream
- `write_state(dest: TextIO, epoch: datetime, state_vector: np.ndarray) -> None`: Write one state vector in CCSDS units
- `write_states(dest: TextIO) -> None`: Write this object's state vectors in CCSDS units
- `update_metadata(**kwargs) -> None`: Update metadata fields in-place
- `find_state_by_timestamp(timestamp: float, tolerance: float = 0.0) -> tuple[float, np.ndarray] | None`: Find a state by timestamp using binary search
