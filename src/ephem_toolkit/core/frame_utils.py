"""Convert Cartesian states between inertial and Earth-fixed frames."""

from __future__ import annotations

import numpy as np

from enum import Enum

import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

try:
    from tudatpy.astro import element_conversion
    from tudatpy.dynamics import environment_setup
    from tudatpy.dynamics.environment_setup.rotation_model import RotationModelSettings
    from tudatpy.interface import spice
except ImportError as exc:
    raise ImportError("frame_utils requires tudatpy") from exc

from . import spice_utils

_has_compute_state_rotation_matrix_between_frames: bool = hasattr(
    spice, "compute_state_rotation_matrix_between_frames"
)
"""Whether the installed TudatPy version provides the combined state transform."""

_tudat_spice_rotation_model: object | None = None
"""Cached TudatPy rotation model using SPICE Earth orientation data."""

_tudat_iau2006_rotation_model: object | None = None
"""Cached TudatPy rotation model using the IAU 2006 Earth orientation model."""


def _load_spice_kernels() -> None:
    """Load the SPICE kernels required by the frame conversions."""

    spice_kernel_files = [
        "naif0012.tls",
        "pck00011.tpc",
        "gm_de431.tpc",
        "earth_200101_990825_predict.bpc",
        "tudat_merged_spk_kernel.bsp",
    ]
    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


_load_spice_kernels()


class Frame(Enum):
    """Enumeration of supported reference frames."""

    TEME = "TEME"
    """True Equator Mean Equinox frame."""

    J2000 = "J2000"
    """J2000 Reference frame."""

    EME2000 = "EME2000"
    """J2000 Reference frame."""

    ICRF = "ICRF"
    """International Celestial Reference Frame."""

    GCRF = "GCRF"
    """Geocentric Celestial Reference Frame."""

    ITRF1993 = "ITRF1993"
    """International Terrestrial Reference Frame 1993."""

    ITRF = "ITRF"
    """International Terrestrial Reference Frame."""


def teme_to_j2000(epoch_tt_s: float, teme_state: np.ndarray) -> np.ndarray:
    """Convert a TEME Cartesian state to the J2000 frame.

    Parameters
    ----------
    epoch_tt_s : float
        TT seconds since the J2000 epoch, used to evaluate the rotation.
    teme_state : np.ndarray
        Six-component TEME state vector. The first three components are
        position and the last three are velocity.

    Returns
    -------
    np.ndarray
        Six-component vector in J2000 coordinates.

    Notes
    -----
    Position and velocity are each multiplied by the epoch-dependent TEME
    rotation. This helper does not include the rotation-matrix derivative
    term required for a full time-dependent frame state transformation.
    """
    j2000_state: np.ndarray = np.zeros(6, dtype=float)
    rotation_to_j2000: np.ndarray = element_conversion.teme_to_j2000(epoch_tt_s)
    j2000_state[0:3] = teme_state[0:3] @ rotation_to_j2000
    j2000_state[3:6] = teme_state[3:6] @ rotation_to_j2000
    return j2000_state


def j2000_to_teme(epoch_tt_s: float, j2000_state: np.ndarray) -> np.ndarray:
    """Convert a J2000 Cartesian state to the TEME frame.

    Parameters
    ----------
    epoch_tt_s : float
        TT seconds since the J2000 epoch, used to evaluate the rotation.
    j2000_state : np.ndarray
        Six-component J2000 state vector. The first three components are
        position and the last three are velocity.

    Returns
    -------
    np.ndarray
        Six-component vector in TEME coordinates.

    Notes
    -----
    Position and velocity are each multiplied by the transpose of the
    epoch-dependent TEME-to-J2000 rotation. This helper does not include the
    rotation-matrix derivative term required for a full time-dependent frame
    state transformation.
    """
    teme_state: np.ndarray = np.zeros(6, dtype=float)
    rotation_to_teme: np.ndarray = np.transpose(
        element_conversion.teme_to_j2000(epoch_tt_s)
    )
    teme_state[0:3] = j2000_state[0:3] @ rotation_to_teme
    teme_state[3:6] = j2000_state[3:6] @ rotation_to_teme
    return teme_state


def spice_convert_frame(
    base_frame: str,
    target_frame: str,
    epoch_tt_s: float,
    input_state_m: np.ndarray,
) -> np.ndarray:
    """Convert a state vector from one SPICE frame to another.

    Uses SPICE rotation matrices and their time derivatives to build a
    6-by-6 state conversion matrix that correctly transforms both position
    and velocity, accounting for the rotating-frame transport term.

    Parameters
    ----------
    base_frame : str
        Name of the source SPICE frame (e.g. ``"J2000"``).
    target_frame : str
        Name of the destination SPICE frame (e.g. ``"ITRF93"``).
    epoch_tt_s : float
        Epoch in ephemeris time (TT seconds since J2000).
    input_state_m : np.ndarray
        State vector ``[x, y, z, vx, vy, vz]`` (6,) in metres and m/s in
        *base_frame*.

    Returns
    -------
    np.ndarray
        6-element state vector ``[x, y, z, vx, vy, vz]`` in metres and m/s
        in *target_frame*.
    """

    if base_frame == "ITRF" or base_frame == "ITRF1993":
        base_frame = "ITRF93"

    if target_frame == "ITRF" or target_frame == "ITRF1993":
        target_frame = "ITRF93"

    if _has_compute_state_rotation_matrix_between_frames:
        state_conversion_matrix: np.ndarray = np.asarray(
            spice.compute_state_rotation_matrix_between_frames(
                base_frame, target_frame, epoch_tt_s
            )
        )
    else:
        rotation_matrix: np.ndarray = spice.compute_rotation_matrix_between_frames(
            base_frame, target_frame, epoch_tt_s
        )
        rotation_matrix_derivative: np.ndarray = (
            spice.compute_rotation_matrix_derivative_between_frames(
                base_frame, target_frame, epoch_tt_s
            )
        )

        state_conversion_matrix = np.zeros((6, 6))
        state_conversion_matrix[0:3, 0:3] = rotation_matrix
        state_conversion_matrix[3:6, 0:3] = rotation_matrix_derivative
        state_conversion_matrix[3:6, 3:6] = rotation_matrix

    return state_conversion_matrix @ np.asarray(input_state_m)


def _tudat_create_rotation_model(
    body_name: str,
    global_frame_orientation: str,
    rotation_model_settings: RotationModelSettings,
) -> object:
    """Create a TudatPy rotation model for a body.

    Parameters
    ----------
    body_name : str
        Name of the body for which to create the rotation model.
    global_frame_orientation : str
        Inertial frame orientation used for the body's default settings.
    rotation_model_settings : RotationModelSettings
        TudatPy settings describing the rotation model.

    Returns
    -------
    object
        TudatPy rotation model configured for the requested body.

    Notes
    -----
    The model can be used to convert between inertial and body-fixed
    coordinate systems.
    """

    global_frame_origin: str = body_name
    bodies_to_create: list[str] = [body_name]

    body_settings: dict = environment_setup.get_default_body_settings(
        bodies_to_create, global_frame_origin, global_frame_orientation
    )

    bodies: object = environment_setup.create_system_of_bodies(body_settings)

    environment_setup.add_rotation_model(
        bodies,
        body_name,
        rotation_model_settings,
    )

    return bodies.get(body_name).rotation_model


def tudat_spice_rotation_model() -> object:
    """Return the cached TudatPy SPICE rotation model for Earth. J2000 <-> ITRF93."""

    global _tudat_spice_rotation_model

    if _tudat_spice_rotation_model is not None:
        return _tudat_spice_rotation_model

    original_frame: str = "J2000"
    target_frame: str = "ITRF93"

    rotation_model_settings: RotationModelSettings = (
        environment_setup.rotation_model.spice(
            original_frame,
            target_frame,
        )
    )
    global_frame_orientation: str = original_frame

    _tudat_spice_rotation_model = _tudat_create_rotation_model(
        "Earth",
        global_frame_orientation,
        rotation_model_settings,
    )

    return _tudat_spice_rotation_model


def tudat_iau2006_rotation_model() -> object:
    """Return the cached TudatPy IAU 2006 rotation model for Earth. J2000 <-> ITRF."""

    global _tudat_iau2006_rotation_model

    if _tudat_iau2006_rotation_model is not None:
        return _tudat_iau2006_rotation_model

    global_frame_orientation: str = "GCRS"

    rotation_model_settings: RotationModelSettings = (
        environment_setup.rotation_model.gcrs_to_itrs(
            environment_setup.rotation_model.IAUConventions.iau_2006,
            global_frame_orientation,
        )
    )

    _tudat_iau2006_rotation_model = _tudat_create_rotation_model(
        "Earth",
        global_frame_orientation,
        rotation_model_settings,
    )

    return _tudat_iau2006_rotation_model


def tudat_convert_inertial_to_body_fixed(
    rotation_model: object,
    input_epoch_et_s: float,
    input_inertial_state_m: np.ndarray,
) -> np.ndarray:
    """Convert an inertial state to a body-fixed state.

    Parameters
    ----------
    rotation_model : object
        Rotation model providing inertial-to-body-fixed rotation and angular
        velocity methods.
    input_epoch_et_s : float
        Epoch in ephemeris time, in seconds.
    input_inertial_state_m : np.ndarray
        Six-component inertial state vector with position in metres and
        velocity in metres per second.

    Returns
    -------
    np.ndarray
        Six-component body-fixed state vector with position in metres and
        velocity in metres per second.
    """

    inertial_to_body_fixed_rotation_matrix: np.ndarray = (
        rotation_model.inertial_to_body_fixed_rotation(input_epoch_et_s)
    )
    body_fixed_rotational_velocity_rad_s: np.ndarray = (
        rotation_model.angular_velocity_in_body_fixed_frame(input_epoch_et_s)
    )

    input_inertial_position_m: np.ndarray = input_inertial_state_m[0:3]
    input_inertial_velocity_m_s: np.ndarray = input_inertial_state_m[3:6]
    output_body_fixed_position_m: np.ndarray = (
        inertial_to_body_fixed_rotation_matrix @ input_inertial_position_m
    )
    output_body_fixed_velocity_m_s: np.ndarray = (
        inertial_to_body_fixed_rotation_matrix @ input_inertial_velocity_m_s
        - np.cross(body_fixed_rotational_velocity_rad_s, output_body_fixed_position_m)
    )

    return np.concatenate(
        [output_body_fixed_position_m, output_body_fixed_velocity_m_s]
    )


def tudat_convert_body_fixed_to_inertial(
    rotation_model: object,
    input_epoch_et_s: float,
    input_body_fixed_state_m: np.ndarray,
) -> np.ndarray:
    """Convert a body-fixed state to an inertial state.

    Parameters
    ----------
    rotation_model : object
        Rotation model providing body-fixed-to-inertial rotation and angular
        velocity methods.
    input_epoch_et_s : float
        Epoch in ephemeris time, in seconds.
    input_body_fixed_state_m : np.ndarray
        Six-component body-fixed state vector with position in metres and
        velocity in metres per second.

    Returns
    -------
    np.ndarray
        Six-component inertial state vector with position in metres and
        velocity in metres per second.
    """

    body_fixed_to_inertial_rotation_matrix: np.ndarray = (
        rotation_model.body_fixed_to_inertial_rotation(input_epoch_et_s)
    )
    inertial_rotational_velocity_rad_s: np.ndarray = (
        rotation_model.angular_velocity_in_inertial_frame(input_epoch_et_s)
    )

    input_body_fixed_position_m: np.ndarray = input_body_fixed_state_m[0:3]
    input_body_fixed_velocity_m_s: np.ndarray = input_body_fixed_state_m[3:6]
    output_inertial_position_m: np.ndarray = (
        body_fixed_to_inertial_rotation_matrix @ input_body_fixed_position_m
    )
    output_inertial_velocity_m_s: np.ndarray = (
        body_fixed_to_inertial_rotation_matrix @ input_body_fixed_velocity_m_s
        + np.cross(inertial_rotational_velocity_rad_s, output_inertial_position_m)
    )

    return np.concatenate([output_inertial_position_m, output_inertial_velocity_m_s])


def convert_frame(
    base_frame: Frame,
    target_frame: Frame,
    epoch_tt_s: float,
    input_state_m: np.ndarray,
) -> np.ndarray | None:
    """Convert a state vector from one frame to another.

    Parameters
    ----------
    base_frame : Frame
        Source reference frame for the input state vector.
    target_frame : Frame
        Destination reference frame for the output state vector.
    epoch_tt_s : float
        Epoch in TT seconds since J2000, used to evaluate time-dependent
        rotations.
    input_state_m : np.ndarray
        Six-component state vector ``[x, y, z, vx, vy, vz]`` in metres and
        m/s in the base frame.

    Returns
    -------
    np.ndarray | None
        Six-component state vector in metres and m/s in the target frame,
        or *None* if the conversion is not supported.

    Raises
    ------
    ValueError
        If the base frame or target frame is not supported.

    Notes
    -----
    Equivalent inertial frames (J2000, EME2000, ICRF, GCRF) are treated as
    J2000 for TudatPy conversions. The function routes through J2000 as an
    intermediate frame when converting between non-inertial frames.
    """

    # Handle equivalent inertial frames as J2000 for TudatPy conversions.
    if (
        base_frame == Frame.J2000
        or base_frame == Frame.EME2000
        or base_frame == Frame.ICRF
        or base_frame == Frame.GCRF
    ):
        base_frame = Frame.J2000

    # Handle equivalent inertial frames as J2000 for TudatPy conversions.
    if (
        target_frame == Frame.J2000
        or target_frame == Frame.EME2000
        or target_frame == Frame.ICRF
        or target_frame == Frame.GCRF
    ):
        target_frame = Frame.J2000

    if base_frame == target_frame:
        return input_state_m

    if base_frame == Frame.TEME or base_frame == Frame.J2000:
        if base_frame == Frame.TEME:
            j2000_state_m = teme_to_j2000(epoch_tt_s, input_state_m)
        else:
            j2000_state_m = input_state_m

        if target_frame == Frame.J2000:
            return j2000_state_m
        elif target_frame == Frame.TEME:
            return j2000_to_teme(epoch_tt_s, j2000_state_m)
        elif target_frame == Frame.ITRF1993:
            rotation_model = tudat_spice_rotation_model()
            return tudat_convert_inertial_to_body_fixed(
                rotation_model, epoch_tt_s, j2000_state_m
            )
        elif target_frame == Frame.ITRF:
            rotation_model = tudat_iau2006_rotation_model()
            return tudat_convert_inertial_to_body_fixed(
                rotation_model, epoch_tt_s, j2000_state_m
            )
        else:
            raise ValueError(f"Unsupported target frame: {target_frame}")

    elif base_frame == Frame.ITRF1993:
        rotation_model = tudat_spice_rotation_model()
        j2000_state_m = tudat_convert_body_fixed_to_inertial(
            rotation_model, epoch_tt_s, input_state_m
        )

        if target_frame == Frame.J2000:
            return j2000_state_m
        elif target_frame == Frame.TEME:
            return j2000_to_teme(epoch_tt_s, j2000_state_m)
        elif target_frame == Frame.ITRF:
            rotation_model = tudat_iau2006_rotation_model()
            return tudat_convert_inertial_to_body_fixed(
                rotation_model, epoch_tt_s, j2000_state_m
            )
        else:
            raise ValueError(f"Unsupported target frame: {target_frame}")

    elif base_frame == Frame.ITRF:
        rotation_model = tudat_iau2006_rotation_model()
        j2000_state_m = tudat_convert_body_fixed_to_inertial(
            rotation_model, epoch_tt_s, input_state_m
        )

        if target_frame == Frame.J2000:
            return j2000_state_m
        elif target_frame == Frame.TEME:
            return j2000_to_teme(epoch_tt_s, j2000_state_m)
        elif target_frame == Frame.ITRF1993:
            rotation_model = tudat_spice_rotation_model()
            return tudat_convert_inertial_to_body_fixed(
                rotation_model, epoch_tt_s, j2000_state_m
            )
        else:
            raise ValueError(f"Unsupported target frame: {target_frame}")

    else:
        raise ValueError(f"Unsupported base frame: {base_frame}")
