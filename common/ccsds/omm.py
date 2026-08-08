"""Read, parse, and write CCSDS Orbit Mean-Elements Message (OMM) files.

Provides low-level functions (:func:`read_omm`, :func:`write_omm`) that
operate on plain dictionaries, and a structured :class:`CcsdsOmm` class.

References:
    CCSDS 502.0-B-3 "Orbit Mean-Elements Message (OMM)" standard (2023-04).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, TextIO
from datetime import datetime, timezone

import numpy as np

import common.common as common
import common.consts as consts
import common.time_utils as time_utils
import common.kepler as kepler

# ===================================================================
# Internal helpers
# ===================================================================


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


_META_KEY_ORDER: list[str] = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "TIME_SYSTEM",
    "MEAN_ELEMENT_THEORY",
]
"""Canonical key ordering for the OMM metadata section."""

_MEAN_ELEMENTS_KEY_ORDER: list[str] = [
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
]
"""Canonical key ordering for the mean elements section."""

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
"""Canonical key ordering for the TLE-related parameters section."""


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

        kv: tuple[str, str] | None = common.parse_key_value_line(line)
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
    version: float | int = header.get("CCSDS_OMM_VERS", 3.0)
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
    element_set_no: int = 999
    """Element set number for this satellite"""
    rev_at_epoch: int = 0
    """Revolution number at epoch"""
    bstar: str = "0"
    """BSTAR drag term (for SGP4) or BTERM ballistic coefficient (for SGP4-XP)"""
    mean_motion_dot: str = "0"
    """First time derivative of mean motion (for SGP or PPT3)"""
    mean_motion_ddot: str = "0"
    """Second time derivative of mean motion (for SGP or PPT3) or AGOM (for SGP4-XP)"""


@dataclass
class CcsdsOmm:
    """Parsed CCSDS Orbit Mean-Elements Message.

    All angular quantities are stored in degrees and mean motion in
    revolutions per day, matching the native OMM/TLE representation.
    """

    version: float = 3.0
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

        # Check if TLE-related parameters are present
        tle_params: TleParameters | None = None
        if any(key in data for key in _TLE_PARAMS_KEY_ORDER):
            tle_params = TleParameters(
                ephemeris_type=int(data.get("EPHEMERIS_TYPE", 0)),
                classification_type=str(data.get("CLASSIFICATION_TYPE", "U")),
                norad_cat_id=int(data.get("NORAD_CAT_ID", 0)),
                element_set_no=int(data.get("ELEMENT_SET_NO", 999)),
                rev_at_epoch=int(data.get("REV_AT_EPOCH", 0)),
                bstar=str(data.get("BSTAR", "0")),
                mean_motion_dot=str(data.get("MEAN_MOTION_DOT", "0")),
                mean_motion_ddot=str(data.get("MEAN_MOTION_DDOT", "0")),
            )

        return cls(
            version=float(header.get("CCSDS_OMM_VERS", 3.0)),
            creation_date=str(header.get("CREATION_DATE", "")),
            originator=str(header.get("ORIGINATOR", "")),
            comments=header.get("COMMENT", []),
            object_name=str(data.get("OBJECT_NAME", "")),
            object_id=str(data.get("OBJECT_ID", "")),
            center_name=str(data.get("CENTER_NAME", "EARTH")),
            ref_frame=str(data.get("REF_FRAME", "ICRF")),
            time_system=str(data.get("TIME_SYSTEM", "UTC")),
            mean_element_theory=str(data.get("MEAN_ELEMENT_THEORY", "DSST")),
            epoch=str(data.get("EPOCH", "")),
            mean_motion=float(data.get("MEAN_MOTION", 0.0)),
            eccentricity=float(data.get("ECCENTRICITY", 0.0)),
            inclination=float(data.get("INCLINATION", 0.0)),
            ra_of_asc_node=float(data.get("RA_OF_ASC_NODE", 0.0)),
            arg_of_pericenter=float(data.get("ARG_OF_PERICENTER", 0.0)),
            mean_anomaly=float(data.get("MEAN_ANOMALY", 0.0)),
            tle_parameters=tle_params,
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
        }

        # Add TLE-related parameters if present
        if self.tle_parameters is not None:
            data["EPHEMERIS_TYPE"] = self.tle_parameters.ephemeris_type
            data["CLASSIFICATION_TYPE"] = self.tle_parameters.classification_type
            data["NORAD_CAT_ID"] = self.tle_parameters.norad_cat_id
            data["ELEMENT_SET_NO"] = self.tle_parameters.element_set_no
            data["REV_AT_EPOCH"] = self.tle_parameters.rev_at_epoch
            data["BSTAR"] = self.tle_parameters.bstar
            data["MEAN_MOTION_DOT"] = self.tle_parameters.mean_motion_dot
            data["MEAN_MOTION_DDOT"] = self.tle_parameters.mean_motion_ddot

        write_omm(dest, hdr, data)

    def __repr__(self) -> str:
        """Return a concise string representation of this OMM instance."""
        norad_id = self.tle_parameters.norad_cat_id if self.tle_parameters else "N/A"
        return (
            f"CcsdsOmm(object={self.object_name!r}, "
            f"norad_cat_id={norad_id}, "
            f"epoch={self.epoch!r})"
        )


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
    omm.CcsdsOmm
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
    mean_motion_rev_day: float = kepler.semi_major_axis_to_mean_motion(a_m, mu_m3_s2)

    # Format epoch as ISO 8601 (per CCSDS 502.0-B-3 section 7.5.10)
    epoch_str: str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)

    # Create OMM object compliant with CCSDS 502.0-B-3
    # Note: TLE-related parameters are NOT included (set to None) as this is not a TLE-based OMM
    omm_obj: CcsdsOmm = CcsdsOmm(
        version=3.0,  # CCSDS 502.0-B-3 (2023-04)
        creation_date=time_utils.datetime_to_iso8601(
            datetime.now(timezone.utc), fractional_second_places=3
        ),
        originator="tudatpy-utils",
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
        mean_motion=mean_motion_rev_day,
        eccentricity=e,
        inclination=np.degrees(i_rad),
        ra_of_asc_node=np.degrees(raan_rad),
        arg_of_pericenter=np.degrees(omega_rad),
        mean_anomaly=np.degrees(mean_anomaly_rad),
        tle_parameters=None,  # No TLE parameters for non-TLE OMMs
    )

    return omm_obj
