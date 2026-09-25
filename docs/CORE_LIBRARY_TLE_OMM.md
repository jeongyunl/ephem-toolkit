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
Parsed Two-Line Element set data. Angles are stored in degrees and mean motion in revolutions per day; raw exponential-format fields remain strings.

**Key Fields:**
- `object_name`: Optional satellite name (empty for two-line input)
- `line1`, `line2`: Raw TLE lines
- `norad_cat_id`: NORAD catalog number
- `classification`: U=Unclassified, C=Classified, S=Secret
- `int_designator_year`, `int_designator_launch_number`, `int_designator_piece`: International designator components
- `epoch_year`, `epoch_day`: Epoch (2-digit year + fractional day)
- `mean_motion_first_derivative`: First time derivative (rev/day²)
- `mean_motion_second_derivative`: Second time derivative (TLE exponential format)
- `bstar`: BSTAR drag term (TLE exponential format)
- `ephemeris_type`, `element_set_number`: TLE line-1 fields
- `inclination_deg`, `raan_deg`, `arg_perigee_deg`, `mean_anomaly_deg`: Orbital elements (degrees)
- `eccentricity`: Eccentricity (0.0 to 1.0)
- `mean_motion_rev_per_day`: Mean motion (rev/day)
- `revolution_number_at_epoch`: Revolution number at epoch
- `line1_checksum`, `line2_checksum`: Checksums from the input; corresponding `*_expected` fields contain computed checksums

`Tle` also provides dict-style field access, `to_dict()`, and `get_object_id()` (COSPAR ID from the international designator, using the 1957-2056 TLE year convention).

### Functions

#### `read_tle(stream: TextIO | str | Path) -> Tle`
Parse TLE elements from a text stream or file path. Accepts 2-line input or 3-line input with a name. Lines shorter than 69 characters are rejected; trailing characters beyond column 69 are ignored.

#### `write_tle(dest: TextIO | str | Path, tle_data: Tle | Mapping[str, object]) -> tuple[str, str]`
Write a TLE to a text stream or file path. Returns the formatted (line1, line2) strings.

#### `datetime_to_tle_epoch(epoch_dt: datetime) -> tuple[int, float]`
Convert a datetime object to a two-digit year and 1-based fractional day of year. Timezone-aware values are converted to UTC for the day calculation, but the year is taken before that conversion; crossing a year boundary can therefore produce mismatched year/day components. Naive values are used without timezone conversion.

#### `tle_epoch_to_datetime(epoch_year: int, epoch_day: float) -> datetime`
Convert a two-digit TLE year and fractional day to a UTC-aware `datetime`. Years 57-99 map to 1957-1999; 00-56 map to 2000-2056.

#### `tle_epoch_to_tt_s(epoch_year: int, epoch_day: float) -> float` / `tle_epoch_to_tdb_s(epoch_year: int, epoch_day: float) -> float`
Convert a TLE epoch to TT or TDB seconds since J2000.

#### `tle_epoch_to_iso8601(epoch_year: int, epoch_day: float) -> str`
Convert TLE epoch (2-digit year + fractional day) to ISO 8601 datetime string.

#### `iso8601_to_tle_epoch(iso_str: str) -> tuple[int, float]`
Convert ISO 8601 datetime string to TLE epoch (2-digit year + fractional day).

#### `format_tle_strings(tle_data: Tle | Mapping[str, object]) -> tuple[str, str]`
Format TLE data into raw TLE line strings with checksums.

#### `compute_tle_checksum(line_without_checksum: str) -> str`
Return the modulo-10 TLE checksum character. Digits contribute their value and each minus sign contributes 1.

---

## ephem_toolkit.core.convert_tle - TLE/OMM Conversion

**Purpose**: Convert between TLE and OMM representations, and TLE to osculating Keplerian elements.

### Key Dependencies
- `numpy`
- `ephem_toolkit.core.propagator.kepler`
- `ephem_toolkit.core.propagator.brouwer_j2`
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

The generated OMM uses version 2.0, TEME, UTC, and `MEAN_ELEMENT_THEORY = SGP/SGP4`; TLE-specific metadata is included in `tle_parameters`.

#### `omm_to_tle(omm_obj: ccsds.omm.CcsdsOmm) -> tle.Tle`
Convert a CCSDS OMM to a TLE.

**Parameters:**
- `omm_obj`: Parsed OMM dataclass instance

**Returns:** The equivalent TLE representation (with empty `line1` and `line2` fields; use `write_tle` to format them).

Conversion requires `tle_parameters`; otherwise it raises `ValueError`. `validate_sgp4_compatible_omm` separately checks the declared theory and TLE parameters; `omm_to_tle` does not invoke that helper itself.

### TLE to Osculating Keplerian

#### `tle_to_osculating_keplerian(tle_obj: tle.Tle, mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2, apply_j2: bool = True) -> np.ndarray`
Extract osculating Keplerian elements at the TLE epoch.

**Parameters:**
- `tle_obj`: Parsed TLE dataclass
- `mu_m3_s2`: Gravitational parameter (m³/s²) (default: Earth WGS-84)
- `apply_j2`: If True, apply Brouwer J2 short-period corrections; if False, use simple two-body conversion

**Returns:** `[a_m, e, i_rad, omega_rad, RAAN_rad, theta_rad]`, where `omega` is argument of pericenter and `theta` is true anomaly. With `apply_j2=True`, the elements include Brouwer first-order J2 short-period corrections; with `False`, they use two-body conversion.

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
- `CCSDS_TIMECODE_PATTERN`: Pattern for CCSDS date/time values
- `CCSDS_NON_DECIMAL_STRING_PATTERN`, `CCSDS_FREE_TEXT_STRING_PATTERN`: Patterns for ODM non-decimal and free-text fields
- `CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN`, `CCSDS_3VALUE_NUMERICAL_PATTERN`: Patterns for numeric fields, optionally with units, and 3-value sequences

---

## ephem_toolkit.core.ccsds.omm - Orbit Mean-Elements Message

**Purpose**: Read, parse, and write CCSDS Orbit Mean-Elements Message (OMM) files.

### Key Dependencies
- `dataclasses`, `pathlib`, `typing`, `datetime`
- `numpy`
- `ephem_toolkit.core.misc`, `ephem_toolkit.core.consts`, `ephem_toolkit.core.time_utils`, `ephem_toolkit.core.kepler`
- `ephem_toolkit.core.misc`, `ephem_toolkit.core.consts`, `ephem_toolkit.core.time_utils`, `ephem_toolkit.core.propagator.kepler`

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
- `TleParameters` is created by `from_source` when TLE-related parameter fields are present
- `tle_parameters`: Optional `TleParameters` for TLE/SGP-family metadata such as ephemeris type, classification, catalog ID, element set, revolution number, BSTAR, and mean-motion derivatives
- SGP4-XP `TleParameters` may also include `bterm` and `agom`
- `ref_frame_epoch`, `semi_major_axis`, `gm`: Optional reference-frame epoch, semi-major axis (km), and gravitational parameter (km³/s²); mean elements use either semi-major axis or mean motion
- `spacecraft_parameters`: Optional mass, solar-radiation area/coefficient, and drag area/coefficient
- `covariance`: Optional symmetric 6×6 state covariance and covariance frame
- `data`: Raw parsed fields, including fields without dedicated attributes

The low-level `read_omm` and `write_omm` functions operate on dictionaries; `CcsdsOmm.from_source` and `to_file` provide the structured interface.

### Functions

#### `read_omm(source: TextIO | str | Path, *, validate: bool = True) -> tuple[dict, dict]`
Read an OMM file and return `(header, data)` dictionaries. Validation is enabled by default and checks required fields, including the requirement for exactly one of `SEMI_MAJOR_AXIS` or `MEAN_MOTION`; pass `validate=False` to skip validation.

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
OEM files use kilometers (km) and km/s per the CCSDS standard. This module converts state vectors to SI units (meters and m/s) when reading, and converts back to km/km·s⁻¹ when writing. Input epoch strings are interpreted as UTC and converted to TT seconds since J2000 regardless of the `TIME_SYSTEM` metadata; non-UTC time-system conversion is not performed.

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
- `states`: List of (TT seconds since J2000, state_vector) tuples in stored/input order. State vectors are six-element arrays [x, y, z, vx, vy, vz] in meters and m/s.
- Ordering: `from_states` sorts by epoch, while `read` preserves file order.

**Properties:**
- `epochs`: Epoch timestamps (TT seconds since J2000) in the same order as `states`
- Ordering: The property returns stored order and does not sort the states
- `state_vectors`: State vectors in the same order as `states`, shape (N, 6) in meters and m/s

**Class Methods:**
- `CcsdsOem.read(source: TextIO | str | Path) -> CcsdsOem`: Read and construct from a file or stream
- `CcsdsOem.from_states(states, object_name="", object_id="", ref_frame="", center_name="", time_system="UTC") -> CcsdsOem`: Create from states with minimal metadata; sorts input by epoch
- Default `time_system` is `UTC`; the `states` timestamps are TT seconds since J2000
- `CcsdsOem.parse_oem_state_line(line: str) -> tuple[float, np.ndarray] | None`: Parse a single OEM-style state line

**Instance Methods:**
- `write(dest: TextIO | str | Path, format_type: OemFormat = OemFormat.OEM) -> None`: Write this OEM to a file or stream as OEM or CSV-formatted output
- `write_state(dest: TextIO, epoch: datetime, state_vector: np.ndarray, sep: str = " ") -> None`: Write one state vector in CCSDS units; `sep` defaults to one space
- `OemFormat` supports `OEM` and `CSV`
- `find_state_by_timestamp(timestamp: float, tolerance: float = 0.0) -> tuple[float, np.ndarray] | None`: Binary-search sorted states; exact match is required when tolerance is zero, otherwise returns the closest state within tolerance
- `write_states(dest: TextIO, format_type: OemFormat = OemFormat.OEM) -> None`: Write state vectors as OEM or CSV
- `update_metadata(**kwargs) -> None`: Update metadata fields in-place

`OemFormat` defines the `OEM` and `CSV` output choices. `read` preserves source state order, so sort input before using `find_state_by_timestamp` on an unsorted OEM file.
