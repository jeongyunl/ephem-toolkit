"""CLI argument parsing functions for orbit propagation."""

from __future__ import annotations

import argparse
import re

import ephem_toolkit.core.time_utils as time_utils

from .constants import (
    DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
    DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE,
    DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER,
    DEFAULT_INTEGRATOR_METHOD,
    DEFAULT_INTEGRATOR_STEP_SIZE_S,
    DEFAULT_SATELLITE_DRAG_COEFFICIENT,
    DEFAULT_SATELLITE_MASS_KG,
    DEFAULT_SATELLITE_NAME,
    DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT,
    DEFAULT_SIMULATION_DURATION_S,
    INTEGRATOR_METHOD_DESCRIPTIONS,
    SUPPORTED_INTEGRATOR_METHODS,
)


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
    match: re.Match[str] | None = re.fullmatch(
        r"\s*([0-9]+)\s*[xX]\s*([0-9]+)\s*", value
    )
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
        raise argparse.ArgumentTypeError(
            "earth gravity order must be less than or equal to degree"
        )

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
        raise argparse.ArgumentTypeError(
            "drag area must be a valid number in m²"
        ) from exc

    if drag_area_m2 <= 0.0:
        raise argparse.ArgumentTypeError("drag area must be a positive value in m²")

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
        raise argparse.ArgumentTypeError(
            "drag coefficient must be a valid number"
        ) from exc

    if drag_coefficient <= 0.0:
        raise argparse.ArgumentTypeError("drag coefficient must be a positive value")

    return drag_coefficient


def parse_arguments() -> argparse.Namespace:
    """Create the command-line argument parser for this script.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments for all supported CLI options.
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
        type=time_utils.parse_duration_to_seconds,
        metavar="<value[s|m|h|d]>",
        default=DEFAULT_SIMULATION_DURATION_S,
        help=(
            "Simulation duration (default: 1d). "
            "Use -d/--duration, e.g. -d 90 (90 seconds), --duration 90s, -d 2m, --duration 1.5h, -d 1d."
        ),
    )
    parser.add_argument(
        "--oem",
        metavar="<file|->",
        default="-",
        help=(
            "Write propagated state history as OEM state-vector lines "
            "(UTC_ISO x y z vx vy vz, km and km/s). "
            "Use '-' to write to stdout (default)."
        ),
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Write only OEM state-vector data without the OEM header or metadata.",
    )
    parser.add_argument(
        "--dep-vars",
        metavar="<file>",
        default=None,
        help=(
            "Write dependent variables to a CSV file. "
            "If omitted, dependent variables are not written."
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
        default=DEFAULT_INTEGRATOR_STEP_SIZE_S,
        help=(
            "Integrator step sizes in seconds as a single comma-separated token. "
            "Provide either one value for fixed-step size (for example, 10) "
            "or two values for variable-step size as <initial_and_minimum_step>,<maximum_step> "
            "(for example, 0.001,1000), "
            "or three values for variable-step size in this order: "
            "<initial_step>,<minimum_step>,<maximum_step> "
            "(for example, 30,0.001,1000). "
            f"(default: {DEFAULT_INTEGRATOR_STEP_SIZE_S})."
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
        metavar="<m²>",
        default=DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
        help=(
            "Drag area / average projection area of the propagated satellite in m² "
            f"(default: {DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2})."
        ),
    )

    # Solar radiation pressure
    parser.add_argument(
        "--srp",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help="Enable or disable solar radiation pressure acceleration (default: on).",
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
        help="Enable or disable aerodynamic drag acceleration (default: on).",
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
        help="Enable or disable Moon point-mass gravity perturbation (default: on).",
    )
    parser.add_argument(
        "--sun-gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help="Enable or disable Sun point-mass gravity perturbation (default: on).",
    )
    parser.add_argument(
        "--venus-gravity",
        dest="venus_gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help="Enable or disable Venus point-mass gravity perturbation (default: on).",
    )
    parser.add_argument(
        "--mars-gravity",
        dest="mars_gravity",
        type=parse_bool_flag,
        metavar="<on|off>",
        default=True,
        help="Enable or disable Mars point-mass gravity perturbation (default: on).",
    )
    return parser.parse_args()
