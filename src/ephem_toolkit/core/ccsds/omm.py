"""Read, parse, and write CCSDS Orbit Mean-Elements Message (OMM) files.

Provides a structured :class:`CcsdsOmm` class with stream, path, and text
serialization methods.

References:
    CCSDS 502.0-B-3 "Orbit Mean-Elements Message (OMM)" standard (2023-04).
"""

from __future__ import annotations

import io
import math
import re
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from .. import misc
from .. import consts
from .. import time_utils
from ..propagator import kepler
from . import odm

DEFAULT_OMM_VERSION: float = 3.0
"""Default CCSDS OMM version (2023-04 standard)."""

DEFAULT_ELEMENT_SET_NUMBER: int = 999
"""Default TLE element set number when the field is absent."""

MINIMUM_OMM_KEY_WIDTH: int = 14
"""Minimum key column width when writing OMM data fields."""

COVARIANCE_DIMENSION: int = 6
"""Number of position and velocity components in the covariance matrix."""

# ===================================================================
# Internal helpers
# ===================================================================


_HEADER_KEYS: set[str] = {
    "CCSDS_OMM_VERS",
    "CLASSIFICATION",
    "CREATION_DATE",
    "ORIGINATOR",
    "MESSAGE_ID",
}
_HEADER_KEY_ORDER: tuple[str, ...] = (
    "CCSDS_OMM_VERS",
    "CLASSIFICATION",
    "CREATION_DATE",
    "ORIGINATOR",
    "MESSAGE_ID",
)

_META_KEY_ORDER: list[str] = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "REF_FRAME_EPOCH",
    "TIME_SYSTEM",
    "MEAN_ELEMENT_THEORY",
]
"""Canonical key ordering for the OMM metadata section."""

_MEAN_ELEMENTS_KEY_ORDER: list[str] = [
    "EPOCH",
    "SEMI_MAJOR_AXIS",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "GM",
]
"""Canonical key ordering for the mean elements section."""

_TLE_PARAMS_KEY_ORDER: list[str] = [
    "EPHEMERIS_TYPE",
    "CLASSIFICATION_TYPE",
    "NORAD_CAT_ID",
    "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
    "BSTAR",
    "BTERM",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
    "AGOM",
]
"""Canonical key ordering for the TLE-related parameters section."""

_COVARIANCE_KEYS: tuple[str, ...] = (
    "CX_X",
    "CY_X",
    "CY_Y",
    "CZ_X",
    "CZ_Y",
    "CZ_Z",
    "CX_DOT_X",
    "CX_DOT_Y",
    "CX_DOT_Z",
    "CX_DOT_X_DOT",
    "CY_DOT_X",
    "CY_DOT_Y",
    "CY_DOT_Z",
    "CY_DOT_X_DOT",
    "CY_DOT_Y_DOT",
    "CZ_DOT_X",
    "CZ_DOT_Y",
    "CZ_DOT_Z",
    "CZ_DOT_X_DOT",
    "CZ_DOT_Y_DOT",
    "CZ_DOT_Z_DOT",
)

_COVARIANCE_POSITIONS: tuple[tuple[int, int], ...] = tuple(
    (row, column) for row in range(COVARIANCE_DIMENSION) for column in range(row + 1)
)

_UNIT_BY_KEY: dict[str, str] = {
    "SEMI_MAJOR_AXIS": "km",
    "MEAN_MOTION": "rev/day",
    "INCLINATION": "deg",
    "RA_OF_ASC_NODE": "deg",
    "ARG_OF_PERICENTER": "deg",
    "MEAN_ANOMALY": "deg",
    "GM": "km**3/s**2",
    "MASS": "kg",
    "SOLAR_RAD_AREA": "m**2",
    "DRAG_AREA": "m**2",
    "MEAN_MOTION_DOT": "rev/day**2",
    "MEAN_MOTION_DDOT": "rev/day**3",
    "BSTAR": "1/ER",
}

for covariance_key, (row, column) in zip(_COVARIANCE_KEYS, _COVARIANCE_POSITIONS):
    if row < 3 and column < 3:
        _UNIT_BY_KEY[covariance_key] = "km**2"
    elif row >= 3 and column < 3:
        _UNIT_BY_KEY[covariance_key] = "km**2/s"
    else:
        _UNIT_BY_KEY[covariance_key] = "km**2/s**2"

_SPACECRAFT_KEY_ORDER: tuple[str, ...] = (
    "MASS",
    "SOLAR_RAD_AREA",
    "SOLAR_RAD_COEFF",
    "DRAG_AREA",
    "DRAG_COEFF",
)


def _validate_omm_value(key: str, value: str) -> None:
    """Validate generic ODM numeric, time, and optional unit syntax."""
    if not value:
        return
    if "[n/a]" in value.lower():
        raise ValueError("[n/a] is not permitted in an OMM")
    unit_match = re.search(r"\s+\[([^\]]*)\]$", value)
    if "[" in value or "]" in value:
        if unit_match is None:
            raise ValueError(f"Invalid unit notation for OMM keyword {key}")
        expected_unit = _UNIT_BY_KEY.get(key)
        if expected_unit is None or unit_match.group(1) != expected_unit:
            raise ValueError(f"Invalid unit for OMM keyword {key}")
        value = value[: unit_match.start()].rstrip()
    if (
        not value
        or any(char.isspace() for char in value)
        and key
        not in {
            "OBJECT_NAME",
            "CLASSIFICATION",
            "ORIGINATOR",
            "MESSAGE_ID",
        }
        and not key.startswith("USER_DEFINED_")
    ):
        raise ValueError(f"Invalid whitespace in OMM value for {key}")
    if key in {"CREATION_DATE", "EPOCH", "REF_FRAME_EPOCH"}:
        if not re.fullmatch(
            r"\d{4}-(?:\d{2}-\d{2}|\d{3})T\d{2}:\d{2}:\d{2}(?:\.\d{1,16})?Z?",
            value,
        ):
            raise ValueError(f"Invalid OMM time value for {key}: {value}")
        if re.match(r"\d{4}-\d{3}T", value):
            time_text = value.removesuffix("Z")
            formats = ("%Y-%jT%H:%M:%S.%f", "%Y-%jT%H:%M:%S")
            valid_time = False
            for time_format in formats:
                try:
                    datetime.strptime(time_text, time_format)
                    valid_time = True
                    break
                except ValueError:
                    continue
            if not valid_time:
                raise ValueError(f"Invalid OMM time value for {key}: {value}")
        else:
            time_utils.iso8601_to_datetime(value)
    if (
        key == "CCSDS_OMM_VERS"
        or key in _UNIT_BY_KEY
        or key
        in {
            "ECCENTRICITY",
            "INCLINATION",
            "RA_OF_ASC_NODE",
            "ARG_OF_PERICENTER",
            "MEAN_ANOMALY",
            "EPHEMERIS_TYPE",
            "NORAD_CAT_ID",
            "ELEMENT_SET_NO",
            "REV_AT_EPOCH",
            "BTERM",
            "AGOM",
        }
    ):
        if not re.fullmatch(
            r"[+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?",
            value,
        ):
            if re.fullmatch(r"[+-]?\.\d+(?:[Ee][+-]?\d+)?", value):
                warnings.warn(
                    f"OMM keyword {key} uses a leading-decimal numeric value "
                    f"accepted for compatibility: {value}",
                    UserWarning,
                    stacklevel=2,
                )
                value = re.sub(r"^([+-]?)\.", r"\g<1>0.", value)
            else:
                raise ValueError(
                    f"Invalid numeric value for OMM keyword {key}: {value}"
                )
        if key == "CCSDS_OMM_VERS" and not re.fullmatch(r"\d+\.\d+", value):
            raise ValueError("CCSDS_OMM_VERS must have the form x.y")
        if re.search("[Ee]", value) and not re.fullmatch(
            r"[+-]?\d+\.\d+[Ee][+-]?\d+", value
        ):
            raise ValueError(f"Invalid floating-point value for OMM keyword {key}")
        mantissa = re.split("[Ee]", value)[0].lstrip("+-").replace(".", "")
        significant_digits = len(mantissa.lstrip("0")) or 1
        if significant_digits > 16:
            raise ValueError(f"Too many significant digits for OMM keyword {key}")
        if not math.isfinite(float(value)):
            raise ValueError(f"Non-finite numeric value for OMM keyword {key}")
        if key in {
            "EPHEMERIS_TYPE",
            "NORAD_CAT_ID",
            "ELEMENT_SET_NO",
            "REV_AT_EPOCH",
        }:
            integer = int(value)
            if integer < -2_147_483_648 or integer > 2_147_483_647:
                raise ValueError(f"Integer value out of range for OMM keyword {key}")
            if not re.fullmatch(r"[+-]?\d+", value):
                raise ValueError(f"OMM keyword {key} requires an integer")
    if key in {"CENTER_NAME", "REF_FRAME", "TIME_SYSTEM", "MEAN_ELEMENT_THEORY"}:
        if value != value.upper() and value != value.lower():
            raise ValueError(f"OMM keyword {key} must use a consistent case")


def validate_omm(header: dict[str, Any], data: dict[str, Any]) -> None:
    """Validate mandatory and conditional CCSDS OMM fields."""
    unsupported_header = set(header) - (_HEADER_KEYS | {"COMMENT"})
    if unsupported_header:
        raise ValueError(
            "Unsupported OMM header keyword(s): "
            + ", ".join(sorted(unsupported_header))
        )
    supported_data = {
        *_META_KEY_ORDER,
        *_MEAN_ELEMENTS_KEY_ORDER,
        *_TLE_PARAMS_KEY_ORDER,
        *_SPACECRAFT_KEY_ORDER,
        "COV_REF_FRAME",
        *_COVARIANCE_KEYS,
    }
    unsupported_data = {
        key
        for key in data
        if key not in supported_data
        and not re.fullmatch(r"USER_DEFINED_[A-Z0-9_]+", key)
    }
    if unsupported_data:
        raise ValueError(
            "Unsupported OMM keyword(s): " + ", ".join(sorted(unsupported_data))
        )
    for key, value in (*header.items(), *data.items()):
        if key != "COMMENT":
            serialized = (
                CcsdsOmm._write_value(key, value)
                if isinstance(value, (float, np.floating))
                else str(value)
            )
            _validate_omm_value(key, serialized)

    required_header: set[str] = {"CCSDS_OMM_VERS", "CREATION_DATE", "ORIGINATOR"}
    required_metadata: set[str] = {
        "OBJECT_NAME",
        "OBJECT_ID",
        "CENTER_NAME",
        "REF_FRAME",
        "TIME_SYSTEM",
        "MEAN_ELEMENT_THEORY",
    }
    required_elements: set[str] = {
        "EPOCH",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
    }
    missing: list[str] = sorted(required_header - header.keys())
    if missing:
        raise ValueError("Missing required OMM header field(s): " + ", ".join(missing))
    empty = sorted(key for key in required_header if not str(header[key]).strip())
    if empty:
        warnings.warn(
            "Empty required OMM header field(s): " + ", ".join(empty),
            UserWarning,
            stacklevel=2,
        )
    missing = sorted(required_metadata - data.keys())
    if missing:
        raise ValueError(
            "Missing required OMM metadata field(s): " + ", ".join(missing)
        )
    empty = sorted(key for key in required_metadata if not str(data[key]).strip())
    if empty:
        raise ValueError("Empty required OMM metadata field(s): " + ", ".join(empty))
    odm.validate_odm_context(
        str(data["CENTER_NAME"]),
        str(data["REF_FRAME"]),
        str(data["TIME_SYSTEM"]),
    )
    missing = sorted(required_elements - data.keys())
    if missing:
        raise ValueError(
            "Missing required OMM mean element field(s): " + ", ".join(missing)
        )
    empty = sorted(key for key in required_elements if not str(data[key]).strip())
    if empty:
        raise ValueError(
            "Empty required OMM mean element field(s): " + ", ".join(empty)
        )
    if not ({"SEMI_MAJOR_AXIS", "MEAN_MOTION"} & data.keys()):
        raise ValueError("OMM requires SEMI_MAJOR_AXIS or MEAN_MOTION")
    if {"SEMI_MAJOR_AXIS", "MEAN_MOTION"} <= data.keys():
        raise ValueError(
            "OMM must contain exactly one of SEMI_MAJOR_AXIS or MEAN_MOTION"
        )

    theory: str = str(data["MEAN_ELEMENT_THEORY"]).upper()
    if theory in {"SGP", "PPT3"}:
        tle_required: set[str] = {"MEAN_MOTION_DOT", "MEAN_MOTION_DDOT"}
    elif theory in {"SGP4", "SGP/SGP4"}:
        tle_required = {"BSTAR"}
    elif theory == "SGP4-XP":
        tle_required = {"BTERM", "AGOM"}
    elif theory in {"DSST", "BROUWER", "BROUWER-LYDDANE", "USM"}:
        # DSST, Brouwer, and USM theories have no special required fields
        # Optional fields (DRAG_AREA, DRAG_COEFF, MASS, SOLAR_RAD_AREA, SOLAR_RAD_COEFF, GM)
        # are utilized when present but not required
        tle_required = set()
    else:
        tle_required = set()
    if tle_required:
        missing = sorted(tle_required - data.keys())
        if missing:
            raise ValueError("Missing required OMM TLE field(s): " + ", ".join(missing))
    covariance_present: set[str] = set(_COVARIANCE_KEYS) & data.keys()
    if covariance_present and covariance_present != set(_COVARIANCE_KEYS):
        missing = sorted(set(_COVARIANCE_KEYS) - covariance_present)
        raise ValueError("Incomplete OMM covariance matrix: " + ", ".join(missing))


# ===================================================================
# Low-level reader (dict-based)
# ===================================================================


# ===================================================================
# Low-level writer (dict-based)
# ===================================================================


# ===================================================================
# Structured dataclass
# ===================================================================


@dataclass
class TleParameters:
    """TLE-related parameters for OMM.

    This section is only required if MEAN_ELEMENT_THEORY = SGP/SGP4.
    Per CCSDS 502.0-B-3 Table 4-3.
    """

    ephemeris_type: int = 0
    """Ephemeris type (0=SGP, 2=SGP4, 3=PPT3, 4=SGP4-XP, 6=Special Perturbations)"""
    classification_type: str = "U"
    """Classification (U=Unclassified, C=Classified, S=Secret)"""
    norad_cat_id: int = 0
    """NORAD catalog ID number (up to 9 digits)"""
    element_set_no: int = DEFAULT_ELEMENT_SET_NUMBER
    """Element set number for this satellite"""
    rev_at_epoch: int = 0
    """Revolution number at epoch"""
    bstar: str = "0"
    """BSTAR drag term (for SGP4) or BTERM ballistic coefficient (for SGP4-XP)"""
    mean_motion_dot: str = "0"
    """First time derivative of mean motion (for SGP or PPT3)"""
    mean_motion_ddot: str = "0"
    """Second time derivative of mean motion (for SGP or PPT3) or AGOM (for SGP4-XP)"""
    bterm: str | None = None
    """Ballistic coefficient for SGP4-XP."""
    agom: str | None = None
    """Solar radiation pressure coefficient for SGP4-XP."""


@dataclass
class OmmSpacecraftParameters:
    """Optional spacecraft physical parameters in OMM file units."""

    mass: float | None = None
    """Spacecraft mass (kg)."""
    solar_rad_area: float | None = None
    """Solar radiation pressure area (m²)."""
    solar_rad_coeff: float | None = None
    """Solar radiation pressure coefficient."""
    drag_area: float | None = None
    """Atmospheric drag area (m²)."""
    drag_coeff: float | None = None
    """Atmospheric drag coefficient."""


@dataclass
class OmmCovariance:
    """Optional symmetric 6x6 position/velocity covariance matrix."""

    matrix: np.ndarray
    """Symmetric position and velocity covariance matrix."""
    ref_frame: str | None = None
    """Reference frame of the covariance matrix, when provided."""


@dataclass
class CcsdsOmm:
    """Parsed CCSDS Orbit Mean-Elements Message.

    All angular quantities are stored in degrees and mean motion in
    revolutions per day, matching the native OMM/TLE representation.
    """

    version: float = DEFAULT_OMM_VERSION
    """CCSDS OMM format version number"""
    creation_date: str = ""
    """File creation date (ISO 8601 format)"""
    originator: str = ""
    """Organization or entity that created the OMM file"""
    classification: str = ""
    """Security classification."""
    message_id: str = ""
    """Optional message identifier."""
    comments: list[str] = field(default_factory=list)
    """List of comment lines from the OMM header"""

    object_name: str = ""
    """Satellite or object name"""
    object_id: str = ""
    """International designator or NORAD catalog number"""
    center_name: str = "EARTH"
    """Central body name (e.g., EARTH, MOON)"""
    ref_frame: str = "ICRF"
    """Reference frame (e.g., ICRF, J2000, EME2000, TEME, ITRF)"""
    time_system: str = "UTC"
    """Time system (e.g., UTC, GPS, TAI)"""
    mean_element_theory: str = "DSST"
    """Mean element theory used (e.g., DSST, USM, SGP4, SGP4-XP)"""

    epoch: str = ""
    """Epoch time (ISO 8601 format)"""
    mean_motion: float = 0.0
    """Mean motion (revolutions per day)"""
    eccentricity: float = 0.0
    """Eccentricity (dimensionless, 0.0 to 1.0)"""
    inclination: float = 0.0
    """Inclination (degrees)"""
    ra_of_asc_node: float = 0.0
    """Right ascension of ascending node (degrees)"""
    arg_of_pericenter: float = 0.0
    """Argument of pericenter (degrees)"""
    mean_anomaly: float = 0.0
    """Mean anomaly (degrees)"""

    tle_parameters: TleParameters | None = None
    """TLE-related parameters (only for SGP/SGP4 mean element theories)"""
    ref_frame_epoch: str = ""
    """Reference-frame epoch when required by the frame definition."""
    semi_major_axis: float | None = None
    """Semi-major axis (km), when used instead of mean motion."""
    gm: float | None = None
    """Gravitational coefficient (km**3/s**2)."""
    spacecraft_parameters: OmmSpacecraftParameters | None = None
    """Optional spacecraft physical parameters."""
    covariance: OmmCovariance | None = None
    """Optional state covariance."""
    data: dict[str, Any] = field(default_factory=dict)
    """Raw parsed fields, including user-defined parameters."""

    def to_dict(self) -> dict[str, object]:
        """Convert to a plain dictionary."""
        return asdict(self)

    @classmethod
    def read(cls, source: TextIO) -> CcsdsOmm:
        """Construct a :class:`CcsdsOmm` from a text stream.

        Parameters
        ----------
        source : TextIO
            Readable text stream.

        Returns
        -------
        CcsdsOmm
            Parsed OMM instance.
        """
        header: dict[str, Any]
        data: dict[str, Any]
        header, data = _read_omm(source)

        # Check if TLE-related parameters are present
        tle_parameters: TleParameters | None = None
        if any(key in data for key in _TLE_PARAMS_KEY_ORDER):
            tle_parameters = TleParameters(
                ephemeris_type=int(data.get("EPHEMERIS_TYPE", 0)),
                classification_type=str(data.get("CLASSIFICATION_TYPE", "U")),
                norad_cat_id=int(data.get("NORAD_CAT_ID", 0)),
                element_set_no=int(
                    data.get("ELEMENT_SET_NO", DEFAULT_ELEMENT_SET_NUMBER)
                ),
                rev_at_epoch=int(data.get("REV_AT_EPOCH", 0)),
                bstar=str(data.get("BSTAR", "0")),
                mean_motion_dot=str(data.get("MEAN_MOTION_DOT", "0")),
                mean_motion_ddot=str(data.get("MEAN_MOTION_DDOT", "0")),
                bterm=str(data["BTERM"]) if "BTERM" in data else None,
                agom=str(data["AGOM"]) if "AGOM" in data else None,
            )

        spacecraft_keys: set[str] = {
            "MASS",
            "SOLAR_RAD_AREA",
            "SOLAR_RAD_COEFF",
            "DRAG_AREA",
            "DRAG_COEFF",
        }
        spacecraft: OmmSpacecraftParameters | None = None
        if spacecraft_keys & data.keys():
            spacecraft = OmmSpacecraftParameters(
                **{
                    key.lower(): float(data[key]) if key in data else None
                    for key in spacecraft_keys
                }
            )

        covariance: OmmCovariance | None = None
        if set(_COVARIANCE_KEYS) <= data.keys():
            matrix: np.ndarray = np.zeros((COVARIANCE_DIMENSION, COVARIANCE_DIMENSION))
            for key, (row, column) in zip(_COVARIANCE_KEYS, _COVARIANCE_POSITIONS):
                matrix[row, column] = float(data[key])
                matrix[column, row] = matrix[row, column]
            covariance = OmmCovariance(matrix, data.get("COV_REF_FRAME"))

        return cls(
            version=float(header.get("CCSDS_OMM_VERS", DEFAULT_OMM_VERSION)),
            creation_date=str(header.get("CREATION_DATE", "")),
            originator=str(header.get("ORIGINATOR", "")),
            classification=str(header.get("CLASSIFICATION", "")),
            message_id=str(header.get("MESSAGE_ID", "")),
            comments=header.get("COMMENT", []),
            object_name=str(data.get("OBJECT_NAME", "")),
            object_id=str(data.get("OBJECT_ID", "")),
            center_name=str(data.get("CENTER_NAME", "EARTH")),
            ref_frame=str(data.get("REF_FRAME", "ICRF")),
            time_system=str(data.get("TIME_SYSTEM", "UTC")),
            mean_element_theory=str(data.get("MEAN_ELEMENT_THEORY", "DSST")),
            ref_frame_epoch=str(data.get("REF_FRAME_EPOCH", "")),
            epoch=str(data.get("EPOCH", "")),
            mean_motion=(float(data["MEAN_MOTION"]) if "MEAN_MOTION" in data else 0.0),
            eccentricity=float(data.get("ECCENTRICITY", 0.0)),
            inclination=float(data.get("INCLINATION", 0.0)),
            ra_of_asc_node=float(data.get("RA_OF_ASC_NODE", 0.0)),
            arg_of_pericenter=float(data.get("ARG_OF_PERICENTER", 0.0)),
            mean_anomaly=float(data.get("MEAN_ANOMALY", 0.0)),
            tle_parameters=tle_parameters,
            semi_major_axis=(
                float(data["SEMI_MAJOR_AXIS"]) if "SEMI_MAJOR_AXIS" in data else None
            ),
            gm=float(data["GM"]) if "GM" in data else None,
            spacecraft_parameters=spacecraft,
            covariance=covariance,
            data=data,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> CcsdsOmm:
        """Read this OMM from a UTF-8 file."""
        with Path(path).open("r", encoding="utf-8") as source:
            return cls.read(source)

    @classmethod
    def from_text(cls, text: str) -> CcsdsOmm:
        """Read this OMM from serialized text."""
        return cls.read(io.StringIO(text))

    def to_text(self) -> str:
        """Serialize this OMM to text."""
        dest = io.StringIO()
        self.write(dest)
        return dest.getvalue()

    def write(self, dest: TextIO) -> None:
        """Write this OMM to a text stream.

        Parameters
        ----------
        dest : TextIO
            Writable text stream.
        """
        header_fields: dict[str, Any] = {
            "CCSDS_OMM_VERS": self.version,
            "CREATION_DATE": self.creation_date,
            "ORIGINATOR": self.originator,
        }
        if self.classification:
            header_fields["CLASSIFICATION"] = self.classification
        if self.message_id:
            header_fields["MESSAGE_ID"] = self.message_id
        if self.comments:
            header_fields["COMMENT"] = self.comments

        data: dict[str, Any] = {
            "OBJECT_NAME": self.object_name,
            "OBJECT_ID": self.object_id,
            "CENTER_NAME": self.center_name,
            "REF_FRAME": self.ref_frame,
            "REF_FRAME_EPOCH": self.ref_frame_epoch,
            "TIME_SYSTEM": self.time_system,
            "MEAN_ELEMENT_THEORY": self.mean_element_theory,
            "EPOCH": self.epoch,
            "MEAN_MOTION": self.mean_motion,
            "ECCENTRICITY": self.eccentricity,
            "INCLINATION": self.inclination,
            "RA_OF_ASC_NODE": self.ra_of_asc_node,
            "ARG_OF_PERICENTER": self.arg_of_pericenter,
            "MEAN_ANOMALY": self.mean_anomaly,
        }
        data.update(self.data)
        if self.semi_major_axis is not None:
            data["SEMI_MAJOR_AXIS"] = self.semi_major_axis
            data.pop("MEAN_MOTION", None)
        if self.gm is not None:
            data["GM"] = self.gm

        # Add TLE-related parameters if present
        if self.tle_parameters is not None:
            data["EPHEMERIS_TYPE"] = self.tle_parameters.ephemeris_type
            data["CLASSIFICATION_TYPE"] = self.tle_parameters.classification_type
            data["NORAD_CAT_ID"] = self.tle_parameters.norad_cat_id
            data["ELEMENT_SET_NO"] = self.tle_parameters.element_set_no
            data["REV_AT_EPOCH"] = self.tle_parameters.rev_at_epoch
            data["BSTAR"] = self.tle_parameters.bstar
            if self.tle_parameters.bterm is not None:
                data["BTERM"] = self.tle_parameters.bterm
            if self.tle_parameters.agom is not None:
                data["AGOM"] = self.tle_parameters.agom
            data["MEAN_MOTION_DOT"] = self.tle_parameters.mean_motion_dot
            data["MEAN_MOTION_DDOT"] = self.tle_parameters.mean_motion_ddot

        if self.spacecraft_parameters is not None:
            for key, value in asdict(self.spacecraft_parameters).items():
                if value is not None:
                    data[key.upper()] = value

        if self.covariance is not None:
            if self.covariance.ref_frame is not None:
                data["COV_REF_FRAME"] = self.covariance.ref_frame
            data.update(
                {
                    key: self.covariance.matrix[row, column]
                    for key, (row, column) in zip(
                        _COVARIANCE_KEYS, _COVARIANCE_POSITIONS
                    )
                }
            )

        _write_omm(dest, header_fields, data)

    def to_file(self, path: str | Path) -> None:
        """Write this OMM to a UTF-8 file."""
        with Path(path).open("w", encoding="utf-8", newline="\n") as dest:
            self.write(dest)

    def __repr__(self) -> str:
        """Return a concise string representation of this OMM instance."""
        norad_id: int | str = (
            self.tle_parameters.norad_cat_id if self.tle_parameters else "N/A"
        )
        return (
            f"CcsdsOmm(object={self.object_name!r}, "
            f"norad_cat_id={norad_id}, "
            f"epoch={self.epoch!r})"
        )

    @staticmethod
    def _try_numeric(value: str) -> int | float | str:
        """Attempt to convert a CCSDS value to int or float."""
        value = value.strip()
        if "[" in value:
            value = value.split("[", 1)[0].strip()
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    @staticmethod
    def _write_value(key: str, value: Any) -> str:
        unit = _UNIT_BY_KEY.get(key)
        if key == "CCSDS_OMM_VERS":
            value_text = f"{float(value):.1f}"
        elif isinstance(value, (float, np.floating)):
            value_text = f"{value:.15g}"
        else:
            value_text = str(value)
        return f"{value_text} [{unit}]" if unit else value_text


def _read_omm(
    source: TextIO,
    *,
    validate: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read an OMM file and return *(header, data)*.

    Parameters
    ----------
    source : TextIO | str | Path
        A readable text stream, file path string, or :class:`Path`.

    Returns
    -------
    tuple[dict[str, Any], dict[str, Any]]
        A 2-tuple of ``(header, data)`` where *header* contains file-level
        keywords (``CCSDS_OMM_VERS``, ``CREATION_DATE``, ``ORIGINATOR``,
        and any ``COMMENT`` lines), and *data* contains all remaining
        keyword-value pairs (metadata, mean elements, and TLE parameters).
    """
    if isinstance(source, (str, Path)):
        with Path(source).open("r", encoding="utf-8") as file_handle:
            return _read_omm(file_handle, validate=validate)

    header: dict[str, Any] = {}
    data: dict[str, Any] = {}
    seen_header: list[str] = []
    seen_data: list[str] = []
    current_group = -1
    comment_group: int | None = None
    first_line = True
    mean_keys = [
        "EPOCH",
        "SEMI_MAJOR_AXIS",
        "MEAN_MOTION",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
        "GM",
    ]
    covariance_keys = list(_COVARIANCE_KEYS)
    data_groups = [
        _META_KEY_ORDER,
        mean_keys,
        list(_SPACECRAFT_KEY_ORDER),
        _TLE_PARAMS_KEY_ORDER,
        ["COV_REF_FRAME", *covariance_keys],
    ]

    for raw_line in source:
        raw_line = raw_line.rstrip("\r\n")
        if len(raw_line) > 254:
            raise ValueError("OMM line exceeds the 254-character limit")
        if any(ord(char) < 32 or ord(char) > 126 for char in raw_line):
            raise ValueError("OMM lines must contain printable ASCII only")
        line: str = raw_line.strip()
        if not line:
            continue
        if first_line:
            first_line = False
            assignment = misc.parse_key_value_line(line)
            if assignment is None or assignment[0] != "CCSDS_OMM_VERS":
                raise ValueError("CCSDS_OMM_VERS must be the first non-blank OMM line")

        comment_line = raw_line.lstrip(" ")
        if comment_line.startswith("COMMENT"):
            if not comment_line.startswith("COMMENT "):
                raise ValueError("OMM comments must begin with 'COMMENT '")
            header_comment = not seen_data and seen_header == ["CCSDS_OMM_VERS"]
            if seen_data:
                if comment_group is None:
                    comment_group = current_group + 1
            elif {
                "CCSDS_OMM_VERS",
                "CREATION_DATE",
                "ORIGINATOR",
            } <= set(seen_header):
                comment_group = 0
            elif not header_comment:
                raise ValueError("OMM header comments must follow the version")
            comment_text = comment_line[len("COMMENT ") :]
            header.setdefault("COMMENT", [])
            header["COMMENT"].append(comment_text)
            continue

        key_value: tuple[str, str] | None = misc.parse_key_value_line(line)
        if key_value is None:
            raise ValueError(f"Invalid OMM KVN line: {line}")

        key, value = key_value
        if not key.isupper() or " " in key:
            raise ValueError(f"Invalid OMM keyword: {key}")
        if key in _HEADER_KEYS:
            if seen_data:
                raise ValueError(f"OMM header keyword {key} appears after data")
            if key in seen_header:
                raise ValueError(f"Duplicate OMM keyword: {key}")
            if _HEADER_KEY_ORDER.index(key) < max(
                (_HEADER_KEY_ORDER.index(item) for item in seen_header), default=-1
            ):
                raise ValueError(f"OMM header keyword out of order: {key}")
            seen_header.append(key)
            _validate_omm_value(key, value)
            header[key] = CcsdsOmm._try_numeric(value) if value else value
            continue

        if key not in {
            item for group in data_groups for item in group
        } and not re.fullmatch(r"USER_DEFINED_[A-Z0-9_]+", key):
            raise ValueError(f"Unsupported OMM keyword: {key}")
        group_index = next(
            (index for index, group in enumerate(data_groups) if key in group),
            len(data_groups),
        )
        if key in seen_data:
            raise ValueError(f"Duplicate OMM keyword: {key}")
        if comment_group is not None:
            if group_index < comment_group:
                raise ValueError(
                    "OMM comments must appear at the beginning of a data block"
                )
            comment_group = None
        if group_index < current_group:
            raise ValueError(f"OMM keyword out of order: {key}")
        group = data_groups[group_index] if group_index < len(data_groups) else []
        if key in group:
            prior_group_keys = [item for item in seen_data if item in group]
            if prior_group_keys and group.index(key) < group.index(
                prior_group_keys[-1]
            ):
                raise ValueError(f"OMM keyword out of order: {key}")
        current_group = group_index
        seen_data.append(key)
        _validate_omm_value(key, value)

        data[key] = CcsdsOmm._try_numeric(value) if value else value

    if validate:
        validate_omm(header, data)
    return header, data


def _write_omm(
    dest: TextIO,
    header: dict[str, Any],
    data: dict[str, Any],
) -> None:
    """Write an OMM file from *(header, data)* dicts.

    Parameters
    ----------
    dest : TextIO | str | Path
        A writable text stream, file path string, or :class:`Path`.
    header : dict[str, Any]
        File-level keywords (``CCSDS_OMM_VERS``, ``CREATION_DATE``,
        ``ORIGINATOR``, and optionally ``COMMENT``).
    data : dict[str, Any]
        All remaining keyword-value pairs (metadata, mean elements,
        and TLE parameters).
    """
    if isinstance(dest, (str, Path)):
        with Path(dest).open("w", encoding="utf-8", newline="\n") as file_handle:
            _write_omm(file_handle, header, data)
        return
    validation_header = {
        "CCSDS_OMM_VERS": header.get("CCSDS_OMM_VERS", DEFAULT_OMM_VERSION),
        **{key: value for key, value in header.items() if key != "COMMENT"},
    }
    validate_omm(validation_header, data)

    def write_text(text: str) -> int:
        if any(
            ord(char) < 32 and char not in "\r\n" or ord(char) > 126 for char in text
        ):
            raise ValueError("OMM output must contain printable ASCII only")
        for line in text.split("\n"):
            line = line.rstrip("\r")
            if len(line) > 254:
                raise ValueError("OMM line exceeds the 254-character limit")
        return dest.write(text)

    # --- Header ---
    version: float | int = header.get("CCSDS_OMM_VERS", DEFAULT_OMM_VERSION)
    write_text(f"CCSDS_OMM_VERS = {CcsdsOmm._write_value('CCSDS_OMM_VERS', version)}\n")

    for comment in header.get("COMMENT", []):
        write_text(f"COMMENT {comment}\n")

    if "CLASSIFICATION" in header:
        write_text(f"CLASSIFICATION = {header['CLASSIFICATION']}\n")

    creation_date: str | int | float = header.get("CREATION_DATE", "")
    write_text(f"CREATION_DATE  = {creation_date}\n")

    originator: str | int | float = header.get("ORIGINATOR", "")
    write_text(f"ORIGINATOR     = {originator}\n")

    if "MESSAGE_ID" in header:
        write_text(f"MESSAGE_ID     = {header['MESSAGE_ID']}\n")

    write_text("\n")

    # --- Metadata section ---
    for key in _META_KEY_ORDER:
        if key in data and data[key] != "":
            write_text(
                f"{key:<{max(MINIMUM_OMM_KEY_WIDTH, len(key))}} = {CcsdsOmm._write_value(key, data[key])}\n"
            )

    write_text("\n")

    # --- Mean elements section ---
    for key in _MEAN_ELEMENTS_KEY_ORDER:
        if key in data and data[key] != "":
            write_text(
                f"{key:<{max(MINIMUM_OMM_KEY_WIDTH, len(key))}} = {CcsdsOmm._write_value(key, data[key])}\n"
            )

    write_text("\n")

    for key in _SPACECRAFT_KEY_ORDER:
        if key in data and data[key] != "":
            write_text(
                f"{key:<{max(MINIMUM_OMM_KEY_WIDTH, len(key))}} = {CcsdsOmm._write_value(key, data[key])}\n"
            )

    if any(key in data for key in _SPACECRAFT_KEY_ORDER):
        write_text("\n")

    # --- TLE-related parameters section ---
    for key in _TLE_PARAMS_KEY_ORDER:
        if key in data and data[key] != "":
            write_text(
                f"{key:<{max(MINIMUM_OMM_KEY_WIDTH, len(key))}} = {CcsdsOmm._write_value(key, data[key])}\n"
            )

    for key in ("COV_REF_FRAME", *_COVARIANCE_KEYS):
        if key in data and data[key] != "":
            write_text(
                f"{key:<{max(MINIMUM_OMM_KEY_WIDTH, len(key))}} = "
                f"{CcsdsOmm._write_value(key, data[key])}\n"
            )

    user_defined_keys = sorted(
        key for key in data if re.fullmatch(r"USER_DEFINED_[A-Z0-9_]+", key)
    )
    unsupported = set(data) - set(
        _META_KEY_ORDER
        + _MEAN_ELEMENTS_KEY_ORDER
        + _TLE_PARAMS_KEY_ORDER
        + list(_SPACECRAFT_KEY_ORDER)
        + ["COV_REF_FRAME", *_COVARIANCE_KEYS]
        + user_defined_keys
    )
    if unsupported:
        raise ValueError(
            "Unsupported OMM keyword(s): " + ", ".join(sorted(unsupported))
        )
    for key in user_defined_keys:
        write_text(
            f"{key:<{max(MINIMUM_OMM_KEY_WIDTH, len(key))}} = {CcsdsOmm._write_value(key, data[key])}\n"
        )

    write_text("\n")


def keplerian_to_omm(
    epoch: datetime,
    keplerian_elements: np.ndarray,
    object_name: str = "OBJECT",
    object_id: str = "UNKNOWN",
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    ref_frame: str = "ICRF",
    mean_element_theory: str = "DSST",
) -> CcsdsOmm:
    """Convert Keplerian elements to OMM format.

    Generates an OMM compliant with CCSDS 502.0-B-3 (2023-04) standard.
    This function is for general mean element representations, not specifically
    for TLE/SGP4 format. For TLE-specific OMMs, use appropriate TLE conversion
    functions.

    Parameters
    ----------
    epoch : datetime
        Reference epoch (UTC).
    keplerian_elements : np.ndarray
        Keplerian elements (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in meters, angles in radians.
        Note: Last element should be mean anomaly for mean element theories.
    object_name : str
        Satellite or object name. Defaults to "OBJECT".
        Recommended to use names from UN Office of Outer Space Affairs
        designator index when available.
    object_id : str
        International designator. Defaults to "UNKNOWN".
        Recommended format: YYYY-NNNP{PP} (e.g., "2023-100A").
    mu_m3_s2 : float
        Gravitational parameter (m³/s²). Defaults to Earth's standard
        gravitational parameter.
    ref_frame : str
        Reference frame for the elements. Defaults to "ICRF".
        Common values: "ICRF", "J2000", "EME2000", "ITRF2000".
        Note: Use "TEME" only for TLE-based OMMs.
    mean_element_theory : str
        Mean element theory. Defaults to "DSST".
        Valid values per CCSDS 502.0-B-3 Table 4-2:
        "DSST" (Draper Semi-analytical Satellite Theory),
        "USM" (Universal Semianalytical Method),
        or other user-defined theories.
        Note: Use "SGP4" or "SGP4-XP" only for TLE-based OMMs.

    Returns
    -------
    CcsdsOmm
        OMM object with converted elements, compliant with CCSDS 502.0-B-3.

    Notes
    -----
    - This function does NOT generate TLE-related parameters (BSTAR,
      MEAN_MOTION_DOT, etc.) as it is not intended for TLE/SGP4 use.
    - Per CCSDS 502.0-B-3 Table 4-3, SEMI_MAJOR_AXIS is preferred over
      MEAN_MOTION for non-SGP4 theories. However, MEAN_MOTION is provided
      for compatibility.
    - The input should ideally be mean elements, not osculating elements,
      for proper OMM representation.
    """
    # Extract Keplerian elements
    a_m: float = keplerian_elements[kepler.SEMI_MAJOR_AXIS_INDEX]
    e: float = keplerian_elements[kepler.ECCENTRICITY_INDEX]
    i_rad: float = keplerian_elements[kepler.INCLINATION_INDEX]
    omega_rad: float = keplerian_elements[kepler.ARGUMENT_OF_PERIAPSIS_INDEX]
    raan_rad: float = keplerian_elements[kepler.RAAN_INDEX]
    theta_rad: float = keplerian_elements[kepler.TRUE_ANOMALY_INDEX]

    # Convert true anomaly to mean anomaly if needed
    mean_anomaly_rad: float = kepler.true_to_mean_anomaly(theta_rad, e)

    # Compute mean motion (rev/day) from semi-major axis
    mean_motion_rev_per_day: float = kepler.semi_major_axis_to_mean_motion(
        a_m, mu_m3_s2
    )

    # Format epoch as ISO 8601 (per CCSDS 502.0-B-3 section 7.5.10)
    epoch_str: str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)

    # Create OMM object compliant with CCSDS 502.0-B-3
    # Note: TLE-related parameters are NOT included (set to None) as this is not a TLE-based OMM
    omm_message: CcsdsOmm = CcsdsOmm(
        version=DEFAULT_OMM_VERSION,  # CCSDS 502.0-B-3 (2023-04)
        creation_date=time_utils.datetime_to_iso8601(
            datetime.now(timezone.utc), fractional_second_places=3
        ),
        originator="ephem-toolkit",
        comments=[
            "Mean Keplerian elements",
            "Compliant with CCSDS 502.0-B-3 (2023-04)",
        ],
        object_name=object_name,
        object_id=object_id,
        center_name="EARTH",
        ref_frame=ref_frame,  # User-specified, defaults to ICRF
        time_system="UTC",
        mean_element_theory=mean_element_theory,  # User-specified, defaults to DSST
        epoch=epoch_str,
        mean_motion=mean_motion_rev_per_day,
        eccentricity=e,
        inclination=np.degrees(i_rad),
        ra_of_asc_node=np.degrees(raan_rad),
        arg_of_pericenter=np.degrees(omega_rad),
        mean_anomaly=np.degrees(mean_anomaly_rad),
        tle_parameters=None,  # No TLE parameters for non-TLE OMMs
    )

    return omm_message
