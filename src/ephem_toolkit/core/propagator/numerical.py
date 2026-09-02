"""Numerical propagator wrapping TudatPy's translational dynamics simulator.

Provides:
- :class:`NumericalPropagatorConfig` - force-model and integrator configuration
- :class:`NumericalInitialState` - Cartesian initial state paired with epoch
- :class:`NumericalPropagator` - perturbed numerical propagator
- Engine functions: :func:`load_spice_kernels`, :func:`create_environment_and_bodies`,
  :func:`create_acceleration_models`, :func:`create_dependent_variables_to_save`,
  :func:`create_translational_propagator_settings`, :func:`run_numerical_propagation`

Requires tudatpy.

References:
    https://docs.tudat.space/en/latest/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from typing_extensions import override

from .base import Propagator
from .. import spice_utils

if TYPE_CHECKING:
    from typing import Any

# ===================================================================
# Engine constants (moved from propagate_orbit/constants.py)
# ===================================================================

DEFAULT_BODIES_TO_CREATE: list[str] = ["Sun", "Earth"]
"""Default list of celestial bodies always included in the environment."""

DEFAULT_GLOBAL_FRAME_ORIGIN: str = "Earth"
"""Default global frame origin for the Tudat environment."""

DEFAULT_GLOBAL_FRAME_ORIENTATION: str = "J2000"
"""Default global frame orientation for the Tudat environment."""

INTEGRATOR_METHOD_DESCRIPTIONS: dict[str, str] = {
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
"""Mapping of integrator method identifiers to human-readable descriptions."""

SUPPORTED_INTEGRATOR_METHODS: tuple[str, ...] = tuple(INTEGRATOR_METHOD_DESCRIPTIONS)
"""Tuple of all supported integrator method identifier strings."""

DEFAULT_INTEGRATOR_METHOD: str = "rkdp_87"
"""Default numerical integrator method (Dormand-Prince 8(7))."""


# ===================================================================
# Data types
# ===================================================================


@dataclass(frozen=True)
class NumericalPropagatorConfig:
    """Force-model and integrator settings for numerical propagation.

    This is model configuration — passed to ``NumericalPropagator.__init__``,
    not to ``set_initial_state``.
    """

    satellite_name: str
    """Name of the propagated vehicle body added to the Tudat environment."""
    satellite_mass_kg: float
    """Spacecraft mass (kg) used by dynamics propagation."""

    integrator_method: str
    """Numerical integrator method identifier (e.g. ``'rkdp_87'``)."""
    integrator_step_size_values_s: tuple[float, ...]
    """Step-size input (s): one value = fixed step, three values (initial, min, max) = variable step."""

    earth_spherical_harmonic_gravity_degree: int
    """Degree for Earth's spherical harmonic gravity field."""
    earth_spherical_harmonic_gravity_order: int
    """Order for Earth's spherical harmonic gravity field."""

    satellite_drag_area_m2: float
    """Effective drag/reference area (m²) for aerodynamic drag and SRP cannonball model."""

    is_srp_on: bool
    """Whether solar radiation pressure acceleration is enabled."""
    srp_coefficient: float
    """Dimensionless solar radiation pressure coefficient (Cr)."""

    is_earth_drag_on: bool
    """Whether aerodynamic drag from Earth's atmosphere is enabled."""
    satellite_drag_coefficient: float
    """Dimensionless aerodynamic drag coefficient (Cd)."""

    is_moon_gravity_on: bool
    """Whether Moon point-mass gravity perturbation is enabled."""
    is_sun_gravity_on: bool
    """Whether Sun point-mass gravity perturbation is enabled."""
    is_venus_gravity_on: bool
    """Whether Venus point-mass gravity perturbation is enabled."""
    is_mars_gravity_on: bool
    """Whether Mars point-mass gravity perturbation is enabled."""


@dataclass(frozen=True)
class NumericalInitialState:
    """Cartesian initial state paired with its epoch.

    Passed to :meth:`NumericalPropagator.set_initial_state`.
    """

    state_m_m_s: np.ndarray
    """Cartesian state vector [x, y, z, vx, vy, vz] in SI units (m, m/s)."""
    epoch_s: float
    """Epoch at which :attr:`state_m_m_s` is defined (TT, s since J2000 TT)."""


# ===================================================================
# Engine functions (moved verbatim from propagate_orbit/tudat_setup.py,
# updated to accept NumericalPropagatorConfig + NumericalInitialState)
# ===================================================================


def load_spice_kernels() -> None:
    """Load required SPICE kernels for propagation support."""
    spice_kernel_files = [
        "naif0012.tls",
        "pck00011.tpc",
        "gm_de431.tpc",
        "earth_200101_990825_predict.bpc",
        "tudat_merged_spk_kernel.bsp",
    ]
    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


def create_environment_and_bodies(config: NumericalPropagatorConfig) -> Any:
    """Create environment settings, add spacecraft interfaces, and build bodies.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.

    Returns
    -------
    object
        Tudat system-of-bodies object.
    """
    from tudatpy.dynamics import environment_setup

    bodies_to_create = list(DEFAULT_BODIES_TO_CREATE)
    if config.is_moon_gravity_on:
        bodies_to_create.append("Moon")
    if config.is_mars_gravity_on:
        bodies_to_create.append("Mars")
    if config.is_venus_gravity_on:
        bodies_to_create.append("Venus")

    body_settings = environment_setup.get_default_body_settings(
        bodies_to_create,
        DEFAULT_GLOBAL_FRAME_ORIGIN,
        DEFAULT_GLOBAL_FRAME_ORIENTATION,
    )

    body_settings.add_empty_settings(config.satellite_name)

    if config.is_srp_on:
        occulting_bodies_dict = {"Sun": ["Earth"]}
        vehicle_target_settings = (
            environment_setup.radiation_pressure.cannonball_radiation_target(
                config.satellite_drag_area_m2,
                config.srp_coefficient,
                occulting_bodies_dict,
            )
        )
        body_settings.get(config.satellite_name).radiation_pressure_target_settings = (
            vehicle_target_settings
        )

    if config.is_earth_drag_on:
        aero_coefficient_settings = environment_setup.aerodynamic_coefficients.constant(
            config.satellite_drag_area_m2,
            [config.satellite_drag_coefficient, 0.0, 0.0],
        )
        body_settings.get(config.satellite_name).aerodynamic_coefficient_settings = (
            aero_coefficient_settings
        )

    bodies = environment_setup.create_system_of_bodies(body_settings)
    bodies.get(config.satellite_name).mass = config.satellite_mass_kg
    return bodies


def create_acceleration_models(
    config: NumericalPropagatorConfig,
    bodies: Any,
    bodies_to_propagate: list[str],
    central_bodies: list[str],
) -> Any:
    """Create acceleration models for the propagated satellite.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.
    bodies : object
        Tudat system-of-bodies object.
    bodies_to_propagate : list[str]
        Bodies whose translational states are propagated.
    central_bodies : list[str]
        Central bodies for translational dynamics.

    Returns
    -------
    object
        Tudat acceleration-model map.
    """
    from tudatpy.dynamics import propagation_setup

    satellite_acceleration_settings: dict[str, list[Any]] = {}

    sun_accelerations: list[Any] = []
    if config.is_srp_on:
        sun_accelerations.insert(0, propagation_setup.acceleration.radiation_pressure())
    if config.is_sun_gravity_on:
        sun_accelerations.append(propagation_setup.acceleration.point_mass_gravity())
    if sun_accelerations:
        satellite_acceleration_settings["Sun"] = sun_accelerations

    earth_accelerations: list[Any] = [
        propagation_setup.acceleration.spherical_harmonic_gravity(
            config.earth_spherical_harmonic_gravity_degree,
            config.earth_spherical_harmonic_gravity_order,
        ),
    ]
    if config.is_earth_drag_on:
        earth_accelerations.append(propagation_setup.acceleration.aerodynamic())
    satellite_acceleration_settings["Earth"] = earth_accelerations

    if config.is_moon_gravity_on:
        satellite_acceleration_settings["Moon"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]
    if config.is_venus_gravity_on:
        satellite_acceleration_settings["Venus"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]
    if config.is_mars_gravity_on:
        satellite_acceleration_settings["Mars"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    acceleration_settings = {config.satellite_name: satellite_acceleration_settings}

    return propagation_setup.create_acceleration_models(
        bodies, acceleration_settings, bodies_to_propagate, central_bodies
    )


def create_dependent_variables_to_save(
    config: NumericalPropagatorConfig,
) -> list[Any]:
    """Create dependent-variable save settings for propagation.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.

    Returns
    -------
    list[Any]
        Dependent-variable save settings.
    """
    from tudatpy.dynamics import propagation_setup
    from tudatpy.dynamics.propagation_setup import dependent_variable

    dep_vars: list[Any] = [
        dependent_variable.total_acceleration(config.satellite_name),
        dependent_variable.keplerian_state(config.satellite_name, "Earth"),
        dependent_variable.geodetic_latitude(config.satellite_name, "Earth"),
        dependent_variable.longitude(config.satellite_name, "Earth"),
        dependent_variable.central_body_fixed_cartesian_position(
            config.satellite_name, "Earth"
        ),
        dependent_variable.relative_position(config.satellite_name, "Earth"),
        dependent_variable.single_acceleration_norm(
            propagation_setup.acceleration.spherical_harmonic_gravity_type,
            config.satellite_name,
            "Earth",
        ),
    ]

    if config.is_moon_gravity_on:
        dep_vars.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                config.satellite_name,
                "Moon",
            )
        )
    if config.is_sun_gravity_on:
        dep_vars.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                config.satellite_name,
                "Sun",
            )
        )
    if config.is_srp_on:
        dep_vars.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.radiation_pressure_type,
                config.satellite_name,
                "Sun",
            )
        )
    if config.is_earth_drag_on:
        dep_vars.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.aerodynamic_type,
                config.satellite_name,
                "Earth",
            )
        )
    if config.is_venus_gravity_on:
        dep_vars.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                config.satellite_name,
                "Venus",
            )
        )
    if config.is_mars_gravity_on:
        dep_vars.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                config.satellite_name,
                "Mars",
            )
        )

    return dep_vars


def create_translational_propagator_settings(
    config: NumericalPropagatorConfig,
    initial_state: NumericalInitialState,
    target_epoch_s: float,
    central_bodies: list[str],
    acceleration_models: Any,
    bodies_to_propagate: list[str],
    dependent_variables_to_save: list[Any],
) -> Any:
    """Create translational propagator settings.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.
    initial_state : NumericalInitialState
        Initial Cartesian state and epoch.
    target_epoch_s : float
        Propagation end epoch (TT, s since J2000 TT).
    central_bodies : list[str]
        Central bodies for translational dynamics.
    acceleration_models : object
        Acceleration model map.
    bodies_to_propagate : list[str]
        Bodies whose translational states are propagated.
    dependent_variables_to_save : list[Any]
        Dependent-variable save settings.

    Returns
    -------
    object
        Tudat translational propagator settings object.
    """
    from tudatpy.dynamics import propagation_setup

    try:
        coefficient_set = getattr(
            propagation_setup.integrator.CoefficientSets,
            config.integrator_method,
        )
    except AttributeError as exc:
        raise ValueError(
            f"Unsupported integrator method '{config.integrator_method}'. "
            f"Supported methods are: {', '.join(SUPPORTED_INTEGRATOR_METHODS)}. "
            f"Default is {DEFAULT_INTEGRATOR_METHOD}."
        ) from exc

    if len(config.integrator_step_size_values_s) == 1:
        integrator_settings = propagation_setup.integrator.runge_kutta_fixed_step(
            config.integrator_step_size_values_s[0],
            coefficient_set=coefficient_set,
        )
    else:
        initial_step_s, minimum_step_s, maximum_step_s = (
            config.integrator_step_size_values_s
        )
        step_size_validation_settings = (
            propagation_setup.integrator.step_size_validation(
                minimum_step_s, maximum_step_s
            )
        )
        step_size_control_settings = (
            propagation_setup.integrator.step_size_control_elementwise_scalar_tolerance(
                1.0e-10, 1.0e-10
            )
        )
        integrator_settings = propagation_setup.integrator.runge_kutta_variable_step(
            initial_time_step=initial_step_s,
            coefficient_set=coefficient_set,
            step_size_validation_settings=step_size_validation_settings,
            step_size_control_settings=step_size_control_settings,
        )

    termination_condition = propagation_setup.propagator.time_termination(
        target_epoch_s
    )

    return propagation_setup.propagator.translational(
        central_bodies,
        acceleration_models,
        bodies_to_propagate,
        initial_state.state_m_m_s,
        initial_state.epoch_s,
        integrator_settings,
        termination_condition,
        output_variables=dependent_variables_to_save,
    )


def run_numerical_propagation(
    config: NumericalPropagatorConfig,
    initial_state: NumericalInitialState,
    target_epoch_s: float,
) -> tuple[dict[float, np.ndarray], Any, list[Any]]:
    """Run numerical propagation from initial_state to target_epoch_s.

    Performs no file I/O. Raises exceptions rather than calling sys.exit.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.
    initial_state : NumericalInitialState
        Initial Cartesian state and epoch.
    target_epoch_s : float
        Propagation end epoch (TT, s since J2000 TT).

    Returns
    -------
    tuple[dict[float, np.ndarray], Any, list[Any]]
        ``(state_history, dep_var_dict, dependent_variables_to_save)`` where
        ``state_history`` maps TT epoch (s) to Cartesian state (6,),
        ``dep_var_dict`` is the Tudat dependent-variable dictionary, and
        ``dependent_variables_to_save`` is the list of save settings (needed
        for downstream CSV writing).
    """
    from tudatpy.dynamics import propagation, simulator

    bodies = create_environment_and_bodies(config)
    bodies_to_propagate = [config.satellite_name]
    central_bodies = ["Earth"]

    acceleration_models = create_acceleration_models(
        config, bodies, bodies_to_propagate, central_bodies
    )
    dependent_variables_to_save = create_dependent_variables_to_save(config)
    propagator_settings = create_translational_propagator_settings(
        config,
        initial_state,
        target_epoch_s,
        central_bodies,
        acceleration_models,
        bodies_to_propagate,
        dependent_variables_to_save,
    )

    dynamics_simulator = simulator.create_dynamics_simulator(
        bodies, propagator_settings
    )
    state_history: dict[float, np.ndarray] = (
        dynamics_simulator.propagation_results.state_history
    )
    dep_var_dict = propagation.create_dependent_variable_dictionary(dynamics_simulator)

    return state_history, dep_var_dict, dependent_variables_to_save


# ===================================================================
# NumericalPropagator
# ===================================================================


def _interpolate_state(
    state_history: dict[float, np.ndarray], target_epoch_s: float
) -> np.ndarray:
    """Return the state at target_epoch_s via nearest-neighbour lookup.

    Parameters
    ----------
    state_history : dict[float, np.ndarray]
        Mapping of TT epoch (s) to Cartesian state (6,).
    target_epoch_s : float
        Target epoch (TT, s since J2000 TT).

    Returns
    -------
    np.ndarray
        Cartesian state [x, y, z, vx, vy, vz] in m and m/s.
    """
    epochs = np.array(sorted(state_history.keys()))
    idx = int(np.argmin(np.abs(epochs - target_epoch_s)))
    return np.asarray(state_history[epochs[idx]], dtype=float)


class NumericalPropagator(Propagator[NumericalInitialState]):
    """Perturbed numerical propagator (Tudat translational dynamics).

    Wraps TudatPy's ``simulator.create_dynamics_simulator``. Requires tudatpy.

    Model configuration (force model, integrator) is fixed at construction.
    Initial state (epoch + Cartesian state) is set via :meth:`set_initial_state`.

    Each call to :meth:`propagate_to` re-runs the integrator from the initial
    state to the target epoch. Caching is a future optimization.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator settings.
    initial_state : NumericalInitialState
        Initial Cartesian state and epoch.
    """

    def __init__(
        self,
        config: NumericalPropagatorConfig,
        initial_state: NumericalInitialState,
    ) -> None:
        self._config = config
        super().__init__()
        self.set_initial_state(initial_state)

    @override
    def set_initial_state(self, initial_state: NumericalInitialState) -> None:
        """Set initial state.

        Parameters
        ----------
        initial_state : NumericalInitialState
            Initial Cartesian state and epoch.
        """
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    @override
    def get_initial_epoch_s(self) -> float:
        """Return the initial epoch (TT, s since J2000 TT).

        Returns
        -------
        float
            Fixed initial epoch.
        """
        return self._initial_state.epoch_s

    @override
    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Run integrator and return state at target_epoch_s.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch (TT, s since J2000 TT).

        Returns
        -------
        np.ndarray
            Cartesian state [x, y, z, vx, vy, vz] in m and m/s.
        """
        state_history, _, _ = run_numerical_propagation(
            self._config, self._initial_state, target_epoch_s
        )
        return _interpolate_state(state_history, target_epoch_s)

    @override
    def _propagate_trajectory_impl(
        self, from_epoch_s: float, to_epoch_s: float
    ) -> list[tuple[float, np.ndarray]]:
        """Run integrator once and return all samples in [from_epoch_s, to_epoch_s].

        Overrides the base default to avoid re-running the integrator per sample.

        Parameters
        ----------
        from_epoch_s : float
            Start of the trajectory window (TT, s since J2000 TT).
        to_epoch_s : float
            End of the trajectory window (TT, s since J2000 TT).

        Returns
        -------
        list[tuple[float, np.ndarray]]
            List of (epoch_s, state) tuples.
        """
        state_history, _, _ = run_numerical_propagation(
            self._config, self._initial_state, to_epoch_s
        )
        return [
            (t, np.asarray(s, dtype=float))
            for t, s in sorted(state_history.items())
            if t >= from_epoch_s
        ]
