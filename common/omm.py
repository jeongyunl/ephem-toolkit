"""Read, parse, and write CCSDS Orbit Mean-Elements Message (OMM) files.

Provides low-level functions (:func:`read_omm`, :func:`write_omm`) that
operate on plain dictionaries, and a structured :class:`CcsdsOmm` class.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, TextIO

# ===================================================================
# Internal helpers
# ===================================================================


def _parse_kv_line(line: str) -> tuple[str, str] | None:
    """Return (key, value) from ``KEY = VALUE`` lines, or *None*."""
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    return key.strip(), value.strip()


def _try_numeric(value: str) -> int | float | str:
    """Attempt to convert *value* to int or float; return str on failure."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# Canonical key ordering for the OMM metadata section
_META_KEY_ORDER: list[str] = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "TIME_SYSTEM",
    "MEAN_ELEMENT_THEORY",
]

# Canonical key ordering for the mean elements section
_MEAN_ELEMENTS_KEY_ORDER: list[str] = [
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
]

# Canonical key ordering for the TLE-related parameters section
_TLE_PARAMS_KEY_ORDER: list[str] = [
    "EPHEMERIS_TYPE",
    "CLASSIFICATION_TYPE",
    "NORAD_CAT_ID",
    "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
    "BSTAR",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
]


# ===================================================================
# Low-level reader (dict-based)
# ===================================================================


def read_omm(
    source: TextIO | str | Path,
) -> tuple[dict, dict]:
    """Read an OMM file and return *(header, data)*.

    Parameters
    ----------
    source : TextIO | str | Path
        A readable text stream, file path string, or :class:`Path`.

    Returns
    -------
    tuple[dict, dict]
        A 2-tuple of ``(header, data)`` where *header* contains file-level
        keywords (``CCSDS_OMM_VERS``, ``CREATION_DATE``, ``ORIGINATOR``,
        and any ``COMMENT`` lines), and *data* contains all remaining
        keyword-value pairs (metadata, mean elements, and TLE parameters).
    """
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return read_omm(fh)

    header: dict = {}
    data: dict = {}

    _HEADER_KEYS: set[str] = {"CCSDS_OMM_VERS", "CREATION_DATE", "ORIGINATOR"}

    for raw_line in source:
        line: str = raw_line.strip()
        if not line:
            continue

        # Handle COMMENT lines
        if line.startswith("COMMENT"):
            comment_text: str = line[len("COMMENT") :].strip()
            header.setdefault("COMMENT", [])
            header["COMMENT"].append(comment_text)
            continue

        kv: tuple[str, str] | None = _parse_kv_line(line)
        if kv is None:
            continue

        key, value = kv

        if key in _HEADER_KEYS:
            header[key] = _try_numeric(value) if value else value
        else:
            data[key] = _try_numeric(value) if value else value

    return header, data


# ===================================================================
# Low-level writer (dict-based)
# ===================================================================


def write_omm(
    dest: TextIO | str | Path,
    header: dict,
    data: dict,
) -> None:
    """Write an OMM file from *(header, data)* dicts.

    Parameters
    ----------
    dest : TextIO | str | Path
        A writable text stream, file path string, or :class:`Path`.
    header : dict
        File-level keywords (``CCSDS_OMM_VERS``, ``CREATION_DATE``,
        ``ORIGINATOR``, and optionally ``COMMENT``).
    data : dict
        All remaining keyword-value pairs (metadata, mean elements,
        and TLE parameters).
    """
    if isinstance(dest, (str, Path)):
        with open(dest, "w", encoding="utf-8") as fh:
            return write_omm(fh, header, data)

    w: Callable[[str], int] = dest.write

    # --- Header ---
    version: float | int = header.get("CCSDS_OMM_VERS", 2.0)
    w(f"CCSDS_OMM_VERS = {version}\n")

    creation_date: str | int | float = header.get("CREATION_DATE", "")
    w(f"CREATION_DATE  = {creation_date}\n")

    originator: str | int | float = header.get("ORIGINATOR", "")
    w(f"ORIGINATOR     = {originator}\n")

    for comment in header.get("COMMENT", []):
        w(f"COMMENT {comment}\n")

    w("\n")

    # --- Metadata section ---
    for key in _META_KEY_ORDER:
        if key in data:
            w(f"{key:<{max(14, len(key))}} = {data[key]}\n")

    w("\n")

    # --- Mean elements section ---
    for key in _MEAN_ELEMENTS_KEY_ORDER:
        if key in data:
            w(f"{key:<{max(14, len(key))}} = {data[key]}\n")

    w("\n")

    # --- TLE-related parameters section ---
    for key in _TLE_PARAMS_KEY_ORDER:
        if key in data:
            w(f"{key:<{max(14, len(key))}} = {data[key]}\n")

    # --- Any extra keys not in the canonical ordering ---
    all_ordered: set[str] = set(
        _META_KEY_ORDER + _MEAN_ELEMENTS_KEY_ORDER + _TLE_PARAMS_KEY_ORDER
    )
    extra_keys: list[str] = [k for k in data if k not in all_ordered and k != "COMMENT"]
    for key in extra_keys:
        w(f"{key:<{max(14, len(key))}} = {data[key]}\n")

    w("\n")


# ===================================================================
# Structured dataclass
# ===================================================================


@dataclass
class CcsdsOmm:
    """Parsed CCSDS Orbit Mean-Elements Message.

    All angular quantities are stored in degrees and mean motion in
    revolutions per day, matching the native OMM/TLE representation.
    """

    version: float = 2.0
    """CCSDS OMM format version number"""
    creation_date: str = ""
    """File creation date (ISO 8601 format)"""
    originator: str = ""
    """Organization or entity that created the OMM file"""
    comments: list[str] = field(default_factory=list)
    """List of comment lines from the OMM header"""

    object_name: str = ""
    """Satellite or object name"""
    object_id: str = ""
    """International designator or NORAD catalog number"""
    center_name: str = "EARTH"
    """Central body name (e.g., EARTH, MOON)"""
    ref_frame: str = "TEME"
    """Reference frame (e.g., TEME, J2000, ITRF)"""
    time_system: str = "UTC"
    """Time system (e.g., UTC, GPS, TAI)"""
    mean_element_theory: str = "SGP/SGP4"
    """Mean element theory used (e.g., SGP/SGP4, SGP8)"""

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

    ephemeris_type: int = 0
    """Ephemeris type (0=SGP, 2=SGP4, 4=SGP8, 6=SP)"""
    classification_type: str = "U"
    """Classification (U=Unclassified, C=Classified, S=Secret)"""
    norad_cat_id: int = 0
    """NORAD catalog ID number"""
    element_set_no: int = 999
    """Element set number"""
    rev_at_epoch: int = 0
    """Revolution number at epoch"""
    bstar: str = "0"
    """BSTAR drag term"""
    mean_motion_dot: str = "0"
    """First time derivative of mean motion"""
    mean_motion_ddot: str = "0"
    """Second time derivative of mean motion"""

    def to_dict(self) -> dict[str, object]:
        """Convert to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_source(cls, source: TextIO | str | Path) -> CcsdsOmm:
        """Construct a :class:`CcsdsOmm` from a file or stream.

        Parameters
        ----------
        source : TextIO | str | Path
            A readable text stream, file path string, or :class:`Path`.

        Returns
        -------
        CcsdsOmm
            Parsed OMM instance.
        """
        header: dict
        data: dict
        header, data = read_omm(source)

        return cls(
            version=float(header.get("CCSDS_OMM_VERS", 2.0)),
            creation_date=str(header.get("CREATION_DATE", "")),
            originator=str(header.get("ORIGINATOR", "")),
            comments=header.get("COMMENT", []),
            object_name=str(data.get("OBJECT_NAME", "")),
            object_id=str(data.get("OBJECT_ID", "")),
            center_name=str(data.get("CENTER_NAME", "EARTH")),
            ref_frame=str(data.get("REF_FRAME", "TEME")),
            time_system=str(data.get("TIME_SYSTEM", "UTC")),
            mean_element_theory=str(data.get("MEAN_ELEMENT_THEORY", "SGP/SGP4")),
            epoch=str(data.get("EPOCH", "")),
            mean_motion=float(data.get("MEAN_MOTION", 0.0)),
            eccentricity=float(data.get("ECCENTRICITY", 0.0)),
            inclination=float(data.get("INCLINATION", 0.0)),
            ra_of_asc_node=float(data.get("RA_OF_ASC_NODE", 0.0)),
            arg_of_pericenter=float(data.get("ARG_OF_PERICENTER", 0.0)),
            mean_anomaly=float(data.get("MEAN_ANOMALY", 0.0)),
            ephemeris_type=int(data.get("EPHEMERIS_TYPE", 0)),
            classification_type=str(data.get("CLASSIFICATION_TYPE", "U")),
            norad_cat_id=int(data.get("NORAD_CAT_ID", 0)),
            element_set_no=int(data.get("ELEMENT_SET_NO", 999)),
            rev_at_epoch=int(data.get("REV_AT_EPOCH", 0)),
            bstar=str(data.get("BSTAR", "0")),
            mean_motion_dot=str(data.get("MEAN_MOTION_DOT", "0")),
            mean_motion_ddot=str(data.get("MEAN_MOTION_DDOT", "0")),
        )

    def to_file(self, dest: TextIO | str | Path) -> None:
        """Write this OMM to a file or stream.

        Parameters
        ----------
        dest : TextIO | str | Path
            A writable text stream, file path string, or :class:`Path`.
        """
        hdr: dict = {
            "CCSDS_OMM_VERS": self.version,
            "CREATION_DATE": self.creation_date,
            "ORIGINATOR": self.originator,
        }
        if self.comments:
            hdr["COMMENT"] = self.comments

        data: dict = {
            "OBJECT_NAME": self.object_name,
            "OBJECT_ID": self.object_id,
            "CENTER_NAME": self.center_name,
            "REF_FRAME": self.ref_frame,
            "TIME_SYSTEM": self.time_system,
            "MEAN_ELEMENT_THEORY": self.mean_element_theory,
            "EPOCH": self.epoch,
            "MEAN_MOTION": self.mean_motion,
            "ECCENTRICITY": self.eccentricity,
            "INCLINATION": self.inclination,
            "RA_OF_ASC_NODE": self.ra_of_asc_node,
            "ARG_OF_PERICENTER": self.arg_of_pericenter,
            "MEAN_ANOMALY": self.mean_anomaly,
            "EPHEMERIS_TYPE": self.ephemeris_type,
            "CLASSIFICATION_TYPE": self.classification_type,
            "NORAD_CAT_ID": self.norad_cat_id,
            "ELEMENT_SET_NO": self.element_set_no,
            "REV_AT_EPOCH": self.rev_at_epoch,
            "BSTAR": self.bstar,
            "MEAN_MOTION_DOT": self.mean_motion_dot,
            "MEAN_MOTION_DDOT": self.mean_motion_ddot,
        }

        write_omm(dest, hdr, data)

    def __repr__(self) -> str:
        """Return a concise string representation of this OMM instance."""
        return (
            f"CcsdsOmm(object={self.object_name!r}, "
            f"norad_cat_id={self.norad_cat_id}, "
            f"epoch={self.epoch!r})"
        )
