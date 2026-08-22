"""Read, parse, and write CCSDS Orbit Parameter Message (OPM) files.

References:
    https://public.ccsds.org/Pubs/502x0b3e1.pdf
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from .. import misc

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
"""OPM units keyed by field name."""

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
_KEPLERIAN_KEYS: set[str] = {
    "SEMI_MAJOR_AXIS",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "GM",
}
_UNIT_BY_KEY.update(
    {key: "km**2" for key in ("CX_X", "CY_X", "CY_Y", "CZ_X", "CZ_Y", "CZ_Z")}
)
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


def _read_lines(source: TextIO | str | Path) -> list[str]:
    if isinstance(source, (str, Path)):
        return Path(source).read_text(encoding="utf-8").splitlines()
    return list(source)


def validate_opm(
    header: dict[str, Any], metadata: dict[str, Any], data: dict[str, Any]
) -> None:
    """Validate mandatory and conditional CCSDS OPM fields.

    Raises
    ------
    ValueError
        If a required field or a conditional block is incomplete.
    """
    required_header = {"CCSDS_OPM_VERS", "CREATION_DATE", "ORIGINATOR"}
    required_metadata = {
        "OBJECT_NAME",
        "OBJECT_ID",
        "CENTER_NAME",
        "REF_FRAME",
        "TIME_SYSTEM",
    }
    required_state = {"EPOCH", "X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT"}
    for name, required, values in (
        ("header", required_header, header),
        ("metadata", required_metadata, metadata),
        ("state vector", required_state, data),
    ):
        missing = sorted(required - values.keys())
        if missing:
            raise ValueError(
                f"Missing required OPM {name} field(s): {', '.join(missing)}"
            )

    keplerian_present = _KEPLERIAN_KEYS & data.keys()
    anomaly_present = {"TRUE_ANOMALY", "MEAN_ANOMALY"} & data.keys()
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

    covariance_present = _COVARIANCE_KEYS & data.keys()
    if covariance_present and covariance_present != set(_COVARIANCE_KEYS):
        missing = sorted(set(_COVARIANCE_KEYS) - covariance_present)
        raise ValueError("Incomplete OPM covariance matrix: " + ", ".join(missing))

    maneuvers = data.get("MANEUVERS", [])
    if maneuvers and "MASS" not in data:
        raise ValueError("OPM MASS is required when maneuvers are present")
    for index, maneuver in enumerate(maneuvers, start=1):
        delta_mass = maneuver.get("MAN_DELTA_MASS")
        if delta_mass is not None and float(delta_mass) >= 0:
            raise ValueError(f"OPM maneuver {index} MAN_DELTA_MASS must be negative")


def read_opm(
    source: TextIO | str | Path, *, validate: bool = True
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read an OPM and return ``(header, metadata, data)`` dictionaries."""
    header: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    data: dict[str, Any] = {"MANEUVERS": []}
    section = "header"
    current_maneuver: dict[str, Any] | None = None

    for raw_line in _read_lines(source):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("COMMENT"):
            target = (
                header
                if section == "header"
                else metadata if section == "metadata" else data
            )
            target.setdefault("COMMENT", []).append(line[len("COMMENT") :].strip())
            continue
        parsed = misc.parse_key_value_line(line)
        if parsed is None:
            continue
        key, raw_value = parsed
        parsed_value = _value(raw_value)
        if key in _HEADER_KEYS and section == "header":
            header[key] = parsed_value
        elif key in _METADATA_KEYS:
            metadata[key] = parsed_value
            section = "metadata"
        elif key == "MAN_EPOCH_IGNITION":
            current_maneuver = {key: parsed_value}
            data["MANEUVERS"].append(current_maneuver)
            section = "data"
        elif current_maneuver is not None and key in _MANEUVER_KEYS:
            current_maneuver[key] = parsed_value
        else:
            data[key] = parsed_value
            section = "data"
    if not data["MANEUVERS"]:
        data.pop("MANEUVERS")
    if validate:
        validate_opm(header, metadata, data)
    return header, metadata, data


def _write_value(key: str, value: Any) -> str:
    unit = _UNIT_BY_KEY.get(key)
    return f"{value} [{unit}]" if unit else str(value)


def write_opm(
    dest: TextIO | str | Path,
    header: dict[str, Any],
    metadata: dict[str, Any],
    data: dict[str, Any],
) -> None:
    """Write dictionaries returned by :func:`read_opm` as an OPM file."""
    if isinstance(dest, (str, Path)):
        with open(dest, "w", encoding="utf-8") as stream:
            return write_opm(stream, header, metadata, data)
    for key in (
        "CCSDS_OPM_VERS",
        "CLASSIFICATION",
        "CREATION_DATE",
        "ORIGINATOR",
        "MESSAGE_ID",
    ):
        if key in header:
            dest.write(f"{key} = {header[key]}\n")
        if key == "CCSDS_OPM_VERS":
            for comment in header.get("COMMENT", []):
                dest.write(f"COMMENT {comment}\n")
    dest.write("\n")
    for key in (
        "OBJECT_NAME",
        "OBJECT_ID",
        "CENTER_NAME",
        "REF_FRAME",
        "REF_FRAME_EPOCH",
        "TIME_SYSTEM",
    ):
        if key in metadata:
            dest.write(f"{key} = {metadata[key]}\n")
    for comment in metadata.get("COMMENT", []):
        dest.write(f"COMMENT {comment}\n")
    dest.write("\n")
    data_order = (
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
            dest.write(f"{key} = {_write_value(key, data[key])}\n")
    for key, value in data.items():
        if key.startswith("USER_DEFINED_"):
            dest.write(f"{key} = {value}\n")
    for maneuver in data.get("MANEUVERS", []):
        for key in _MANEUVER_KEYS:
            if key in maneuver:
                dest.write(f"{key} = {_write_value(key, maneuver[key])}\n")
    for comment in data.get("COMMENT", []):
        dest.write(f"COMMENT {comment}\n")


@dataclass
class OpmHeader:
    """CCSDS OPM header fields."""

    version: float = 3.0
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
    def from_source(cls, source: TextIO | str | Path) -> "CcsdsOpm":
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
        header, metadata, data = read_opm(source)
        state = OpmStateVector(
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
        header_obj = OpmHeader(
            float(header.get("CCSDS_OPM_VERS", 3.0)),
            list(header.get("COMMENT", [])),
            str(header.get("CLASSIFICATION", "")),
            str(header.get("CREATION_DATE", "")),
            str(header.get("ORIGINATOR", "")),
            str(header.get("MESSAGE_ID", "")),
        )
        keplerian = None
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
        spacecraft_keys = {
            "MASS",
            "SOLAR_RAD_AREA",
            "SOLAR_RAD_COEFF",
            "DRAG_AREA",
            "DRAG_COEFF",
        }
        spacecraft = None
        if spacecraft_keys & data.keys():
            spacecraft = OpmSpacecraftParameters(
                **{
                    key.lower(): float(data[key]) if key in data else None
                    for key in spacecraft_keys
                }
            )
        covariance = None
        if set(_COVARIANCE_KEYS) <= data.keys():
            matrix = np.zeros((6, 6))
            for key, (row, column) in zip(_COVARIANCE_KEYS, _COVARIANCE_POSITIONS):
                matrix[row, column] = float(data[key])
                matrix[column, row] = matrix[row, column]
            covariance = OpmCovariance(matrix, data.get("COV_REF_FRAME"))
        maneuvers = [
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

    def to_file(self, dest: TextIO | str | Path) -> None:
        """Write this structured OPM message to a file or text stream.

        Parameters
        ----------
        dest : TextIO or str or Path
            Destination stream or path for the OPM file.
        """
        header = {
            "CCSDS_OPM_VERS": self.header.version,
            "COMMENT": self.header.comments,
            "CLASSIFICATION": self.header.classification,
            "CREATION_DATE": self.header.creation_date,
            "ORIGINATOR": self.header.originator,
            "MESSAGE_ID": self.header.message_id,
        }
        data = dict(self.data)
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
        write_opm(dest, header, self.metadata, data)
