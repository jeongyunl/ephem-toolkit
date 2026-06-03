#!/usr/bin/env python3
from __future__ import annotations

"""
# Perturbed satellite orbit
## Objectives
This example demonstrates the propagation of a (quasi-massless) body dominated by
a central point-mass attractor, but also including multiple perturbing
accelerations exerted by the central body as well as third bodies.

The example showcases the ease with which a simulation environment can be
extended to a multi-body system. It also demonstrates the wide variety of
acceleration types that can be modelled using the `propagation_setup.acceleration`
module, including accelerations from non-conservative forces such as drag and
radiation pressure. Note that the modelling of these acceleration types requires
special environment interfaces (implemented via
[AerodynamicCoefficientSettings](https://py.api.tudat.space/en/latest/aerodynamic_coefficients.html)
and
[RadiationPressureTargetModelSettings](https://py.api.tudat.space/en/latest/radiation_pressure.html))
of the body undergoing the accelerations.

It also demonstrates and motivates the usage of dependent variables. By keeping
track of such variables throughout the propagation, valuable insight, such as
contributions of individual acceleration types, ground tracks or the evolution
of Kepler elements, can be derived in the post-propagation analysis.

The script expects exactly one OEM-like state line as input with epoch and six
cartesian components: ``UTC_ISO x y z vx vy vz`` where position is in km and
velocity in km/s. Input is read from ``--initial-state`` when provided,
otherwise from stdin.
"""

"""
## Import statements

Only the bare minimum needed for CLI argument parsing (`argparse`, `re`) is
imported at the top of the file.  Every other module -- including standard
library, numpy, tudatpy, and matplotlib -- is imported as late as possible,
immediately before its first use.  This keeps ``--help`` and argument
validation instant and defers heavy library initialisation until the point
where it is actually required.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.common import (
    parse_duration_to_seconds,
    SECONDS_PER_MINUTE,
    SECONDS_PER_HOUR,
    SECONDS_PER_DAY,
)

HOURS_PER_DAY = 24.0
KILOMETERS_TO_METERS = 1e3


# CLI and model defaults
DEFAULT_SATELLITE_NAME = "Satellite"
DEFAULT_SATELLITE_DRAG_COEFFICIENT = 2.2
DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT = 1.2
DEFAULT_SATELLITE_MASS_KG = 30

# 3U CubeSat geometry assumptions used for average projection area
DEFAULT_CUBESAT_LENGTH_M = 0.45
DEFAULT_CUBESAT_WIDTH_M = 0.3
DEFAULT_CUBESAT_HEIGHT_M = 0.3
DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2 = (
    4 * DEFAULT_CUBESAT_LENGTH_M * DEFAULT_CUBESAT_WIDTH_M
    + 2 * DEFAULT_CUBESAT_WIDTH_M * DEFAULT_CUBESAT_HEIGHT_M
) / 4

# Propagation and plotting settings
DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE = 5
DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER = 5
DEFAULT_BODIES_TO_CREATE = ["Sun", "Earth"]
DEFAULT_GLOBAL_FRAME_ORIGIN = "Earth"
DEFAULT_GLOBAL_FRAME_ORIENTATION = "J2000"

DEFAULT_INTEGRATOR_FIXED_STEP_SIZE_S = 10.0
DEFAULT_SIMULATION_DURATION_S = SECONDS_PER_DAY

# Supported integrator method identifiers accepted by the CLI.
# Values should match names in propagation_setup.integrator.CoefficientSets.
#
# Method descriptions are the single source of truth for supported methods.
INTEGRATOR_METHOD_DESCRIPTIONS = {
    "rk_3": "classic RK3",
    "rk_4": "classic RK4",
    "rkf_45": "Fehlberg 4(5)",
    "rkf_56": "Fehlberg 5(6)",
    "rkf_78": "Fehlberg 7(8)",
    "rkf_89": "Fehlberg 8(9)",
    "rkf_108": "Fehlberg 10(8)",
    "rkf_1210": "Fehlberg 12(10)",
    "rkf_1412": "Fehlberg 14(12)",
    "rkdp_87": "Dormand-Prince 8(7)",
    "rkv_89": "Verner 8(9)",
}
SUPPORTED_INTEGRATOR_METHODS = tuple(INTEGRATOR_METHOD_DESCRIPTIONS)
DEFAULT_INTEGRATOR_METHOD = "rk_4"

# Plotting constants (values only -- matplotlib is imported later, just before use)
PLOT_STANDARD_FIGURE_SIZE_IN = (9, 5)
PLOT_KEPLER_FIGURE_SIZE_IN = (9, 12)
PLOT_GROUND_TRACK_H = 3
PLOT_SCATTER_MARKER_SIZE_PT2 = 1
PLOT_LATITUDE_TICK_STEP_DEG = 45
PLOT_TRUE_ANOMALY_TICK_STEP_DEG = 60
EARTH_MEAN_RADIUS_KM = 6378.137


def parse_bool_flag(value: str) -> bool:
    """Parse a CLI boolean token.

    Parameters
    ----------
    value : str
        Input token to parse.

    Returns
    -------
    bool
        Parsed boolean value.

    Notes
    -----
    Accepted true values are ``on``, ``true``, ``yes``, and ``enable``.
    Accepted false values are ``off``, ``false``, ``no``, and ``disable``.
    """
    lower = value.strip().lower()
    if lower in ("on", "true", "yes", "enable"):
        return True
    if lower in ("off", "false", "no", "disable"):
        return False
    raise argparse.ArgumentTypeError(
        f"invalid boolean value: '{value}' "
        "(expected on/off, true/false, yes/no, or enable/disable)"
    )


def parse_integrator_method(value: str) -> str:
    """Parse the integrator method identifier from CLI input.

    Parameters
    ----------
    value : str
        Integrator method token.

    Returns
    -------
    str
        Normalized method identifier.
    """
    method = value.strip().lower()
    if method not in SUPPORTED_INTEGRATOR_METHODS:
        raise argparse.ArgumentTypeError(
            "integrator must be one of: " + ", ".join(SUPPORTED_INTEGRATOR_METHODS)
        )
    return method


def parse_integrator_step_size_values(value: str) -> tuple[float, ...]:
    """Parse integrator step-size values from CLI input.

    Parameters
    ----------
    value : str
        Comma-separated step-size token in seconds.

    Returns
    -------
    tuple[float, ...]
        Parsed step-size values in seconds. One value selects fixed-step size
        integration; three values represent ``(initial, minimum, maximum)`` for
        variable-step size integration.

    Notes
    -----
    Accepted forms are ``<fixed_step>``,
    ``<initial_and_minimum_step>,<maximum_step>``, and
    ``<initial_step>,<minimum_step>,<maximum_step>``. For the two-value form,
    the first value is reused for both initial and minimum step size.
    """
    parts = [part.strip() for part in value.split(",") if part.strip()]
    try:
        if len(parts) == 1:
            step_size_values = (float(parts[0]),)
        elif len(parts) == 2:
            step_size_values = (
                float(
                    parts[0]
                ),  # initial_step. initial_and_minimum_step normalized to initial_step = minimum_step
                float(parts[0]),  # minimum_step
                float(parts[1]),  # maximum_step
            )
        elif len(parts) == 3:
            step_size_values = tuple(float(part) for part in parts)
        else:
            raise argparse.ArgumentTypeError(
                "integrator step size must be one, two, or three comma-separated values "
                "(<fixed_step> or <initial_and_minimum_step>,<maximum_step> or "
                "<initial_step>,<minimum_step>,<maximum_step>)"
            )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "integrator step size values must be valid numbers in seconds"
        ) from exc

    if any(step_size_s <= 0.0 for step_size_s in step_size_values):
        raise argparse.ArgumentTypeError(
            "integrator step size values must be positive numbers in seconds"
        )

    if len(step_size_values) == 1:
        return step_size_values

    initial_step_size_s, minimum_step_size_s, maximum_step_size_s = step_size_values
    if minimum_step_size_s > maximum_step_size_s:
        raise argparse.ArgumentTypeError(
            "for variable-step size integrator, minimum_step must be less than or equal to "
            "maximum_step"
        )
    if not (minimum_step_size_s <= initial_step_size_s <= maximum_step_size_s):
        raise argparse.ArgumentTypeError(
            "for variable-step size integrator, initial_step must be between minimum_step "
            "and maximum_step"
        )

    return step_size_values


def parse_mass_kg(value: str) -> float:
    """Parse satellite mass from CLI input.

    Parameters
    ----------
    value : str
        Mass token in kilograms.

    Returns
    -------
    float
        Positive mass in kilograms.
    """
    try:
        mass_kg = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("mass must be a valid number in kg") from exc

    if mass_kg <= 0.0:
        raise argparse.ArgumentTypeError("mass must be a positive value in kg")

    return mass_kg


def parse_earth_spherical_harmonic_gravity_degree_order(value: str) -> tuple[int, int]:
    """Parse Earth spherical-harmonic gravity degree and order.

    Parameters
    ----------
    value : str
        Degree/order token in ``DxO`` format.

    Returns
    -------
    tuple[int, int]
        Parsed ``(degree, order)`` pair.

    Notes
    -----
    In ``DxO``, ``D`` means degree and ``O`` means order. Examples include
    ``5x5`` and ``8X6``.
    """
    match = re.fullmatch(r"\s*([0-9]+)\s*[xX]\s*([0-9]+)\s*", value)
    if not match:
        raise argparse.ArgumentTypeError(
            "earth gravity must be in DxO format (D=degree, O=order; e.g., 5x5, 8x6)"
        )

    degree = int(match.group(1))
    order = int(match.group(2))

    if degree < 0:
        raise argparse.ArgumentTypeError("earth gravity degree must be non-negative")
    if order < 0:
        raise argparse.ArgumentTypeError("earth gravity order must be non-negative")
    if order > degree:
        raise argparse.ArgumentTypeError("earth gravity order must be less than or equal to degree")

    return degree, order


def parse_drag_area_m2(value: str) -> float:
    """Parse drag/reference area from CLI input.

    Parameters
    ----------
    value : str
        Area token in square meters.

    Returns
    -------
    float
        Positive area value in square meters.
    """
    try:
        drag_area_m2 = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("drag area must be a valid number in m^2") from exc

    if drag_area_m2 <= 0.0:
        raise argparse.ArgumentTypeError("drag area must be a positive value in m^2")

    return drag_area_m2


def parse_srp_coefficient(value: str) -> float:
    """Parse the solar radiation pressure coefficient from CLI input.

    Parameters
    ----------
    value : str
        Coefficient token.

    Returns
    -------
    float
        Positive SRP coefficient.
    """
    try:
        srp_coefficient = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "solar radiation pressure coefficient must be a valid number"
        ) from exc

    if srp_coefficient <= 0.0:
        raise argparse.ArgumentTypeError(
            "solar radiation pressure coefficient must be a positive value"
        )

    return srp_coefficient


def parse_drag_coefficient(value: str) -> float:
    """Parse the aerodynamic drag coefficient from CLI input.

    Parameters
    ----------
    value : str
        Coefficient token.

    Returns
    -------
    float
        Positive drag coefficient.
    """
    try:
        drag_coefficient = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("drag coefficient must be a valid number") from exc

    if drag_coefficient <= 0.0:
        raise argparse.ArgumentTypeError("drag coefficient must be a positive value")

    return drag_coefficient


def build_cli_parser():
    """Create the command-line argument parser for this script.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for all supported CLI options.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run perturbed orbit propagation from one OEM-style state line and "
            "a user-provided simulation duration."
        )
    )
    parser.add_argument(
        "-i",
        "--initial-state",
        metavar="<oem_state_line>",
        help=(
            "One OEM-style state line provided directly on the command line. "
            "If omitted, one line is read from stdin."
        ),
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=parse_duration_to_seconds,
        metavar="<value[s|m|h|d]>",
        default=DEFAULT_SIMULATION_DURATION_S,
        help=(
            "Simulation duration (default: 1d). "
            "Use -d/--duration, e.g. -d 90, --duration 90s, -d 2m, --duration 1.5h, -d 1d."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default=None,
        help=(
            "Write propagated state history in OEM-like format to a file. "
            "Use '-' to write to stdout. If omitted, no state-history output is written."
        ),
    )

    # Satellite properties
    parser.add_argument(
        "--name",
        default=DEFAULT_SATELLITE_NAME,
        metavar="<name>",
        help=f"Name of the propagated satellite body (default: {DEFAULT_SATELLITE_NAME}).",
    )
    parser.add_argument(
        "--mass",
        type=parse_mass_kg,
        metavar="<kg>",
        default=DEFAULT_SATELLITE_MASS_KG,
        help=(
            "Mass of the propagated satellite in kilograms "
            f"(default: {DEFAULT_SATELLITE_MASS_KG})."
        ),
    )

    # Integrator method and step size
    parser.add_argument(
        "--integrator",
        type=parse_integrator_method,
        metavar=f"<{ '|'.join(SUPPORTED_INTEGRATOR_METHODS) }>",
        default=DEFAULT_INTEGRATOR_METHOD,
        help=(
            "Numerical integrator method identifier. "
            f"(default: {DEFAULT_INTEGRATOR_METHOD}; "
            "methods: "
            + "; ".join(
                f"{method}={INTEGRATOR_METHOD_DESCRIPTIONS[method]}"
                for method in SUPPORTED_INTEGRATOR_METHODS
            )
            + ")."
        ),
    )
    parser.add_argument(
        "--integrator-step-size",
        type=parse_integrator_step_size_values,
        metavar="<fixed|init,max|init,min,max>",
        default=(DEFAULT_INTEGRATOR_FIXED_STEP_SIZE_S,),
        help=(
            "Integrator step sizes in seconds as a single comma-separated token. "
            "Provide either one value for fixed-step size (for example, 10) "
            "or two values for variable-step size as <initial_and_minimum_step>,<maximum_step> "
            "(for example, 0.001,1000), "
            "or three values for variable-step size in this order: "
            "<initial_step>,<minimum_step>,<maximum_step> "
            "(for example, 30,0.001,1000). "
            f"(default: {DEFAULT_INTEGRATOR_FIXED_STEP_SIZE_S})."
        ),
    )

    # Earth spherical harmonic gravity degree/order
    parser.add_argument(
        "--earth-gravity",
        type=parse_earth_spherical_harmonic_gravity_degree_order,
        metavar="<DxO>",
        default=(
            DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE,
            DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER,
        ),
        help=(
            "Earth spherical harmonic gravity degree/order in DxO format "
            "(D=degree, O=order) "
            "(default: "
            f"{DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE}x"
            f"{DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER})."
        ),
    )

    # Drag area (also used as the cannonball reference area for SRP)
    parser.add_argument(
        "--drag-area",
        type=parse_drag_area_m2,
        metavar="<m^2>",
        default=DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
        help=(
            "Drag area / average projection area of the propagated satellite in m^2 "
            f"(default: {DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2})."
        ),
    )

    # Solar radiation pressure
    parser.add_argument(
        "--srp",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help=("Enable or disable solar radiation pressure acceleration (default: on)."),
    )
    parser.add_argument(
        "--srp-coeff",
        type=parse_srp_coefficient,
        metavar="<coefficient>",
        default=DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT,
        help=(
            "Solar radiation pressure coefficient of the propagated satellite "
            f"(default: {DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT})."
        ),
    )

    # Aerodynamic drag
    parser.add_argument(
        "--drag",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help=("Enable or disable aerodynamic drag acceleration (default: on)."),
    )
    parser.add_argument(
        "--drag-coeff",
        type=parse_drag_coefficient,
        metavar="<coefficient>",
        default=DEFAULT_SATELLITE_DRAG_COEFFICIENT,
        help=f"Drag coefficient of the propagated satellite (default: {DEFAULT_SATELLITE_DRAG_COEFFICIENT}).",
    )

    parser.add_argument(
        "--moon-gravity",
        dest="moon_gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help=("Enable or disable Moon point-mass gravity perturbation (default: on)."),
    )
    parser.add_argument(
        "--sun-gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help=("Enable or disable Sun point-mass gravity perturbation (default: on)."),
    )
    parser.add_argument(
        "--venus-gravity",
        dest="venus_gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help=("Enable or disable Venus point-mass gravity perturbation (default: on)."),
    )
    parser.add_argument(
        "--mars-gravity",
        dest="mars_gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help=("Enable or disable Mars point-mass gravity perturbation (default: on)."),
    )
    return parser


# Parse CLI arguments once for script-wide configuration.
# Only argparse and re have been imported so far, so --help and validation
# errors are returned instantly without waiting for heavy library loads.
cli_args = build_cli_parser().parse_args()


# Standard-library modules -- imported just after CLI parsing succeeds,
# right before they are first needed by the code that follows.
import io
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Suppress warnings that tudatpy / urllib3 may emit on import.
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

# numpy -- imported just before PropagationInputs and state-vector construction.
import numpy as np


@dataclass
class PropagationInputs:
    """Container for propagation input options and parsed initial-state data.

    Attributes
    ----------
    satellite_name : str
        Name of the propagated vehicle body added to the Tudat environment.
    satellite_mass_kg : float
        Spacecraft mass in kilograms used by dynamics propagation.
    integrator_method : str
        Numerical integrator method identifier used by propagation settings.
    integrator_step_size_values_s : tuple[float, ...]
        Step-size input in seconds from CLI. One value selects fixed-step size
        integration; three values ``(initial, minimum, maximum)`` select
        variable-step size integration.
    earth_spherical_harmonic_gravity_degree : int
        Degree used for Earth's spherical harmonic gravity field.
    earth_spherical_harmonic_gravity_order : int
        Order used for Earth's spherical harmonic gravity field.
    satellite_drag_area_m2 : float
        Effective drag/reference area in square meters used for aerodynamic drag
        and, in this script, also reused as the cannonball reference area for SRP.
    is_srp_on : bool
        Whether solar radiation pressure acceleration is enabled.
    srp_coefficient : float
        Dimensionless solar radiation pressure coefficient (Cr) used when SRP is enabled.
    is_earth_drag_on : bool
        Whether aerodynamic drag acceleration from Earth's atmosphere is enabled.
    satellite_drag_coefficient : float
        Dimensionless aerodynamic drag coefficient (Cd) used when drag is enabled.
    is_moon_gravity_on : bool
        Whether Moon point-mass gravity perturbation is enabled.
    is_sun_gravity_on : bool
        Whether Sun point-mass gravity perturbation is enabled.
    is_venus_gravity_on : bool
        Whether Venus point-mass gravity perturbation is enabled.
    is_mars_gravity_on : bool
        Whether Mars point-mass gravity perturbation is enabled.
    initial_epoch_datetime_utc : datetime
        Start epoch parsed from OEM input, represented as UTC datetime.
    initial_state_m_mps : numpy.ndarray
        Initial translational state vector [x, y, z, vx, vy, vz] in SI units,
        where position is in meters and velocity is in meters per second.
    simulation_duration_s : float
        Total propagation duration in seconds.
    """

    satellite_name: str
    satellite_mass_kg: float

    integrator_method: str
    integrator_step_size_values_s: tuple[float, ...]

    earth_spherical_harmonic_gravity_degree: int
    earth_spherical_harmonic_gravity_order: int

    satellite_drag_area_m2: float

    is_srp_on: bool
    srp_coefficient: float

    is_earth_drag_on: bool
    satellite_drag_coefficient: float

    is_moon_gravity_on: bool
    is_sun_gravity_on: bool
    is_venus_gravity_on: bool
    is_mars_gravity_on: bool

    initial_epoch_datetime_utc: datetime
    initial_state_m_mps: np.ndarray

    simulation_duration_s: float


def load_spice_kernels():
    """Load required SPICE kernels for propagation support.

    Kernels are loaded from Tudat's managed kernel directory returned by
    ``common.common.get_spice_kernel_path()``.

    Returns
    -------
    None
        This function mutates the global SPICE kernel pool.
    """

    spice_kernel_files = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
        "gm_de431.tpc",  # PLANETARY CONSTANTS KERNEL FILE: gravitational parameters for natural bodies
        "earth_200101_990825_predict.bpc",  # Earth rotation prediction. Covers Jan, 2001 to Aug, 2099
        "tudat_merged_spk_kernel.bsp",  # Merged SPK kernel containing ephemerides for various bodies, including Earth, Sun, Moon, Mars, Venus
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(common.get_spice_kernel_path() + "/" + kernel_file)


def read_initial_state_from_stream(stream):
    """Read one OEM-like state record from a text stream.

    Parameters
    ----------
    stream : IO[str]
        Input stream providing one state line.

    Expected line format is:
    ``YYYY-MM-DDTHH:MM:SS.sss x y z vx vy vz`` where position is in km and
    velocity is in km/s.

    Returns
    -------
    tuple[numpy.ndarray, datetime.datetime]
        ``(initial_state_m_mps, initial_epoch_datetime_utc)`` where
        ``initial_state_m_mps`` is a 6-element cartesian state in SI units.
    """
    line = stream.readline()
    if line == "":
        raise ValueError("No input line available in stream")

    parsed = common.parse_oem_state_line(line)
    if parsed is None:
        raise ValueError("The first input line is blank/comment and was not parsed")

    epoch_dt, position_km, velocity_km_s = parsed
    initial_epoch_datetime_utc = epoch_dt
    initial_state_m_mps = np.concatenate([position_km, velocity_km_s]) * KILOMETERS_TO_METERS
    return initial_state_m_mps, initial_epoch_datetime_utc


def read_initial_state_from_cli_or_stdin(cli_args):
    """Read one OEM-like state record from CLI input sources.

    Parameters
    ----------
    cli_args : argparse.Namespace
        Parsed CLI arguments.

    Source precedence is:
    1. ``--initial-state`` value, if provided.
    2. One line from stdin, when stdin is piped.

    This function prints a user-facing error and exits with status 1 when no
    valid input line is available.

    Returns
    -------
    tuple[numpy.ndarray, datetime.datetime]
        ``(initial_state_m_mps, initial_epoch_datetime_utc)``.
    """
    if cli_args.initial_state is not None:
        try:
            return read_initial_state_from_stream(io.StringIO(cli_args.initial_state + "\n"))
        except ValueError as exc:
            print(f"Error: invalid --initial-state value: {exc}", file=sys.stderr)
            sys.exit(1)

    if not sys.stdin.isatty():
        try:
            return read_initial_state_from_stream(sys.stdin)
        except ValueError as exc:
            print(f"Error: invalid stdin input: {exc}", file=sys.stderr)
            sys.exit(1)

    print(
        "Error: missing input data. Provide one OEM-style state line via --initial-state or stdin.",
        file=sys.stderr,
    )
    print(
        "Example (CLI): .../perturbed_satellite_orbit.py --duration 86400 --initial-state '2023-04-10T00:00:00.000 7000 0 0 0 7.5 1.0'",
        file=sys.stderr,
    )
    print(
        "Example (stdin): echo '2023-04-10T00:00:00.000 7000 0 0 0 7.5 1.0' | .../perturbed_satellite_orbit.py -d 86400",
        file=sys.stderr,
    )
    sys.exit(1)


def build_propagation_inputs(cli_args) -> PropagationInputs:
    """Build propagation inputs from CLI options and parsed state data.

    Parameters
    ----------
    cli_args : argparse.Namespace
        Parsed CLI arguments.

    The initial-state reader returns only the SI state vector and the parsed UTC
    epoch, which are the only values needed downstream.

    Empty or whitespace-only satellite names are normalized to
    ``DEFAULT_SATELLITE_NAME``.

    Returns
    -------
    PropagationInputs
        Consolidated, validated propagation inputs.
    """
    satellite_name = cli_args.name.strip() if cli_args.name is not None else ""
    if not satellite_name:
        satellite_name = DEFAULT_SATELLITE_NAME

    (
        initial_state_m_mps,
        initial_epoch_datetime_utc,
    ) = read_initial_state_from_cli_or_stdin(cli_args)
    (
        earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order,
    ) = cli_args.earth_gravity

    integrator_step_size_values = tuple(cli_args.integrator_step_size)

    return PropagationInputs(
        satellite_name=satellite_name,
        satellite_mass_kg=cli_args.mass,
        integrator_method=cli_args.integrator,
        integrator_step_size_values_s=integrator_step_size_values,
        earth_spherical_harmonic_gravity_degree=earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order=earth_spherical_harmonic_gravity_order,
        satellite_drag_area_m2=cli_args.drag_area,
        is_srp_on=cli_args.srp,
        srp_coefficient=cli_args.srp_coeff,
        is_earth_drag_on=cli_args.drag,
        satellite_drag_coefficient=cli_args.drag_coeff,
        is_moon_gravity_on=cli_args.moon_gravity,
        is_sun_gravity_on=cli_args.sun_gravity,
        is_venus_gravity_on=cli_args.venus_gravity,
        is_mars_gravity_on=cli_args.mars_gravity,
        initial_epoch_datetime_utc=initial_epoch_datetime_utc,
        initial_state_m_mps=initial_state_m_mps,
        simulation_duration_s=cli_args.duration,
    )


def write_state_history_oem_like(state_history, output_path):
    """Write state history as OEM-like lines.

    Parameters
    ----------
    state_history : dict[float, numpy.ndarray]
        Mapping of TDB seconds since J2000 to 6-element cartesian state vectors
        in SI units ``[x, y, z, vx, vy, vz]``.
    output_path : str
        Output file path, or ``'-'`` to write to stdout.

    Returns
    -------
    None
        Writes one line per epoch in ``UTC_ISO x y z vx vy vz`` format, where
        position is in km and velocity in km/s.
    """
    if output_path == "-":
        stream = sys.stdout
        should_close = False
    else:
        stream = open(output_path, "w", encoding="utf-8")
        should_close = True

    try:
        for epoch_tdb_s, state_m_mps in sorted(state_history.items()):
            epoch_utc_iso = common.tdb_to_datetime(epoch_tdb_s).isoformat(timespec="microseconds")
            position_km = state_m_mps[:3] / KILOMETERS_TO_METERS
            velocity_km_s = state_m_mps[3:] / KILOMETERS_TO_METERS
            stream.write(
                f"{epoch_utc_iso} "
                f"{position_km[0]:.9f} {position_km[1]:.9f} {position_km[2]:.9f} "
                f"{velocity_km_s[0]:.9f} {velocity_km_s[1]:.9f} {velocity_km_s[2]:.9f}\n"
            )
    finally:
        if should_close:
            stream.close()


def print_pre_propagation_summary(
    propagation_inputs: PropagationInputs,
    input_source: str,
    output_state_history_path: str | None = None,
):
    """Print the pre-propagation configuration summary.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.
    input_source : str
        Input source label displayed to the user.
    output_state_history_path : str | None, optional
        State-history output destination. Use ``'-'`` for stdout.

    Returns
    -------
    None
        This function prints a formatted summary to stdout.
    """

    print("=== Propagation Configuration ===")
    print(f"Input source: {input_source}")
    print(f"Satellite name: {propagation_inputs.satellite_name}")
    print(f"Satellite mass [kg]: {propagation_inputs.satellite_mass_kg}")

    # integrator_method and integrator_step_size_values_s
    # display integrator method and step size(s), with mode (fixed or variable)
    # inferred from the number of step size values provided.
    integrator_description = INTEGRATOR_METHOD_DESCRIPTIONS.get(
        propagation_inputs.integrator_method, "unknown method"
    )
    print(
        "Integrator method: " f"{propagation_inputs.integrator_method} ({integrator_description})"
    )
    if len(propagation_inputs.integrator_step_size_values_s) == 1:
        print("Integrator mode: fixed-step size")
        print("Integrator step size [s]: " f"{propagation_inputs.integrator_step_size_values_s[0]}")
    else:
        print("Integrator mode: variable-step size")
        (
            initial_step_size_s,
            minimum_step_size_s,
            maximum_step_size_s,
        ) = propagation_inputs.integrator_step_size_values_s
        print(
            "Integrator step sizes [s] "
            f"(initial, minimum, maximum): {initial_step_size_s}, "
            f"{minimum_step_size_s}, {maximum_step_size_s}"
        )

    # earth_spherical_harmonic_gravity_degree and earth_spherical_harmonic_gravity_order
    print(
        "Earth spherical harmonic gravity [degree x order]: "
        f"{propagation_inputs.earth_spherical_harmonic_gravity_degree}x"
        f"{propagation_inputs.earth_spherical_harmonic_gravity_order}"
    )

    # satellite_drag_area_m2: display drag area, which is used for both drag and SRP in this script.
    print(f"Drag area [m^2]: {propagation_inputs.satellite_drag_area_m2}")

    # is_srp_on: display SRP status; only show coefficient when SRP is enabled.
    print(f"Solar radiation pressure: {'on' if propagation_inputs.is_srp_on else 'off'}")
    if propagation_inputs.is_srp_on:
        print(f"Solar radiation pressure coefficient: {propagation_inputs.srp_coefficient}")

    # is_earth_drag_on: display drag status; only show coefficient when drag is enabled.
    print(f"Aerodynamic drag: {'on' if propagation_inputs.is_earth_drag_on else 'off'}")
    if propagation_inputs.is_earth_drag_on:
        print(f"Drag coefficient: {propagation_inputs.satellite_drag_coefficient}")

    # is_sun_gravity_on / is_moon_gravity_on / is_mars_gravity_on /
    # is_venus_gravity_on: display third-body gravity status.
    print(f"Moon gravity: {'on' if propagation_inputs.is_moon_gravity_on else 'off'}")
    print(f"Sun gravity: {'on' if propagation_inputs.is_sun_gravity_on else 'off'}")
    print(f"Venus gravity: {'on' if propagation_inputs.is_venus_gravity_on else 'off'}")
    print(f"Mars gravity: {'on' if propagation_inputs.is_mars_gravity_on else 'off'}")

    print(f"Initial epoch: {propagation_inputs.initial_epoch_datetime_utc.isoformat()}")
    initial_position_km = propagation_inputs.initial_state_m_mps[:3] / KILOMETERS_TO_METERS
    initial_velocity_kmps = propagation_inputs.initial_state_m_mps[3:] / KILOMETERS_TO_METERS
    print(
        "Initial position vector [km]: "
        f"{np.array2string(initial_position_km, precision=6, separator=', ')}"
    )
    print(
        "Initial velocity vector [km/s]: "
        f"{np.array2string(initial_velocity_kmps, precision=6, separator=', ')}"
    )
    print(f"Simulation duration [s]: {propagation_inputs.simulation_duration_s}")
    simulation_end_epoch_datetime_utc = propagation_inputs.initial_epoch_datetime_utc + timedelta(
        seconds=propagation_inputs.simulation_duration_s
    )
    print("Simulation end epoch: " f"{simulation_end_epoch_datetime_utc.isoformat()}")
    if output_state_history_path is not None:
        output_destination = (
            "stdout" if output_state_history_path == "-" else output_state_history_path
        )
        print(f"State-history output: {output_destination}")
    print("=================================")


def create_translational_propagator_settings(
    propagation_inputs: PropagationInputs,
    central_bodies,
    acceleration_models,
    bodies_to_propagate,
    dependent_variables_to_save,
):
    """Create translational propagator settings for the configured run.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.
    central_bodies : list[str]
        Central bodies for translational dynamics.
    acceleration_models : object
        Acceleration model map returned by Tudat setup utilities.
    bodies_to_propagate : list[str]
        Bodies whose translational states are propagated.
    dependent_variables_to_save : list
        Dependent-variable save settings passed to the propagator.

    Fixed-step integration is selected when one step-size value is provided.
    Variable-step integration is selected when three values are provided and
    uses element-wise scalar tolerances of ``1e-10`` for both absolute and
    relative error control.

    Returns
    -------
    object
        Tudat translational propagator settings object.
    """
    # Resolve the CoefficientSets entry by integrator method name.
    try:
        coefficient_set = getattr(
            propagation_setup.integrator.CoefficientSets,
            propagation_inputs.integrator_method,
        )
    except AttributeError as exc:
        raise ValueError(
            "Unsupported integrator method "
            f"'{propagation_inputs.integrator_method}'. Supported methods are: "
            f"{', '.join(SUPPORTED_INTEGRATOR_METHODS)}. "
            f"Default is {DEFAULT_INTEGRATOR_METHOD}."
        ) from exc

    # Configure fixed-step size or variable-step size integrator based on the number of step-size values.
    if len(propagation_inputs.integrator_step_size_values_s) == 1:
        fixed_step_size_s = propagation_inputs.integrator_step_size_values_s[0]
        integrator_settings = propagation_setup.integrator.runge_kutta_fixed_step(
            fixed_step_size_s,
            coefficient_set=coefficient_set,
        )
    else:
        (
            initial_step_size_s,
            minimum_step_size_s,
            maximum_step_size_s,
        ) = propagation_inputs.integrator_step_size_values_s

        step_size_validation_settings = propagation_setup.integrator.step_size_validation(
            minimum_step_size_s, maximum_step_size_s
        )

        step_size_control_settings = (
            propagation_setup.integrator.step_size_control_elementwise_scalar_tolerance(
                1.0e-10, 1.0e-10
            )
        )

        integrator_settings = propagation_setup.integrator.runge_kutta_variable_step(
            initial_time_step=initial_step_size_s,
            coefficient_set=coefficient_set,
            step_size_validation_settings=step_size_validation_settings,
            step_size_control_settings=step_size_control_settings,
        )

    simulation_end_epoch_datetime_utc = propagation_inputs.initial_epoch_datetime_utc + timedelta(
        seconds=propagation_inputs.simulation_duration_s
    )
    termination_condition = propagation_setup.propagator.time_termination(
        common.datetime_to_tdb(simulation_end_epoch_datetime_utc)
    )

    return propagation_setup.propagator.translational(
        central_bodies,
        acceleration_models,
        bodies_to_propagate,
        propagation_inputs.initial_state_m_mps,
        common.datetime_to_tdb(propagation_inputs.initial_epoch_datetime_utc),
        integrator_settings,
        termination_condition,
        output_variables=dependent_variables_to_save,
    )


def create_environment_and_bodies(propagation_inputs: PropagationInputs):
    """Create environment settings, add spacecraft interfaces, and build bodies.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.

    Sun and Earth are always present. Moon, Mars, and Venus are included only
    when their corresponding gravity flags are enabled. The spacecraft drag area
    is reused as the cannonball reference area for SRP.

    Returns
    -------
    object
        Tudat system-of-bodies object.
    """
    # Build the list of celestial bodies dynamically.  Sun and Earth are always
    # required; Moon, Mars, and Venus are only included when their respective
    # gravity perturbation is enabled.
    bodies_to_create = list(DEFAULT_BODIES_TO_CREATE)
    if propagation_inputs.is_moon_gravity_on:
        bodies_to_create.append("Moon")
    if propagation_inputs.is_mars_gravity_on:
        bodies_to_create.append("Mars")
    if propagation_inputs.is_venus_gravity_on:
        bodies_to_create.append("Venus")

    body_settings = environment_setup.get_default_body_settings(
        bodies_to_create,
        DEFAULT_GLOBAL_FRAME_ORIGIN,
        DEFAULT_GLOBAL_FRAME_ORIENTATION,
    )

    # Add the satellite as an empty body, then attach force-model interfaces based on enabled options.
    body_settings.add_empty_settings(propagation_inputs.satellite_name)

    # is_srp_on: only attach radiation pressure target settings when SRP is enabled.
    if propagation_inputs.is_srp_on:
        occulting_bodies_dict = {"Sun": ["Earth"]}
        vehicle_target_settings = environment_setup.radiation_pressure.cannonball_radiation_target(
            propagation_inputs.satellite_drag_area_m2,
            propagation_inputs.srp_coefficient,
            occulting_bodies_dict,
        )
        body_settings.get(propagation_inputs.satellite_name).radiation_pressure_target_settings = (
            vehicle_target_settings
        )

    # is_earth_drag_on: only attach aerodynamic coefficient settings when drag is enabled.
    if propagation_inputs.is_earth_drag_on:
        aero_coefficient_settings = environment_setup.aerodynamic_coefficients.constant(
            propagation_inputs.satellite_drag_area_m2,
            [propagation_inputs.satellite_drag_coefficient, 0.0, 0.0],
        )
        body_settings.get(propagation_inputs.satellite_name).aerodynamic_coefficient_settings = (
            aero_coefficient_settings
        )

    bodies = environment_setup.create_system_of_bodies(body_settings)
    bodies.get(propagation_inputs.satellite_name).mass = propagation_inputs.satellite_mass_kg
    return bodies


def create_acceleration_models(
    propagation_inputs: PropagationInputs,
    bodies,
    bodies_to_propagate,
    central_bodies,
):
    """Create acceleration models for the propagated satellite.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.
    bodies : object
        Tudat system-of-bodies object.
    bodies_to_propagate : list[str]
        Bodies whose translational states are propagated.
    central_bodies : list[str]
        Central bodies for translational dynamics.

    The model always includes Earth spherical-harmonic gravity and conditionally
    includes drag, SRP, and third-body point-mass perturbations according to
    CLI-derived flags.

    Returns
    -------
    object
        Tudat acceleration-model map.
    """
    # Define accelerations acting on the propagated satellite by Sun, Earth,
    # Moon, Mars, and Venus.
    satellite_acceleration_settings = {}

    # Sun accelerations: radiation pressure and/or point-mass gravity.
    sun_accelerations = []
    if propagation_inputs.is_srp_on:
        sun_accelerations.insert(0, propagation_setup.acceleration.radiation_pressure())
    if propagation_inputs.is_sun_gravity_on:
        sun_accelerations.append(propagation_setup.acceleration.point_mass_gravity())

    if sun_accelerations:
        satellite_acceleration_settings["Sun"] = sun_accelerations

    # is_earth_drag_on: include aerodynamic drag acceleration from Earth only
    # when drag is enabled.
    earth_accelerations = [
        propagation_setup.acceleration.spherical_harmonic_gravity(
            propagation_inputs.earth_spherical_harmonic_gravity_degree,
            propagation_inputs.earth_spherical_harmonic_gravity_order,
        ),
    ]
    if propagation_inputs.is_earth_drag_on:
        earth_accelerations.append(propagation_setup.acceleration.aerodynamic())
    satellite_acceleration_settings["Earth"] = earth_accelerations

    # is_moon_gravity_on: include Moon point-mass gravity only when enabled.
    if propagation_inputs.is_moon_gravity_on:
        satellite_acceleration_settings["Moon"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    # is_venus_gravity_on: include Venus point-mass gravity only when enabled.
    if propagation_inputs.is_venus_gravity_on:
        satellite_acceleration_settings["Venus"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    # is_mars_gravity_on: include Mars point-mass gravity only when enabled.
    if propagation_inputs.is_mars_gravity_on:
        satellite_acceleration_settings["Mars"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    # Create global accelerations settings dictionary.
    acceleration_settings = {propagation_inputs.satellite_name: satellite_acceleration_settings}

    return propagation_setup.create_acceleration_models(
        bodies, acceleration_settings, bodies_to_propagate, central_bodies
    )


def create_dependent_variables_to_save(propagation_inputs: PropagationInputs):
    """Create dependent-variable save settings for propagation and plotting.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.

    Returns
    -------
    tuple[list, list]
        ``(dependent_variables_to_save, acceleration_dependent_variables_to_save)``
        where the first list is passed to the propagator and the second list is
        reused later for acceleration-component plotting.
    """
    # Define list of dependent variables to save.
    dependent_variables_to_save = [
        dependent_variable.total_acceleration(propagation_inputs.satellite_name),
        dependent_variable.keplerian_state(propagation_inputs.satellite_name, "Earth"),
        dependent_variable.latitude(propagation_inputs.satellite_name, "Earth"),
        dependent_variable.longitude(propagation_inputs.satellite_name, "Earth"),
        dependent_variable.central_body_fixed_cartesian_position(
            propagation_inputs.satellite_name, "Earth"
        ),
    ]

    # Earth spherical harmonic gravity is always tracked; other norms are added
    # conditionally.
    acceleration_dependent_variables_to_save = [
        dependent_variable.single_acceleration_norm(
            propagation_setup.acceleration.spherical_harmonic_gravity_type,
            propagation_inputs.satellite_name,
            "Earth",
        ),
    ]

    # is_moon_gravity_on: track Moon gravity acceleration norm only when enabled.
    if propagation_inputs.is_moon_gravity_on:
        acceleration_dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Moon",
            ),
        )

    # is_sun_gravity_on: track Sun gravity acceleration norm only when enabled.
    if propagation_inputs.is_sun_gravity_on:
        acceleration_dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Sun",
            ),
        )

    # is_srp_on: track SRP acceleration norm only when SRP is enabled.
    if propagation_inputs.is_srp_on:
        acceleration_dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.radiation_pressure_type,
                propagation_inputs.satellite_name,
                "Sun",
            ),
        )

    # is_earth_drag_on: track aerodynamic drag acceleration norm only when enabled.
    if propagation_inputs.is_earth_drag_on:
        acceleration_dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.aerodynamic_type,
                propagation_inputs.satellite_name,
                "Earth",
            ),
        )

    # is_venus_gravity_on: track Venus gravity acceleration norm only when enabled.
    if propagation_inputs.is_venus_gravity_on:
        acceleration_dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Venus",
            ),
        )

    # is_mars_gravity_on: track Mars gravity acceleration norm only when enabled.
    if propagation_inputs.is_mars_gravity_on:
        acceleration_dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Mars",
            ),
        )

    dependent_variables_to_save += acceleration_dependent_variables_to_save
    return dependent_variables_to_save, acceleration_dependent_variables_to_save


def plot_total_acceleration(dep_var_dict, relative_time_h, satellite_name):
    """Plot total acceleration norm over time.

    Parameters
    ----------
    dep_var_dict : result2array.Result2ArrayLike
        Dependent-variable history accessor returned by Tudat.
    relative_time_h : numpy.ndarray
        Time history in hours from propagation start.
    satellite_name : str
        Name of the propagated satellite.

    Returns
    -------
    None
        This function creates a matplotlib figure.
    """
    plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    plt.title(f"Total acceleration norm on {satellite_name} over the course of propagation.")
    satellite_total_acceleration_mps2 = dep_var_dict.asarray(
        dependent_variable.total_acceleration(satellite_name)
    )
    total_acceleration_norm_mps2 = np.linalg.norm(satellite_total_acceleration_mps2, axis=1)
    plt.plot(relative_time_h, total_acceleration_norm_mps2)
    plt.xlabel("Time [hr]")
    plt.ylabel("Total Acceleration [m/s$^2$]")
    plt.grid()
    plt.tight_layout()


def plot_ground_track(dep_var_dict, relative_time_h, satellite_name):
    """Plot ground track for the first configured window (default: 3 hours).

    Parameters
    ----------
    dep_var_dict : result2array.Result2ArrayLike
        Dependent-variable history accessor returned by Tudat.
    relative_time_h : numpy.ndarray
        Time history in hours from propagation start.
    satellite_name : str
        Name of the propagated satellite.

    If the propagation is shorter than the configured window, all available
    points are shown.

    Returns
    -------
    None
        This function creates a matplotlib figure.
    """
    plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    plt.title(f"3 hour ground track of {satellite_name}")
    latitude_rad = dep_var_dict.asarray(dependent_variable.latitude(satellite_name, "Earth"))
    longitude_rad = dep_var_dict.asarray(dependent_variable.longitude(satellite_name, "Earth"))
    subset_count = int(len(relative_time_h) / HOURS_PER_DAY * PLOT_GROUND_TRACK_H)
    latitude_deg = np.rad2deg(latitude_rad[0:subset_count])
    longitude_deg = np.rad2deg(longitude_rad[0:subset_count])
    plt.scatter(longitude_deg, latitude_deg, s=PLOT_SCATTER_MARKER_SIZE_PT2)
    plt.xlabel("Longitude [deg]")
    plt.ylabel("Latitude [deg]")
    plt.yticks(np.arange(-90, 91, step=PLOT_LATITUDE_TICK_STEP_DEG))
    plt.grid()
    plt.tight_layout()


def plot_kepler_elements(dep_var_dict, relative_time_h, satellite_name):
    """Plot osculating Keplerian elements over time.

    Parameters
    ----------
    dep_var_dict : result2array.Result2ArrayLike
        Dependent-variable history accessor returned by Tudat.
    relative_time_h : numpy.ndarray
        Time history in hours from propagation start.
    satellite_name : str
        Name of the propagated satellite.

    Semi-major axis is shown in km. Angular elements are shown in degrees.

    Returns
    -------
    None
        This function creates a matplotlib figure.
    """
    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(
        3, 2, figsize=PLOT_KEPLER_FIGURE_SIZE_IN
    )
    fig.suptitle("Evolution of Kepler elements over the course of the propagation.")

    kepler_elements = dep_var_dict.asarray(
        dependent_variable.keplerian_state(satellite_name, "Earth")
    )

    semi_major_axis_km = kepler_elements[:, 0] / KILOMETERS_TO_METERS
    ax1.plot(relative_time_h, semi_major_axis_km)
    ax1.set_ylabel("Semi-major axis [km]")

    eccentricity = kepler_elements[:, 1]
    ax2.plot(relative_time_h, eccentricity)
    ax2.set_ylabel("Eccentricity [-]")

    inclination_deg = np.rad2deg(kepler_elements[:, 2])
    ax3.plot(relative_time_h, inclination_deg)
    ax3.set_ylabel("Inclination [deg]")

    argument_of_periapsis_deg = np.rad2deg(kepler_elements[:, 3])
    ax4.plot(relative_time_h, argument_of_periapsis_deg)
    ax4.set_ylabel("Argument of Periapsis [deg]")

    raan_deg = np.rad2deg(kepler_elements[:, 4])
    ax5.plot(relative_time_h, raan_deg)
    ax5.set_ylabel("RAAN [deg]")

    true_anomaly_deg = np.rad2deg(kepler_elements[:, 5])
    ax6.scatter(relative_time_h, true_anomaly_deg, s=PLOT_SCATTER_MARKER_SIZE_PT2)
    ax6.set_ylabel("True Anomaly [deg]")
    ax6.set_yticks(np.arange(0, 361, step=PLOT_TRUE_ANOMALY_TICK_STEP_DEG))

    for ax in fig.get_axes():
        ax.set_xlabel("Time [hr]")
        ax.grid()
    plt.tight_layout()


def plot_acceleration_components(
    dep_var_dict,
    relative_time_h,
    acceleration_dependent_variables_to_save,
    satellite_name,
):
    """Plot acceleration norms by type and source body on a log scale.

    Parameters
    ----------
    dep_var_dict : result2array.Result2ArrayLike
        Dependent-variable history accessor returned by Tudat.
    relative_time_h : numpy.ndarray
        Time history in hours from propagation start.
    acceleration_dependent_variables_to_save : list
        Acceleration dependent-variable settings used for extraction and labels.
    satellite_name : str
        Name of the propagated satellite.

    Returns
    -------
    None
        This function creates a matplotlib figure.
    """
    acceleration_type_to_string = {
        acceleration.AvailableAcceleration.point_mass_gravity_type: "Point Mass",
        acceleration.AvailableAcceleration.spherical_harmonic_gravity_type: "SphHarm Grav",
        acceleration.AvailableAcceleration.aerodynamic_type: "Aerodynamic Drag",
        acceleration.AvailableAcceleration.radiation_pressure_type: "Radiation Pressure",
    }

    plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)

    for acceleration_dep_var_setting in acceleration_dependent_variables_to_save:
        acceleration_norm_mps2 = dep_var_dict.asarray(acceleration_dep_var_setting)
        label = (
            f"{acceleration_type_to_string[acceleration_dep_var_setting.acceleration_model_type]}: "
            f"{acceleration_dep_var_setting.secondary_body}"
        )

        plt.plot(relative_time_h, acceleration_norm_mps2, label=label)

    plt.xlabel("Time [hr]")
    plt.ylabel("Acceleration Norm [m/s$^2$]")
    plt.legend(bbox_to_anchor=(1.005, 1))
    plt.suptitle(
        f"Accelerations norms on {satellite_name}, distinguished by type and origin, over the course of propagation."
    )
    plt.yscale("log")
    plt.grid()
    plt.tight_layout()


def plot_satellite_position_history_3d(dep_var_dict, satellite_name):
    """Plot propagated 3D trajectory in Earth-fixed coordinates with Earth.

    Parameters
    ----------
    dep_var_dict : result2array.Result2ArrayLike
        Dependent-variable history accessor returned by Tudat.
    satellite_name : str
        Name of the propagated satellite.

    Returns
    -------
    matplotlib.animation.FuncAnimation | None
        Animation object for the 3D trajectory, or ``None`` when no samples
        are available.
    """
    from matplotlib.animation import FuncAnimation

    positions_m = dep_var_dict.asarray(
        dependent_variable.central_body_fixed_cartesian_position(
            satellite_name,
            "Earth",
        )
    )
    if positions_m.size == 0:
        return
    positions_km = positions_m / KILOMETERS_TO_METERS

    fig = plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    ax = fig.add_subplot(111, projection="3d")

    # Draw Earth as a semi-transparent sphere centered at the origin.
    azimuth = np.linspace(0.0, 2.0 * np.pi, 60)
    polar = np.linspace(0.0, np.pi, 30)
    earth_x = EARTH_MEAN_RADIUS_KM * np.outer(np.cos(azimuth), np.sin(polar))
    earth_y = EARTH_MEAN_RADIUS_KM * np.outer(np.sin(azimuth), np.sin(polar))
    earth_z = EARTH_MEAN_RADIUS_KM * np.outer(np.ones_like(azimuth), np.cos(polar))
    ax.plot_surface(earth_x, earth_y, earth_z, color="lightskyblue", alpha=0.35)

    # Draw Earth's polar axis (Earth-fixed +Z / -Z axis).
    polar_axis_extent_km = 1.5 * EARTH_MEAN_RADIUS_KM
    ax.plot(
        [0.0, 0.0],
        [0.0, 0.0],
        [-polar_axis_extent_km, polar_axis_extent_km],
        color="tab:blue",
        linestyle=":",
        linewidth=1.5,
        label="Earth polar axis",
    )
    polar_axis_label_offset_km = 0.03 * polar_axis_extent_km
    ax.text(
        0.0,
        0.0,
        polar_axis_extent_km + polar_axis_label_offset_km,
        "N",
        color="tab:blue",
        ha="center",
        va="bottom",
    )
    ax.text(
        0.0,
        0.0,
        -polar_axis_extent_km - polar_axis_label_offset_km,
        "S",
        color="tab:blue",
        ha="center",
        va="top",
    )

    (trajectory_line,) = ax.plot(
        [],
        [],
        [],
        color="tab:red",
        label=f"{satellite_name} trajectory",
    )
    moving_satellite_marker = ax.scatter(
        [],
        [],
        [],
        color="tab:orange",
        s=22,
        label="current",
    )
    ax.scatter(
        positions_km[0, 0],
        positions_km[0, 1],
        positions_km[0, 2],
        color="tab:green",
        s=20,
        label="start",
    )
    ax.scatter(
        positions_km[-1, 0],
        positions_km[-1, 1],
        positions_km[-1, 2],
        color="tab:purple",
        s=20,
        label="end",
    )

    # Keep an equal visual scale on all axes.
    max_extent_km = (
        max(
            np.max(np.abs(positions_km)),
            EARTH_MEAN_RADIUS_KM,
            polar_axis_extent_km + polar_axis_label_offset_km,
        )
        * 1.05
    )
    ax.set_xlim(-max_extent_km, max_extent_km)
    ax.set_ylim(-max_extent_km, max_extent_km)
    ax.set_zlim(-max_extent_km, max_extent_km)
    ax.set_box_aspect((1.0, 1.0, 1.0))

    ax.set_xlabel("X [km]")
    ax.set_ylabel("Y [km]")
    ax.set_zlabel("Z [km]")
    ax.set_title(f"3D animated position history of {satellite_name} around Earth")
    ax.legend(loc="upper left", bbox_to_anchor=(-0.22, 1.0))

    sample_count = positions_km.shape[0]
    max_animation_frames = 1000
    if sample_count > max_animation_frames:
        frame_indices = np.linspace(
            0,
            sample_count - 1,
            num=max_animation_frames,
            dtype=int,
        )
    else:
        frame_indices = np.arange(sample_count)

    def initialize_animation():
        trajectory_line.set_data([], [])
        trajectory_line.set_3d_properties([])
        moving_satellite_marker._offsets3d = ([], [], [])
        return trajectory_line, moving_satellite_marker

    def update_animation(frame_number):
        sample_index = frame_indices[frame_number]
        visible_positions_km = positions_km[: sample_index + 1]

        trajectory_line.set_data(
            visible_positions_km[:, 0],
            visible_positions_km[:, 1],
        )
        trajectory_line.set_3d_properties(visible_positions_km[:, 2])

        moving_satellite_marker._offsets3d = (
            [positions_km[sample_index, 0]],
            [positions_km[sample_index, 1]],
            [positions_km[sample_index, 2]],
        )
        return trajectory_line, moving_satellite_marker

    trajectory_animation = FuncAnimation(
        fig,
        update_animation,
        frames=len(frame_indices),
        init_func=initialize_animation,
        interval=30,
        blit=False,
        repeat=True,
    )
    return trajectory_animation


def plot_satellite_state_history_3d(state_history, satellite_name):
    """Plot propagated 3D state history in the ECI frame with Earth.

    Parameters
    ----------
    state_history : dict[float, numpy.ndarray]
        State history mapping TDB seconds since J2000 to 6-element cartesian
        state vectors in SI units.
    satellite_name : str
        Name of the propagated satellite.

    Returns
    -------
    None
        This function creates a static matplotlib 3D figure.
    """
    if not state_history:
        return

    epochs_tdb_s = np.array(sorted(state_history))
    state_vectors_m_mps = np.array([state_history[epoch] for epoch in epochs_tdb_s])
    positions_km = state_vectors_m_mps[:, :3] / KILOMETERS_TO_METERS

    fig = plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    ax = fig.add_subplot(111, projection="3d")

    # Draw Earth as a semi-transparent sphere centered at the origin.
    azimuth = np.linspace(0.0, 2.0 * np.pi, 60)
    polar = np.linspace(0.0, np.pi, 30)
    earth_x = EARTH_MEAN_RADIUS_KM * np.outer(np.cos(azimuth), np.sin(polar))
    earth_y = EARTH_MEAN_RADIUS_KM * np.outer(np.sin(azimuth), np.sin(polar))
    earth_z = EARTH_MEAN_RADIUS_KM * np.outer(np.ones_like(azimuth), np.cos(polar))
    ax.plot_surface(earth_x, earth_y, earth_z, color="lightskyblue", alpha=0.35)

    # Draw the inertial Z axis aligned with Earth's mean spin axis.
    polar_axis_extent_km = 1.5 * EARTH_MEAN_RADIUS_KM
    ax.plot(
        [0.0, 0.0],
        [0.0, 0.0],
        [-polar_axis_extent_km, polar_axis_extent_km],
        color="tab:blue",
        linestyle=":",
        linewidth=1.5,
        label="ECI Z axis",
    )
    polar_axis_label_offset_km = 0.03 * polar_axis_extent_km
    ax.text(
        0.0,
        0.0,
        polar_axis_extent_km + polar_axis_label_offset_km,
        "N",
        color="tab:blue",
        ha="center",
        va="bottom",
    )
    ax.text(
        0.0,
        0.0,
        -polar_axis_extent_km - polar_axis_label_offset_km,
        "S",
        color="tab:blue",
        ha="center",
        va="top",
    )

    ax.plot(
        positions_km[:, 0],
        positions_km[:, 1],
        positions_km[:, 2],
        color="tab:red",
        label=f"{satellite_name} state history",
    )
    ax.scatter(
        positions_km[0, 0],
        positions_km[0, 1],
        positions_km[0, 2],
        color="tab:green",
        s=20,
        label="start",
    )
    ax.scatter(
        positions_km[-1, 0],
        positions_km[-1, 1],
        positions_km[-1, 2],
        color="tab:purple",
        s=20,
        label="end",
    )

    max_extent_km = (
        max(
            np.max(np.abs(positions_km)),
            EARTH_MEAN_RADIUS_KM,
            polar_axis_extent_km + polar_axis_label_offset_km,
        )
        * 1.05
    )
    ax.set_xlim(-max_extent_km, max_extent_km)
    ax.set_ylim(-max_extent_km, max_extent_km)
    ax.set_zlim(-max_extent_km, max_extent_km)
    ax.set_box_aspect((1.0, 1.0, 1.0))

    ax.set_xlabel("X [km]")
    ax.set_ylabel("Y [km]")
    ax.set_zlabel("Z [km]")
    ax.set_title(f"3D state history of {satellite_name} in the ECI frame")
    ax.legend(loc="upper left", bbox_to_anchor=(-0.22, 1.0))


# ===================================================================
# Main execution
# ===================================================================

"""
## Configuration
NAIF's `SPICE` kernels are first loaded, so that the position of various bodies
such as the Earth can be made known to `tudatpy`.
See SPICE in Tudat docs:
https://docs.tudat.space/en/latest/_src_user_guide/state_propagation/environment_setup/default_env_models.html
for an overview of the use of SPICE in Tudat.
"""

# common.common -- first module that pulls in tudatpy (via tudatpy.astro.time_representation).
# Imported here, just before build_propagation_inputs() which is its first caller.
import common.common as common

propagation_inputs = build_propagation_inputs(cli_args)
input_source = "--initial-state" if cli_args.initial_state is not None else "stdin"
satellite_name = propagation_inputs.satellite_name
output_state_history_path = cli_args.output

print_pre_propagation_summary(
    propagation_inputs,
    input_source,
    output_state_history_path,
)

# tudatpy SPICE interface -- imported just before loading kernels.
from tudatpy.interface import spice

# Load spice kernels
load_spice_kernels()

# tudatpy dynamics modules -- imported just before environment/body creation.
from tudatpy.dynamics import environment_setup, propagation_setup, simulator

"""
## Environment setup
Let's create the environment for our simulation. This setup covers the creation
of (celestial) bodies, vehicle(s), and environment interfaces.

For more information on how to create and customize settings, see the user guide:
https://docs.tudat.space/en/latest/_src_user_guide/state_propagation/environment_setup.html

### Create the bodies
**Celestial** bodies can be created by making a list of strings with the bodies
that is to be included in the simulation.

For the most common celestial bodies in our Solar system, default settings (such
as atmosphere, body shape, rotation model) come predefined in Tudat.
See the user guide on default environment models:
https://docs.tudat.space/en/latest/_src_user_guide/state_propagation/environment_setup.html
for a comprehensive list of default models.

These settings can be adjusted. Please refer to Available Environment Models:
https://docs.tudat.space/en/latest/_src_user_guide/state_propagation/environment_setup/environment_models.html
in the user guide for more details.
"""


bodies = create_environment_and_bodies(propagation_inputs)


"""
## Propagation setup
Now that the environment is created, the propagation setup is defined.

First, the bodies to be propagated and the central bodies will be defined.
Central bodies are the bodies with respect to which the state of the respective propagated bodies is defined.
"""


# Define bodies that are propagated
bodies_to_propagate = [propagation_inputs.satellite_name]

# Define central bodies of propagation
central_bodies = ["Earth"]


"""
### Create the acceleration model
First off, the acceleration settings that act on the propagated satellite are to be defined.
In this case, these consist in the followings:

- Gravitational acceleration of Earth modeled as spherical harmonic gravity,
  with degree/order taken from ``--earth-gravity``.
- Gravitational acceleration of the Sun, the Moon, Mars, and Venus, modeled as a Point Mass.
- Aerodynamic acceleration caused by the atmosphere of the Earth (using the aerodynamic interface defined earlier).
- Radiation pressure acceleration caused by the Sun (using the radiation interface defined earlier).

The acceleration settings dictionary and resulting models are built by
``create_acceleration_models(...)``.
"""


# Create acceleration models via helper.
acceleration_models = create_acceleration_models(
    propagation_inputs=propagation_inputs,
    bodies=bodies,
    bodies_to_propagate=bodies_to_propagate,
    central_bodies=central_bodies,
)


"""
### Define propagation start and end epochs

Next, the start and end simulation epochs are specified.
In Tudat, all epochs are defined as seconds since J2000.
Within this script, the OEM input line is first parsed into a UTC `datetime`
and an SI cartesian state vector.  The UTC epoch is then converted to TDB
seconds since J2000 via `datetime_to_tdb` only at the points where Tudat
requires it.  The end epoch is computed by adding the CLI-provided simulation
duration to the start epoch using Python's `datetime` and `timedelta`.
"""


# Simulation duration is parsed from CLI near the top of the script.


"""
### Define the initial state
The initial state of the vehicle that will be propagated is now defined. 

This initial state always has to be provided as a cartesian state, in the form of a
numpy array with the first three elements representing the initial position (in meters),
and the three remaining elements representing the initial velocity (in meters per second).

Within this script, the initial state is read from exactly one OEM-style state line
provided either through `--initial-state`/`-i` or stdin.
"""


"""
### Define dependent variables to save
In this example, we are interested in saving not only the propagated state of
the satellite over time, but also a set of so-called dependent variables, that
are to be computed (or extracted and saved) at each integration step.

[This page](https://py.api.tudat.space/en/latest/dependent_variable.html) of the
tudatpy API website provides a detailed explanation of all the dependent
variables that are available.

For later post-processing, we first define all single acceleration norm settings
in the `acceleration_dependent_variables_to_save` variable (which we will reuse
later) and then combine it with all other dependent variables saved in the
`dependent_variables_to_save` variable. This setup is built by
``create_dependent_variables_to_save(...)``.
"""

# dependent_variable and acceleration sub-modules -- imported just before
# defining the dependent variable list.
from tudatpy.dynamics.propagation_setup import dependent_variable, acceleration

# Build propagation and acceleration-specific dependent variable settings.
(
    dependent_variables_to_save,
    acceleration_dependent_variables_to_save,
) = create_dependent_variables_to_save(propagation_inputs)


"""
### Create the propagator settings
The propagator is finally setup.

The integrator, termination condition, and translational propagator settings are
constructed together through a dedicated helper function.
"""

"""
## Propagate the orbit
The orbit is now ready to be propagated.

The propagation is done by calling the `create_dynamics_simulator()` function of
the `dynamics.simulator` module, which requires the `bodies` and
`propagator_settings` that have all been defined earlier.
After successful propagation, results are stored in the `propagation_results`
attribute of each `dynamics_simulator` instance.

The results will be analyzed in the following post-processing section.

"""


"""
## Post-process the propagation results
The results of the propagation are extracted from the `dynamics_simulator` instance.

The dependent variables are retrieved via a `DependentVariableDictionary` created by
`create_dependent_variable_dictionary`.  This dictionary allows retrieval of a specific
dependent variable by passing the corresponding `SingleDependentVariableSaveSettings`
object to its `asarray()` method, avoiding manual column-index book-keeping.

Each row of the returned array stores the dependent variable values at one integration
step, with the corresponding epochs available through the `time_history` attribute.
"""

# create_dependent_variable_dictionary -- imported just before post-processing.
import tudatpy.dynamics.propagation as propagation

# Create propagator settings.
propagator_settings = create_translational_propagator_settings(
    propagation_inputs=propagation_inputs,
    central_bodies=central_bodies,
    acceleration_models=acceleration_models,
    bodies_to_propagate=bodies_to_propagate,
    dependent_variables_to_save=dependent_variables_to_save,
)

# Run the propagation and extract results.
dynamics_simulator = simulator.create_dynamics_simulator(bodies, propagator_settings)

# state_history: dict[time(float), state(numpy.ndarray)] with time in seconds since J2000 and state as a 6-element array of cartesian state.
state_history = dynamics_simulator.propagation_results.state_history
if output_state_history_path is not None:
    try:
        write_state_history_oem_like(state_history, output_state_history_path)
    except OSError as exc:
        print(f"Error: failed to write state-history output: {exc}", file=sys.stderr)
        sys.exit(1)

dep_var_dict = propagation.create_dependent_variable_dictionary(dynamics_simulator)
relative_time_h = (dep_var_dict.time_history - dep_var_dict.time_history[0]) / SECONDS_PER_HOUR


"""
### Retrieve information from the dependent variable dictionary

For an in-depth documentation of how to retrieve information from the
`DependentVariableDictionary`, see the corresponding API reference:
https://py.api.tudat.space/en/latest/dynamics/propagation.html.
In short, by passing a `SingleDependentVariableSaveSettings` object to the
`asarray()` method, the dependent variables will be retrieved and returned as an
array, where each row stores the dependent variables of an integration step
(with the corresponding epochs stored in the `time_history` attribute).
"""

# matplotlib -- imported as late as possible, just before the first plot call.
from matplotlib import pyplot as plt

# Generate and display plots.
plot_total_acceleration(dep_var_dict, relative_time_h, satellite_name)
plot_ground_track(dep_var_dict, relative_time_h, satellite_name)
plot_kepler_elements(dep_var_dict, relative_time_h, satellite_name)
plot_acceleration_components(
    dep_var_dict,
    relative_time_h,
    acceleration_dependent_variables_to_save,
    satellite_name,
)
_trajectory_animation = plot_satellite_position_history_3d(
    dep_var_dict,
    satellite_name,
)
plot_satellite_state_history_3d(state_history, satellite_name)


plt.show()
