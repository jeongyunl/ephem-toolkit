"""Read, parse, and write CCSDS Orbit Parameter Message (OPM) files.

References:
    https://public.ccsds.org/Pubs/502x0b3e1.pdf
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from . import odm
from .. import misc

DEFAULT_OPM_VERSION: float = 3.0
"""Default CCSDS OPM version (2023-04 standard)."""

COVARIANCE_DIMENSION: int = 6
"""Number of position and velocity components in the covariance matrix."""

_HEADER_KEYS: set[str] = {
    "CCSDS_OPM_VERS",
    "CLASSIFICATION",
    "CREATION_DATE",
    "ORIGINATOR",
    "MESSAGE_ID",
}
"""Supported OPM header keys."""

_METADATA_KEYS: set[str] = {
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "REF_FRAME_EPOCH",
    "TIME_SYSTEM",
}
_HEADER_ORDER: tuple[str, ...] = (
    "CCSDS_OPM_VERS",
    "CLASSIFICATION",
    "CREATION_DATE",
    "ORIGINATOR",
    "MESSAGE_ID",
)
_METADATA_ORDER: tuple[str, ...] = (
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "REF_FRAME_EPOCH",
    "TIME_SYSTEM",
)
_STATE_ORDER: tuple[str, ...] = (
    "EPOCH",
    "X",
    "Y",
    "Z",
    "X_DOT",
    "Y_DOT",
    "Z_DOT",
)
_KEPLERIAN_ORDER: tuple[str, ...] = (
    "SEMI_MAJOR_AXIS",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "TRUE_ANOMALY",
    "MEAN_ANOMALY",
    "GM",
)
_SPACECRAFT_ORDER: tuple[str, ...] = (
    "MASS",
    "SOLAR_RAD_AREA",
    "SOLAR_RAD_COEFF",
    "DRAG_AREA",
    "DRAG_COEFF",
)
"""Supported OPM metadata keys."""

_MANEUVER_KEYS: tuple[str, ...] = (
    "MAN_EPOCH_IGNITION",
    "MAN_DURATION",
    "MAN_DELTA_MASS",
    "MAN_REF_FRAME",
    "MAN_DV_1",
    "MAN_DV_2",
    "MAN_DV_3",
)
"""OPM maneuver keys in file order."""

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
"""OPM covariance keys in lower-triangular matrix order."""

_COVARIANCE_POSITIONS: tuple[tuple[int, int], ...] = (
    (0, 0),
    (1, 0),
    (1, 1),
    (2, 0),
    (2, 1),
    (2, 2),
    (3, 0),
    (3, 1),
    (3, 2),
    (3, 3),
    (4, 0),
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (5, 0),
    (5, 1),
    (5, 2),
    (5, 3),
    (5, 4),
    (5, 5),
)
"""Row and column indices corresponding to the covariance keys."""

_UNIT_BY_KEY: dict[str, str] = {
    "X": "km",
    "Y": "km",
    "Z": "km",
    "X_DOT": "km/s",
    "Y_DOT": "km/s",
    "Z_DOT": "km/s",
    "SEMI_MAJOR_AXIS": "km",
    "INCLINATION": "deg",
    "RA_OF_ASC_NODE": "deg",
    "ARG_OF_PERICENTER": "deg",
    "TRUE_ANOMALY": "deg",
    "MEAN_ANOMALY": "deg",
    "GM": "km**3/s**2",
    "MASS": "kg",
    "SOLAR_RAD_AREA": "m**2",
    "DRAG_AREA": "m**2",
    "MAN_DURATION": "s",
    "MAN_DELTA_MASS": "kg",
    "MAN_DV_1": "km/s",
    "MAN_DV_2": "km/s",
    "MAN_DV_3": "km/s",
}
"""Native OPM units keyed by field name."""

_KEPLERIAN_KEYS: set[str] = {
    "SEMI_MAJOR_AXIS",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "GM",
}
"""Keys required when OPM osculating Keplerian elements are present."""
_UNIT_BY_KEY.update(
    {key: "km**2" for key in ("CX_X", "CY_X", "CY_Y", "CZ_X", "CZ_Y", "CZ_Z")}
)


def _validate_opm_value(key: str, value: str) -> None:
    """Validate an OPM value's generic ODM time, numeric, and unit syntax."""
    if not value:
        raise ValueError(f"OPM keyword {key} has an empty value")
    if "[n/a]" in value.lower():
        raise ValueError("[n/a] is not permitted in an OPM")
    unit_match = re.search(r"\s+\[([^\]]+)\]$", value)
    if "[" in value or "]" in value:
        if unit_match is None:
            raise ValueError(f"Invalid unit notation for OPM keyword {key}")
        if _UNIT_BY_KEY.get(key) != unit_match.group(1):
            raise ValueError(f"Invalid unit for OPM keyword {key}")
        value = value[: unit_match.start()].rstrip()
    time_keys = {"CREATION_DATE", "REF_FRAME_EPOCH", "EPOCH", "MAN_EPOCH_IGNITION"}
    if key in time_keys:
        pattern = r"\d{4}-(?:\d{2}-\d{2}|\d{3})T\d{2}:\d{2}:\d{2}(?:\.\d{1,16})?Z?"
        if not re.fullmatch(pattern, value):
            raise ValueError(f"Invalid OPM time value for {key}: {value}")
        if re.match(r"\d{4}-\d{2}-\d{2}T", value):
            normalized = value.removesuffix("Z")
            try:
                datetime.strptime(normalized.split(".")[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError as exc:
                if not re.search(r"T\d{2}:\d{2}:60(?:\.|$)", normalized):
                    raise ValueError(
                        f"Invalid OPM time value for {key}: {value}"
                    ) from exc
    numeric_keys = set(_UNIT_BY_KEY) | {
        "ECCENTRICITY",
        "MAN_DURATION",
        "MAN_DELTA_MASS",
        *_COVARIANCE_KEYS,
    }
    if key in numeric_keys:
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?", value):
            raise ValueError(f"Invalid numeric value for OPM keyword {key}: {value}")
        if re.search("[Ee]", value) and not re.fullmatch(
            r"[+-]?\d+\.\d+[Ee][+-]?\d+", value
        ):
            raise ValueError(f"Invalid floating-point value for OPM keyword {key}")
        mantissa = re.split("[Ee]", value)[0].lstrip("+-").replace(".", "")
        if len(mantissa.lstrip("0")) > 16:
            raise ValueError(f"Too many significant digits for OPM keyword {key}")
        if not math.isfinite(float(value)):
            raise ValueError(f"Non-finite numeric value for OPM keyword {key}")


def _format_opm_number(value: Any) -> str:
    if isinstance(value, float):
        formatted = format(value, ".16g").replace("e", "E")
        if "E" in formatted:
            mantissa, exponent = formatted.split("E", 1)
            if "." not in mantissa:
                formatted = f"{mantissa}.0E{exponent}"
        return formatted
    return str(value)


_UNIT_BY_KEY.update(
    {
        key: "km**2/s"
        for key in (
            "CX_DOT_X",
            "CX_DOT_Y",
            "CX_DOT_Z",
            "CY_DOT_X",
            "CY_DOT_Y",
            "CY_DOT_Z",
            "CZ_DOT_X",
            "CZ_DOT_Y",
            "CZ_DOT_Z",
        )
    }
)
_UNIT_BY_KEY.update(
    {
        key: "km**2/s**2"
        for key in (
            "CX_DOT_X_DOT",
            "CY_DOT_X_DOT",
            "CY_DOT_Y_DOT",
            "CZ_DOT_X_DOT",
            "CZ_DOT_Y_DOT",
            "CZ_DOT_Z_DOT",
        )
    }
)


def validate_opm(
    header: dict[str, Any], metadata: dict[str, Any], data: dict[str, Any]
) -> None:
    """Validate mandatory and conditional CCSDS OPM fields.

    Parameters
    ----------
    header : dict[str, Any]
        File-level OPM keywords.
    metadata : dict[str, Any]
        Object and reference-frame metadata.
    data : dict[str, Any]
        State, optional element, covariance, and maneuver values.

    Raises
    ------
    ValueError
        If a required field or a conditional block is incomplete.
    """
    required_header: set[str] = {"CCSDS_OPM_VERS", "CREATION_DATE", "ORIGINATOR"}
    required_metadata: set[str] = {
        "OBJECT_NAME",
        "OBJECT_ID",
        "CENTER_NAME",
        "REF_FRAME",
        "TIME_SYSTEM",
    }
    required_state: set[str] = {
        "EPOCH",
        "X",
        "Y",
        "Z",
        "X_DOT",
        "Y_DOT",
        "Z_DOT",
    }
    for name, required, values in (
        ("header", required_header, header),
        ("metadata", required_metadata, metadata),
        ("state vector", required_state, data),
    ):
        missing: list[str] = sorted(required - values.keys())
        if missing:
            raise ValueError(
                f"Missing required OPM {name} field(s): {', '.join(missing)}"
            )
    allowed_header = set(_HEADER_KEYS) | {"COMMENT"}
    allowed_metadata = set(_METADATA_KEYS) | {"COMMENT"}
    allowed_data = (
        set(_STATE_ORDER)
        | set(_KEPLERIAN_ORDER)
        | set(_SPACECRAFT_ORDER)
        | {"COV_REF_FRAME", *_COVARIANCE_KEYS, "MANEUVERS", "COMMENT"}
    )
    allowed_data.update(
        key for key in data if re.fullmatch(r"USER_DEFINED_[A-Z0-9_]+", key)
    )
    for name, values, allowed in (
        ("header", header, allowed_header),
        ("metadata", metadata, allowed_metadata),
        ("data", data, allowed_data),
    ):
        unknown = values.keys() - allowed
        if unknown:
            raise ValueError(
                f"Unsupported OPM {name} keyword(s): {', '.join(sorted(unknown))}"
            )
    for values in (header, metadata, data):
        for key, value in values.items():
            if (
                key == "COMMENT"
                or key == "MANEUVERS"
                or key.startswith("USER_DEFINED_")
            ):
                continue
            formatted = (
                _format_opm_number(value)
                if isinstance(value, (int, float))
                else str(value)
            )
            _validate_opm_value(key, formatted)

    odm.validate_odm_context(
        str(metadata["CENTER_NAME"]),
        str(metadata["REF_FRAME"]),
        str(metadata["TIME_SYSTEM"]),
    )

    keplerian_present: set[str] = _KEPLERIAN_KEYS & data.keys()
    anomaly_present: set[str] = {"TRUE_ANOMALY", "MEAN_ANOMALY"} & data.keys()
    if keplerian_present or anomaly_present:
        if len(anomaly_present) == 2:
            raise ValueError(
                "OPM must contain exactly one of TRUE_ANOMALY or MEAN_ANOMALY"
            )
        missing = sorted(_KEPLERIAN_KEYS - data.keys())
        if not anomaly_present:
            missing.append("TRUE_ANOMALY or MEAN_ANOMALY")
        if missing:
            raise ValueError(
                "Incomplete OPM Keplerian element set: " + ", ".join(missing)
            )

    covariance_present: set[str] = _COVARIANCE_KEYS & data.keys()
    if covariance_present and covariance_present != set(_COVARIANCE_KEYS):
        missing = sorted(set(_COVARIANCE_KEYS) - covariance_present)
        raise ValueError("Incomplete OPM covariance matrix: " + ", ".join(missing))

    maneuvers: list[dict[str, Any]] = data.get("MANEUVERS", [])
    if maneuvers and "MASS" not in data:
        raise ValueError("OPM MASS is required when maneuvers are present")
    for index, maneuver in enumerate(maneuvers, start=1):
        unknown = maneuver.keys() - set(_MANEUVER_KEYS)
        if unknown:
            raise ValueError(
                f"Unsupported OPM maneuver keyword(s): {', '.join(sorted(unknown))}"
            )
        for key, value in maneuver.items():
            _validate_opm_value(key, _format_opm_number(value))
        delta_mass = maneuver.get("MAN_DELTA_MASS")
        if delta_mass is not None and float(delta_mass) >= 0:
            raise ValueError(f"OPM maneuver {index} MAN_DELTA_MASS must be negative")


@dataclass
class OpmHeader:
    """CCSDS OPM header fields."""

    version: float = DEFAULT_OPM_VERSION
    """CCSDS OPM format version."""
    comments: list[str] = field(default_factory=list)
    """Header comments."""
    classification: str = ""
    """Security classification."""
    creation_date: str = ""
    """Message creation date in CCSDS time format."""
    originator: str = ""
    """Organization that created the message."""
    message_id: str = ""
    """Optional message identifier."""


@dataclass
class OpmStateVector:
    """Cartesian state vector in OPM file units."""

    epoch: str = ""
    """State epoch in CCSDS time format."""
    x: float = 0.0
    """X position (km)."""
    y: float = 0.0
    """Y position (km)."""
    z: float = 0.0
    """Z position (km)."""
    x_dot: float = 0.0
    """X velocity (km/s)."""
    y_dot: float = 0.0
    """Y velocity (km/s)."""
    z_dot: float = 0.0
    """Z velocity (km/s)."""

    @property
    def values(self) -> np.ndarray:
        """Return the state as a six-element NumPy array."""
        return np.array([self.x, self.y, self.z, self.x_dot, self.y_dot, self.z_dot])


@dataclass
class OpmKeplerianElements:
    """Optional osculating Keplerian elements in OPM file units."""

    semi_major_axis: float
    """Semi-major axis (km)."""
    eccentricity: float
    """Eccentricity (dimensionless)."""
    inclination: float
    """Inclination (degrees)."""
    ra_of_asc_node: float
    """Right ascension of the ascending node (degrees)."""
    arg_of_pericenter: float
    """Argument of pericenter (degrees)."""
    gm: float
    """Gravitational parameter (km³/s²)."""
    true_anomaly: float | None = None
    """True anomaly (degrees), when present."""
    mean_anomaly: float | None = None
    """Mean anomaly (degrees), when present."""


@dataclass
class OpmSpacecraftParameters:
    """Optional spacecraft physical parameters in OPM file units."""

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
class OpmCovariance:
    """Optional symmetric 6x6 position/velocity covariance matrix."""

    matrix: np.ndarray
    """Symmetric position/velocity covariance matrix in OPM units."""
    ref_frame: str | None = None
    """Covariance reference frame, when specified."""


@dataclass
class OpmManeuver:
    """Finite maneuver parameters in OPM file units."""

    man_epoch_ignition: str = ""
    """Maneuver ignition epoch in CCSDS time format."""
    man_duration: float = 0.0
    """Maneuver duration (s)."""
    man_delta_mass: float = 0.0
    """Spacecraft mass change (kg)."""
    man_ref_frame: str = ""
    """Maneuver delta-v reference frame."""
    man_dv_1: float = 0.0
    """First delta-v component (km/s)."""
    man_dv_2: float = 0.0
    """Second delta-v component (km/s)."""
    man_dv_3: float = 0.0
    """Third delta-v component (km/s)."""


@dataclass
class CcsdsOpm:
    """Structured CCSDS Orbit Parameter Message."""

    header: OpmHeader
    """Parsed OPM header."""
    metadata: dict[str, Any]
    """OPM metadata fields keyed by CCSDS name."""
    state_vector: OpmStateVector
    """Required Cartesian state vector."""
    keplerian_elements: OpmKeplerianElements | None = None
    """Optional osculating Keplerian elements."""
    spacecraft_parameters: OpmSpacecraftParameters | None = None
    """Optional spacecraft physical parameters."""
    covariance: OpmCovariance | None = None
    """Optional state covariance."""
    data: dict[str, Any] = field(default_factory=dict)
    """Raw parsed data fields keyed by CCSDS name."""
    maneuvers: list[OpmManeuver] = field(default_factory=list)
    """Parsed finite maneuvers."""

    @classmethod
    def read(cls, source: TextIO) -> "CcsdsOpm":
        """Construct a structured OPM message from a file or text stream.

        Parameters
        ----------
        source : TextIO or str or Path
            OPM content or the path to an OPM file.

        Returns
        -------
        CcsdsOpm
            Parsed structured OPM message.
        """
        header, metadata, data = _read_opm(source)
        state: OpmStateVector = OpmStateVector(
            epoch=str(data.get("EPOCH", "")),
            **{
                name: float(data.get(key, 0.0))
                for name, key in {
                    "x": "X",
                    "y": "Y",
                    "z": "Z",
                    "x_dot": "X_DOT",
                    "y_dot": "Y_DOT",
                    "z_dot": "Z_DOT",
                }.items()
            },
        )
        header_obj: OpmHeader = OpmHeader(
            float(header.get("CCSDS_OPM_VERS", DEFAULT_OPM_VERSION)),
            list(header.get("COMMENT", [])),
            str(header.get("CLASSIFICATION", "")),
            str(header.get("CREATION_DATE", "")),
            str(header.get("ORIGINATOR", "")),
            str(header.get("MESSAGE_ID", "")),
        )
        keplerian: OpmKeplerianElements | None = None
        if _KEPLERIAN_KEYS & data.keys():
            keplerian = OpmKeplerianElements(
                semi_major_axis=float(data["SEMI_MAJOR_AXIS"]),
                eccentricity=float(data["ECCENTRICITY"]),
                inclination=float(data["INCLINATION"]),
                ra_of_asc_node=float(data["RA_OF_ASC_NODE"]),
                arg_of_pericenter=float(data["ARG_OF_PERICENTER"]),
                gm=float(data["GM"]),
                true_anomaly=(
                    float(data["TRUE_ANOMALY"]) if "TRUE_ANOMALY" in data else None
                ),
                mean_anomaly=(
                    float(data["MEAN_ANOMALY"]) if "MEAN_ANOMALY" in data else None
                ),
            )
        spacecraft_keys: set[str] = {
            "MASS",
            "SOLAR_RAD_AREA",
            "SOLAR_RAD_COEFF",
            "DRAG_AREA",
            "DRAG_COEFF",
        }
        spacecraft: OpmSpacecraftParameters | None = None
        if spacecraft_keys & data.keys():
            spacecraft = OpmSpacecraftParameters(
                **{
                    key.lower(): float(data[key]) if key in data else None
                    for key in spacecraft_keys
                }
            )
        covariance: OpmCovariance | None = None
        if set(_COVARIANCE_KEYS) <= data.keys():
            matrix: np.ndarray = np.zeros((COVARIANCE_DIMENSION, COVARIANCE_DIMENSION))
            for key, (row, column) in zip(_COVARIANCE_KEYS, _COVARIANCE_POSITIONS):
                matrix[row, column] = float(data[key])
                matrix[column, row] = matrix[row, column]
            covariance = OpmCovariance(matrix, data.get("COV_REF_FRAME"))
        maneuvers: list[OpmManeuver] = [
            OpmManeuver(**{name.lower(): value for name, value in item.items()})
            for item in data.get("MANEUVERS", [])
        ]
        return cls(
            header=header_obj,
            metadata=metadata,
            state_vector=state,
            keplerian_elements=keplerian,
            spacecraft_parameters=spacecraft,
            covariance=covariance,
            data=data,
            maneuvers=maneuvers,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the structured OPM message as a dictionary."""
        return asdict(self)

    @classmethod
    def from_file(cls, path: str | Path) -> "CcsdsOpm":
        """Read this OPM from a UTF-8 file."""
        with Path(path).open("r", encoding="utf-8") as source:
            return cls.read(source)

    @classmethod
    def from_text(cls, text: str) -> "CcsdsOpm":
        """Read this OPM from serialized text."""
        return cls.read(io.StringIO(text))

    def to_text(self) -> str:
        """Serialize this OPM to text."""
        dest = io.StringIO()
        self.write(dest)
        return dest.getvalue()

    def write(self, dest: TextIO) -> None:
        """Write this structured OPM message to a text stream.

        Parameters
        ----------
        dest : TextIO
            Destination text stream.
        """
        header: dict[str, Any] = {
            "CCSDS_OPM_VERS": self.header.version,
            "COMMENT": self.header.comments,
            "CREATION_DATE": self.header.creation_date,
            "ORIGINATOR": self.header.originator,
        }
        if self.header.classification:
            header["CLASSIFICATION"] = self.header.classification
        if self.header.message_id:
            header["MESSAGE_ID"] = self.header.message_id
        data: dict[str, Any] = dict(self.data)
        data.update(
            {
                "EPOCH": self.state_vector.epoch,
                "X": self.state_vector.x,
                "Y": self.state_vector.y,
                "Z": self.state_vector.z,
                "X_DOT": self.state_vector.x_dot,
                "Y_DOT": self.state_vector.y_dot,
                "Z_DOT": self.state_vector.z_dot,
            }
        )
        if self.keplerian_elements is not None:
            data.update(
                {
                    "SEMI_MAJOR_AXIS": self.keplerian_elements.semi_major_axis,
                    "ECCENTRICITY": self.keplerian_elements.eccentricity,
                    "INCLINATION": self.keplerian_elements.inclination,
                    "RA_OF_ASC_NODE": self.keplerian_elements.ra_of_asc_node,
                    "ARG_OF_PERICENTER": self.keplerian_elements.arg_of_pericenter,
                    "GM": self.keplerian_elements.gm,
                }
            )
            if self.keplerian_elements.true_anomaly is not None:
                data["TRUE_ANOMALY"] = self.keplerian_elements.true_anomaly
            if self.keplerian_elements.mean_anomaly is not None:
                data["MEAN_ANOMALY"] = self.keplerian_elements.mean_anomaly
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
        data["MANEUVERS"] = [
            {key.upper(): value for key, value in asdict(item).items()}
            for item in self.maneuvers
        ]
        _write_opm(dest, header, self.metadata, data)

    def to_file(self, path: str | Path) -> None:
        """Write this OPM to a UTF-8 file."""
        with Path(path).open("w", encoding="utf-8", newline="\n") as dest:
            self.write(dest)

    @staticmethod
    def _value(text: str) -> int | float | str:
        """Parse a value and discard an optional CCSDS unit suffix."""
        value = text.strip()
        if "[" in value:
            value = value.split("[", 1)[0].strip()
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    @staticmethod
    def _read_lines(source: TextIO) -> list[str]:
        """Return all lines from a text stream."""
        return list(source)

    @staticmethod
    def _write_value(key: str, value: Any) -> str:
        """Format a value with its OPM unit suffix when one is defined."""
        unit: str | None = _UNIT_BY_KEY.get(key)
        formatted = _format_opm_number(value)
        return f"{formatted} [{unit}]" if unit else formatted


def _read_opm(
    source: TextIO, *, validate: bool = True
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read an OPM and return ``(header, metadata, data)`` dictionaries.

    Parameters
    ----------
    source : TextIO | str | Path
        Readable text stream or path to an OPM file.
    validate : bool, optional
        Whether to validate mandatory and conditional fields.

    Returns
    -------
    tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
        Header, metadata, and data dictionaries.

    Raises
    ------
    ValueError
        If validation is enabled and required fields are missing or inconsistent.
    """
    if isinstance(source, (str, Path)):
        with Path(source).open("r", encoding="utf-8") as file_handle:
            return _read_opm(file_handle, validate=validate)

    header: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    data: dict[str, Any] = {"MANEUVERS": []}
    section: str = "header"
    current_maneuver: dict[str, Any] | None = None
    previous_header = -1
    previous_metadata = -1
    previous_data_group = -1
    previous_data_key = -1
    data_group_order = [
        set(_STATE_ORDER),
        set(_KEPLERIAN_ORDER),
        set(_SPACECRAFT_ORDER),
        {"COV_REF_FRAME", *_COVARIANCE_KEYS},
        set(_MANEUVER_KEYS),
        set(),
    ]
    maneuver_order = {key: index for index, key in enumerate(_MANEUVER_KEYS)}
    saw_metadata = False
    saw_data = False
    saw_content = False

    for line_number, raw_line in enumerate(CcsdsOpm._read_lines(source), start=1):
        line = raw_line.rstrip("\r\n")
        if len(line) > 254:
            raise ValueError(f"OPM line {line_number} exceeds 254 characters")
        try:
            line.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(f"OPM line {line_number} is not ASCII") from exc
        if line and not line.strip():
            continue
        line = line.rstrip()
        if not line:
            continue
        if not saw_content and not line.startswith("CCSDS_OPM_VERS"):
            raise ValueError("CCSDS_OPM_VERS must be the first OPM line")
        saw_content = True
        if line.startswith("COMMENT "):
            if (
                section == "metadata"
                and {
                    "OBJECT_NAME",
                    "OBJECT_ID",
                    "CENTER_NAME",
                    "REF_FRAME",
                    "TIME_SYSTEM",
                }
                <= metadata.keys()
            ):
                section = "data"
            target: dict[str, Any] = (
                header
                if section == "header"
                else metadata if section == "metadata" else data
            )
            target.setdefault("COMMENT", []).append(line[len("COMMENT ") :])
            continue
        if line.startswith("COMMENT"):
            raise ValueError(f"Invalid OPM COMMENT syntax on line {line_number}")
        parsed: tuple[str, str] | None = misc.parse_key_value_line(line)
        if parsed is None:
            raise ValueError(f"Invalid OPM KVN assignment on line {line_number}")
        key, raw_value = parsed
        if key != key.upper():
            raise ValueError(f"OPM keyword must be uppercase on line {line_number}")
        _validate_opm_value(key, raw_value.strip())
        parsed_value: int | float | str = CcsdsOpm._value(raw_value)
        if key in _HEADER_KEYS and section == "header":
            if key not in _HEADER_ORDER:
                raise ValueError(f"Unsupported OPM header keyword: {key}")
            position = _HEADER_ORDER.index(key)
            if key in header:
                raise ValueError(f"Duplicate OPM keyword {key}")
            if position <= previous_header:
                raise ValueError(f"OPM header keyword {key} is out of order")
            previous_header = position
            header[key] = parsed_value
        elif key in _METADATA_KEYS:
            if saw_data:
                raise ValueError(f"OPM metadata keyword {key} appears after data")
            if key in metadata:
                raise ValueError(f"Duplicate OPM keyword {key}")
            position = _METADATA_ORDER.index(key)
            if position <= previous_metadata:
                raise ValueError(f"OPM metadata keyword {key} is out of order")
            previous_metadata = position
            saw_metadata = True
            metadata[key] = parsed_value
            section = "metadata"
        elif (
            key
            in _STATE_ORDER
            + _KEPLERIAN_ORDER
            + _SPACECRAFT_ORDER
            + ("COV_REF_FRAME",)
            + _COVARIANCE_KEYS
            or re.fullmatch(r"USER_DEFINED_[A-Z0-9_]+", key)
            or key in _MANEUVER_KEYS
        ):
            saw_data = True
            section = "data"
            if key not in _MANEUVER_KEYS and key in data:
                raise ValueError(f"Duplicate OPM keyword {key}")
            if key in _MANEUVER_KEYS:
                group = 4
            elif key.startswith("USER_DEFINED_"):
                group = 5
            else:
                group = next(
                    index for index, keys in enumerate(data_group_order) if key in keys
                )
            if group < previous_data_group:
                raise ValueError(f"OPM keyword {key} is out of order")
            if group < 4:
                order = (
                    _STATE_ORDER
                    if group == 0
                    else (
                        _KEPLERIAN_ORDER
                        if group == 1
                        else (
                            _SPACECRAFT_ORDER
                            if group == 2
                            else ("COV_REF_FRAME", *_COVARIANCE_KEYS)
                        )
                    )
                )
                key_position = order.index(key)
                if group == previous_data_group and key_position <= previous_data_key:
                    raise ValueError(f"OPM keyword {key} is out of order")
            if group != previous_data_group:
                previous_data_key = -1
            if key in _MANEUVER_KEYS:
                if key == "MAN_EPOCH_IGNITION":
                    current_maneuver = {}
                    data["MANEUVERS"].append(current_maneuver)
                if current_maneuver is None:
                    raise ValueError(f"{key} appears before MAN_EPOCH_IGNITION")
                if key in current_maneuver:
                    raise ValueError(f"Duplicate OPM maneuver keyword {key}")
                prior = [maneuver_order[item] for item in current_maneuver]
                if prior and maneuver_order[key] <= max(prior):
                    raise ValueError(f"OPM maneuver keyword {key} is out of order")
                current_maneuver[key] = parsed_value
            else:
                if key in data:
                    raise ValueError(f"Duplicate OPM keyword {key}")
                data[key] = parsed_value
                if group < 4:
                    previous_data_key = order.index(key)
            previous_data_group = group
        else:
            raise ValueError(f"Unsupported OPM keyword {key} on line {line_number}")
    if not data["MANEUVERS"]:
        data.pop("MANEUVERS")
    if validate:
        validate_opm(header, metadata, data)
    return header, metadata, data


def _write_opm(
    dest: TextIO,
    header: dict[str, Any],
    metadata: dict[str, Any],
    data: dict[str, Any],
) -> None:
    if isinstance(dest, (str, Path)):
        with Path(dest).open("w", encoding="utf-8", newline="\n") as file_handle:
            _write_opm(file_handle, header, metadata, data)
        return

    """Write parsed OPM header, metadata, and data dictionaries.

    Parameters
    ----------
    dest : TextIO | str | Path
        Writable text stream or destination file path.
    header : dict[str, Any]
        File-level OPM keywords.
    metadata : dict[str, Any]
        Object and reference-frame metadata.
    data : dict[str, Any]
        State, optional element, covariance, and maneuver values.
    """
    validate_opm(header, metadata, data)
    for name, values in (("header", header), ("metadata", metadata), ("data", data)):
        for comment in values.get("COMMENT", []):
            if not isinstance(comment, str) or not comment.isascii():
                raise ValueError(f"OPM {name} comments must contain ASCII text")
            if "\n" in comment or "\r" in comment:
                raise ValueError(f"OPM {name} comments must be single-line")
    output = io.StringIO()
    for key in (
        "CCSDS_OPM_VERS",
        "CLASSIFICATION",
        "CREATION_DATE",
        "ORIGINATOR",
        "MESSAGE_ID",
    ):
        if key in header:
            output.write(f"{key} = {header[key]}\n")
        if key == "CCSDS_OPM_VERS":
            for comment in header.get("COMMENT", []):
                output.write(f"COMMENT {comment}\n")
    output.write("\n")
    for comment in metadata.get("COMMENT", []):
        output.write(f"COMMENT {comment}\n")
    for key in (
        "OBJECT_NAME",
        "OBJECT_ID",
        "CENTER_NAME",
        "REF_FRAME",
        "REF_FRAME_EPOCH",
        "TIME_SYSTEM",
    ):
        if key in metadata:
            output.write(f"{key} = {metadata[key]}\n")
    output.write("\n")
    for comment in data.get("COMMENT", []):
        output.write(f"COMMENT {comment}\n")
    data_order: tuple[str, ...] = (
        "EPOCH",
        "X",
        "Y",
        "Z",
        "X_DOT",
        "Y_DOT",
        "Z_DOT",
        "SEMI_MAJOR_AXIS",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "TRUE_ANOMALY",
        "MEAN_ANOMALY",
        "GM",
        "MASS",
        "SOLAR_RAD_AREA",
        "SOLAR_RAD_COEFF",
        "DRAG_AREA",
        "DRAG_COEFF",
        "COV_REF_FRAME",
    )
    for key in data_order + _COVARIANCE_KEYS:
        if key in data:
            output.write(f"{key} = {CcsdsOpm._write_value(key, data[key])}\n")
    for maneuver in data.get("MANEUVERS", []):
        for key in _MANEUVER_KEYS:
            if key in maneuver:
                output.write(f"{key} = {CcsdsOpm._write_value(key, maneuver[key])}\n")
    for key, value in data.items():
        if key.startswith("USER_DEFINED_"):
            output.write(f"{key} = {value}\n")
    for line_number, line in enumerate(output.getvalue().splitlines(), start=1):
        if len(line) > 254:
            raise ValueError(f"OPM output line {line_number} exceeds 254 characters")
        if not line.isascii():
            raise ValueError(f"OPM output line {line_number} is not ASCII")
    dest.write(output.getvalue())
