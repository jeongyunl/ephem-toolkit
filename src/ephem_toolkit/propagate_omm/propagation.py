"""Reusable OMM/TLE propagation and output helpers."""

from __future__ import annotations

import datetime as dt
import io
import sys
import warnings
from typing import TextIO

import numpy as np

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.propagator.kepler as kepler
from ephem_toolkit.core.propagator import (
    DSSTPropagator,
    DsstPerturbations,
    KeplerPropagator,
    KeplerianState,
    OutputMode,
    Sgp4Propagator,
)
import ephem_toolkit.core.spice_utils as spice_utils
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.core.tle as tle_mod

# CLI defaults
DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 5.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (5 minutes)."""


# ===================================================================
# OMM input
# ===================================================================


def read_tle_input(cli_value: str | None) -> tle_mod.Tle:
    """Read and parse a TLE from file or stdin.

    Parameters
    ----------
    cli_value : str | None
        Path to TLE file, or "-" for stdin.

    Returns
    -------
    tle_mod.Tle
        Parsed TLE object.
    """
    if cli_value == "-" or cli_value is None:
        if sys.stdin.isatty():
            raise ValueError(
                "Input not provided. Pass <input_file> or pipe TLE text on stdin."
            )

        stdin_text: str = sys.stdin.read()
        if not stdin_text.strip():
            raise ValueError("Empty stdin input. Provide TLE text on stdin.")
        return tle_mod.read_tle(io.StringIO(stdin_text))

    return tle_mod.read_tle(cli_value)


def read_omm_input(cli_value: str | None) -> omm.CcsdsOmm:
    """Read and parse an OMM from file or stdin.

    Parameters
    ----------
    cli_value : str | None
        Path to OMM file, or "-" for stdin.

    Returns
    -------
    omm.CcsdsOmm
        Parsed OMM object.
    """
    if cli_value == "-" or cli_value is None:
        if sys.stdin.isatty():
            raise ValueError(
                "OMM input not provided. Pass <omm_file> or pipe OMM text on stdin."
            )

        stdin_text: str = sys.stdin.read()
        if not stdin_text.strip():
            raise ValueError("Empty stdin input. Provide OMM text on stdin.")
        return omm.CcsdsOmm.from_source(io.StringIO(stdin_text))

    return omm.CcsdsOmm.from_source(cli_value)


# ===================================================================
# TLE propagation path (SGP4)
# ===================================================================


def load_spice_kernels() -> None:
    """Load SPICE kernels required for time conversion."""
    spice_kernel_files: list[str] = [
        "naif0012.tls",
        "pck00011.tpc",
    ]
    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


def propagate_tle_sgp4(
    tle_obj: tle_mod.Tle,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
    output_path: str = "-",
) -> None:
    """Propagate a TLE with SGP4 and emit OEM output.

    Parameters
    ----------
    tle_obj : tle_mod.Tle
        TLE object to propagate.
    start_time : dt.datetime
        Propagation start epoch (UTC).
    stop_time : dt.datetime
        Propagation stop epoch (UTC).
    step_s : float
        Output sampling interval (s).
    data_only : bool
        If True, emit state lines only (no OEM header).
    output_path : str, optional
        Output path or "-" for stdout.
    """
    object_name: str = tle_obj.object_name or "UNKNOWN"

    load_spice_kernels()

    if stop_time < start_time:
        raise ValueError(
            "Invalid propagation window: stop epoch must be >= start epoch.\n"
            f"  Resolved start: {time_utils.datetime_to_iso8601(start_time)}\n"
            f"  Resolved stop:  {time_utils.datetime_to_iso8601(stop_time)}"
        )

    # Create SGP4 propagator
    propagator = Sgp4Propagator(tle_obj)

    propagated_states: list[tuple[float, np.ndarray]] = []
    step_dt = dt.timedelta(seconds=step_s)
    current_time: dt.datetime = start_time
    while current_time <= stop_time:
        current_tt_s: float = time_utils.datetime_to_tt_s(current_time)
        result = propagator.propagate_to(current_tt_s, output=OutputMode.FINAL)
        if not isinstance(result, tuple):
            raise RuntimeError("Propagator did not return a final state tuple")
        epoch_tt_s, state_m = result
        propagated_states.append((epoch_tt_s, state_m))
        current_time = current_time + step_dt

    _write_oem_output(
        propagated_states, object_name, tle_obj.get_object_id(), data_only, output_path
    )


def propagate_omm_sgp4(
    omm_data: omm.CcsdsOmm,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
    output_path: str = "-",
) -> None:
    """Propagate OMM with TLE parameters using TudatPy SGP4.

    Parameters
    ----------
    omm_data : omm.CcsdsOmm
        Parsed OMM with TLE parameters.
    start_time : dt.datetime
        Propagation start epoch (UTC).
    stop_time : dt.datetime
        Propagation stop epoch (UTC).
    step_s : float
        Output sampling interval (s).
    data_only : bool
        If True, emit state lines only (no OEM header).
    output_path : str
        Output path or "-" for stdout.
    """
    # Convert OMM to TLE, then format TLE lines for SGP4
    tle_obj: tle_mod.Tle = convert_tle.omm_to_tle(omm_data)

    propagate_tle_sgp4(tle_obj, start_time, stop_time, step_s, data_only, output_path)


# ===================================================================
# Kepler propagation path (two-body)
# ===================================================================


def propagate_omm_dsst(
    omm_data: omm.CcsdsOmm,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
    output_path: str = "-",
) -> None:
    """Propagate OMM with DSST mean elements.

    Parameters
    ----------
    omm_data : omm.CcsdsOmm
        Parsed OMM with DSST mean elements.
    start_time : dt.datetime
        Propagation start epoch (UTC).
    stop_time : dt.datetime
        Propagation stop epoch (UTC).
    step_s : float
        Output sampling interval (s).
    data_only : bool
        If True, emit state lines only (no OEM header).
    output_path : str
        Output path or "-" for stdout.
    """
    if stop_time < start_time:
        raise ValueError(
            "Invalid propagation window: stop epoch must be >= start epoch.\n"
            f"  Resolved start: {time_utils.datetime_to_iso8601(start_time)}\n"
            f"  Resolved stop:  {time_utils.datetime_to_iso8601(stop_time)}"
        )

    # Convert OMM mean elements to DSST mean Keplerian state vector [a, e, i, ω, Ω, M]
    initial_kepler: np.ndarray = np.array(
        [
            kepler.mean_motion_to_semi_major_axis(omm_data.mean_motion),
            omm_data.eccentricity,
            np.radians(omm_data.inclination),
            np.radians(omm_data.arg_of_pericenter),
            np.radians(omm_data.ra_of_asc_node),
            np.radians(omm_data.mean_anomaly),  # DSST uses mean anomaly
        ],
        dtype=float,
    )

    epoch_dt: dt.datetime = time_utils.iso8601_to_datetime(omm_data.epoch)
    object_name: str = omm_data.object_name or "UNKNOWN"

    # Configure DSST perturbations from OMM spacecraft parameters
    perturbations = DsstPerturbations(include_j2=True)
    if omm_data.spacecraft_parameters is not None:
        sp = omm_data.spacecraft_parameters
        if (
            sp.drag_area is not None
            and sp.drag_coeff is not None
            and sp.mass is not None
        ):
            perturbations.include_drag = True
            perturbations.drag_area_m2 = sp.drag_area
            perturbations.drag_coeff = sp.drag_coeff
            perturbations.mass_kg = sp.mass
        if sp.solar_rad_area is not None and sp.solar_rad_coeff is not None:
            perturbations.include_srp = True
            perturbations.srp_area_m2 = sp.solar_rad_area
            perturbations.srp_coeff = sp.solar_rad_coeff

    # Create DSST propagator
    epoch_tt_s = time_utils.datetime_to_tt_s(epoch_dt)
    dsst_state = KeplerianState(elements=initial_kepler, epoch_s=epoch_tt_s)
    propagator = DSSTPropagator(initial_state=dsst_state, perturbations=perturbations)

    propagated_states: list[tuple[float, np.ndarray]] = []
    step_dt = dt.timedelta(seconds=step_s)
    current_time: dt.datetime = start_time
    while current_time <= stop_time:
        current_tt_s = time_utils.datetime_to_tt_s(current_time)
        result = propagator.propagate_to(current_tt_s, output=OutputMode.FINAL)
        if not isinstance(result, tuple):
            raise RuntimeError("Propagator did not return a final state tuple")
        epoch_tt_s, cartesian_m = result
        propagated_states.append((epoch_tt_s, cartesian_m))
        current_time = current_time + step_dt

    _write_oem_output(
        propagated_states, object_name, omm_data.object_id, data_only, output_path
    )


def propagate_omm_kepler(
    omm_data: omm.CcsdsOmm,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
    output_path: str = "-",
) -> None:
    """Propagate OMM mean elements using two-body Kepler propagator.

    Parameters
    ----------
    omm_data : omm.CcsdsOmm
        Parsed OMM without TLE parameters.
    start_time : dt.datetime
        Propagation start epoch (UTC).
    stop_time : dt.datetime
        Propagation stop epoch (UTC).
    step_s : float
        Output sampling interval (s).
    data_only : bool
        If True, emit state lines only (no OEM header).
    output_path : str
        Output path or "-" for stdout.
    """
    if stop_time < start_time:
        raise ValueError(
            "Invalid propagation window: stop epoch must be >= start epoch.\n"
            f"  Resolved start: {time_utils.datetime_to_iso8601(start_time)}\n"
            f"  Resolved stop:  {time_utils.datetime_to_iso8601(stop_time)}"
        )

    # Convert OMM mean elements to Keplerian state vector [a, e, i, ω, Ω, θ]
    initial_kepler: np.ndarray = np.array(
        [
            kepler.mean_motion_to_semi_major_axis(omm_data.mean_motion),
            omm_data.eccentricity,
            np.radians(omm_data.inclination),
            np.radians(omm_data.arg_of_pericenter),
            np.radians(omm_data.ra_of_asc_node),
            kepler.mean_to_true_anomaly(
                np.radians(omm_data.mean_anomaly), omm_data.eccentricity
            ),
        ],
        dtype=float,
    )

    epoch_dt: dt.datetime = time_utils.iso8601_to_datetime(omm_data.epoch)
    object_name: str = omm_data.object_name or "UNKNOWN"

    # Create propagator once outside loop
    epoch_tt_s = time_utils.datetime_to_tt_s(epoch_dt)
    kepler_state = KeplerianState(elements=initial_kepler, epoch_s=epoch_tt_s)
    propagator = KeplerPropagator(initial_state=kepler_state)

    propagated_states: list[tuple[float, np.ndarray]] = []
    step_dt = dt.timedelta(seconds=step_s)
    current_time: dt.datetime = start_time
    while current_time <= stop_time:
        current_tt_s = time_utils.datetime_to_tt_s(current_time)
        result = propagator.propagate_to(current_tt_s, output=OutputMode.FINAL)
        if not isinstance(result, tuple):
            raise RuntimeError("Propagator did not return a final state tuple")
        epoch_tt_s, cartesian_m = result
        propagated_states.append((epoch_tt_s, cartesian_m))
        current_time = current_time + step_dt

    _write_oem_output(
        propagated_states, object_name, omm_data.object_id, data_only, output_path
    )


# ===================================================================
# Common OEM output
# ===================================================================


def _write_oem_output(
    propagated_states: list[tuple[float, np.ndarray]],
    object_name: str,
    object_id: str,
    data_only: bool,
    output_path: str,
) -> None:
    """Write propagated states as OEM output.

    Parameters
    ----------
    propagated_states : list[tuple[float, np.ndarray]]
        List of (TT seconds since J2000, state_vector) tuples.
    object_name : str
        Object name for OEM metadata.
    object_id : str
        Object ID for OEM metadata.
    data_only : bool
        If True, emit state lines only.
    output_path : str
        Output path or "-" for stdout.
    """

    def emit(output_stream: TextIO) -> None:
        if data_only:
            oem.CcsdsOem.from_states(propagated_states).write_states(output_stream)
        else:
            oem_obj: oem.CcsdsOem = oem.CcsdsOem.from_states(
                propagated_states,
                object_name=object_name,
                object_id=object_id,
                ref_frame="EME2000",
                center_name="EARTH",
                time_system="UTC",
            )
            oem_obj.write(output_stream)

    if output_path == "-":
        emit(sys.stdout)
        return

    with open(output_path, "w", encoding="utf-8") as output_stream:
        emit(output_stream)


# ===================================================================
# Time resolution helpers
# ===================================================================


def resolve_epoch_datetime(
    reference_dt: dt.datetime,
    spec: dt.datetime | dt.timedelta,
) -> dt.datetime:
    """Resolve absolute UTC datetime from a datetime or offset specification."""
    if isinstance(spec, dt.timedelta):
        return reference_dt + spec
    return spec


def resolve_time_bounds(
    reference_dt: dt.datetime,
    start_spec: dt.datetime | dt.timedelta,
    stop_spec: dt.datetime | dt.timedelta | None,
    duration_s: float = DEFAULT_PROPAGATION_DURATION_S,
) -> tuple[dt.datetime, dt.datetime]:
    """Resolve absolute start and stop datetimes for a propagation window."""
    start_time = resolve_epoch_datetime(reference_dt, start_spec)
    if stop_spec is None:
        stop_time = start_time + dt.timedelta(seconds=duration_s)
    else:
        stop_time = resolve_epoch_datetime(start_time, stop_spec)
    return start_time, stop_time
