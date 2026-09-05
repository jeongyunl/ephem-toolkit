#!/usr/bin/env python3
"""Fit OEM state vectors and write an OPM with the selected fit representation.

Algorithm overview (--kepler mode):
  - The epoch position r₀ is fixed to the first OEM position.
  - The epoch velocity v₀ is estimated via a Gauss-Newton least-squares
    minimizer that minimizes position residuals ‖r_OEM(tᵢ) - r_Kepler(tᵢ)‖
    over the fit arc.
  - A numerical (forward-difference) Jacobian ∂residuals/∂v₀ is computed
    at each iteration.
  - Levenberg-Marquardt-style diagonal damping stabilizes the normal
    equations, and a backtracking line search with physical feasibility
    guards (eccentricity < 1, semi-major axis > 6000 km) ensures
    convergence to a physically meaningful orbit.

Usage:
    oem-to-opm <input_oem|-> -o <output_opm|->
"""

from __future__ import annotations

import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn, TextIO

import numpy as np

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.propagator.kepler as kepler
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.core.provenance as provenance

from .oem_to_opm_cli import OemToOpmArgs
from .oem_to_opm_cli import build_arg_parser, parse_arguments

from . import fit_common
from . import fit_numerical
from . import fit_osculating_kepler

# ===================================================================
# Reporting
# ===================================================================


def report_results(
    output_text: str,
    dest: TextIO | str | Path,
    verbose: bool = False,
) -> None:
    """Report results to stdout, file, or stderr.

    Handles all output operations including writing to files or stdout,
    and optional verbose status messages to stderr.

    Parameters
    ----------
    output_text : str
        Formatted output text to write.
    dest : TextIO | str | Path
        Output destination. Use "-" for stdout, a file path, or a TextIO stream.
    verbose : bool
        If True, print status messages to stderr.
    """
    if dest == "-":
        print(output_text)
    elif isinstance(dest, (str, Path)):
        output_path = Path(dest)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    else:
        # Handle TextIO stream
        dest.write(output_text)


def report_error(message: str, exit_code: int = 1) -> NoReturn:
    """Report an error message to stderr and exit.

    Parameters
    ----------
    message : str
        Error message to display.
    exit_code : int
        Exit code (default: 1).

    Raises
    ------
    SystemExit
        Always raised with the supplied exit code.
    """
    print(message, file=sys.stderr)
    sys.exit(exit_code)


def verbose_message(enabled: bool, message: str) -> None:
    """Write a conversion progress message when verbose mode is enabled."""
    if enabled:
        print(f"[oem-to-opm] {message}", file=sys.stderr)


def debug_message(enabled: bool, message: str) -> None:
    """Write a detailed debug message when debug mode is enabled."""
    if enabled:
        print(f"[oem-to-opm:debug] {message}", file=sys.stderr)


def build_opm(
    epoch: datetime,
    initial_state_m_m_s: np.ndarray,
    keplerian_elements: np.ndarray | None,
    *,
    object_name: str,
    object_id: str,
    center_name: str,
    ref_frame: str,
    time_system: str,
    mu_m3_s2: float,
) -> opm.CcsdsOpm:
    """Build an OPM containing the initial state and optional fitted elements.

    Parameters
    ----------
    epoch : datetime
        Epoch of the initial state.
    initial_state_m_m_s : np.ndarray
        Initial Cartesian state in meters and meters per second.
    keplerian_elements : np.ndarray | None
        Fitted Keplerian elements in meters and radians, or ``None`` for a
        numerical Cartesian-only fit.
    object_name : str
        Spacecraft name for OPM metadata.
    object_id : str
        International designator for OPM metadata.
    center_name : str
        Central body name for OPM metadata.
    ref_frame : str
        Reference frame for OPM metadata.
    time_system : str
        Time system for OPM metadata.
    mu_m3_s2 : float
        Gravitational parameter in m³/s².

    Returns
    -------
    opm.CcsdsOpm
        OPM containing the initial state and, for two-body fits, fitted elements.
    """
    epoch_str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)
    return opm.CcsdsOpm(
        header=opm.OpmHeader(
            creation_date=time_utils.datetime_to_iso8601(
                datetime.now(timezone.utc), fractional_second_places=3
            ),
            originator="oem_to_opm",
        ),
        metadata={
            "OBJECT_NAME": object_name,
            "OBJECT_ID": object_id,
            "CENTER_NAME": center_name,
            "REF_FRAME": ref_frame,
            "TIME_SYSTEM": time_system,
        },
        state_vector=opm.OpmStateVector(
            epoch=epoch_str,
            x=float(initial_state_m_m_s[0] / 1000.0),
            y=float(initial_state_m_m_s[1] / 1000.0),
            z=float(initial_state_m_m_s[2] / 1000.0),
            x_dot=float(initial_state_m_m_s[3] / 1000.0),
            y_dot=float(initial_state_m_m_s[4] / 1000.0),
            z_dot=float(initial_state_m_m_s[5] / 1000.0),
        ),
        keplerian_elements=(opm.OpmKeplerianElements(
            semi_major_axis=float(
                keplerian_elements[kepler.SEMI_MAJOR_AXIS_INDEX] / 1000.0
            ),
            eccentricity=float(keplerian_elements[kepler.ECCENTRICITY_INDEX]),
            inclination=float(np.degrees(keplerian_elements[kepler.INCLINATION_INDEX])),
            ra_of_asc_node=float(np.degrees(keplerian_elements[kepler.RAAN_INDEX])),
            arg_of_pericenter=float(
                np.degrees(keplerian_elements[kepler.ARGUMENT_OF_PERIAPSIS_INDEX])
            ),
            true_anomaly=float(
                np.degrees(keplerian_elements[kepler.TRUE_ANOMALY_INDEX])
            ),
            gm=float(mu_m3_s2 / 1.0e9),
        ) if keplerian_elements is not None else None),
    )


# ===================================================================
# Main
# ===================================================================


def main(argv=None) -> None:
    """Parse CLI arguments and dispatch to the appropriate conversion mode."""
    cli_parser = build_arg_parser()
    cli_args: OemToOpmArgs = parse_arguments(cli_parser, argv)
    show_progress = cli_args.verbose or cli_args.debug
    debug_message(cli_args.debug, f"parsed arguments: {vars(cli_args)}")

    # Determine input source: file path or stdin (piped input)
    read_from_stdin: bool = cli_args.input_oem == "-"
    verbose_message(show_progress, f"reading OEM input: {cli_args.input_oem}")

    # Read and parse CCSDS OEM ephemeris data
    if read_from_stdin:
        oem_data = oem.CcsdsOem.read(sys.stdin)
    else:
        oem_path = Path(cli_args.input_oem)
        if not oem_path.exists():
            report_error(f"Error: Input file not found: {cli_args.input_oem}")
        oem_data = oem.CcsdsOem.read(oem_path)

    states: list[tuple[float, np.ndarray]] = oem_data.states
    verbose_message(show_progress, f"loaded {len(states)} OEM state vectors")
    debug_message(
        cli_args.debug,
        f"OEM metadata: object={oem_data.meta.object_name!r}, frame={oem_data.meta.ref_frame!r}, time_system={oem_data.meta.time_system!r}",
    )

    if len(states) < 2:
        report_error("Error: At least 2 state vectors required for fitting.")

    fit_span_s: float = cli_args.fit_span.total_seconds()
    try:
        source_model, source_report = provenance.resolve_source_model(
            cli_args.source_model, cli_args.source_report
        )
    except ValueError as error:
        report_error(f"Error: {error}")
    if cli_args.no_fit_report and cli_args.fit_report:
        report_error("Error: --fit-report and --no-fit-report cannot be used together")
    fit_report = None if cli_args.no_fit_report else (
        cli_args.fit_report or provenance.default_fit_report_path(
            cli_args.input_oem, cli_args.output_opm
        )
    )
    verbose_message(
        show_progress,
        f"fit model={cli_args.fit_model}, span={fit_span_s:g}s, report={'disabled' if fit_report is None else fit_report}",
    )

    # Determine object name: use --object-name if provided, otherwise use OEM metadata
    object_name: str = (
        cli_args.object_name
        if cli_args.object_name
        else (oem_data.meta.object_name or "OBJECT")
    )

    # Determine object_id: use --object-id if provided, otherwise use OEM metadata
    if cli_args.object_id:
        object_id: str = cli_args.object_id
    else:
        object_id: str = oem_data.meta.object_id or "UNKNOWN"

    # Run the selected fit (the numerical path uses the shared Tudat adapter).
    fitted_elements: np.ndarray | None = None
    fitted_state: np.ndarray | None = None
    diagnostics: object
    fit_transformation = "two-body fit"
    fit_target_model = "two-body-kepler"
    fit_configuration: dict[str, object] = {
        "fit_span_s": fit_span_s,
        "mu_m3_s2": cli_args.mu_m3_s2,
        "source_frame": oem_data.meta.ref_frame or "unknown",
        "source_time_system": oem_data.meta.time_system or "unknown",
        "source_comments": list(getattr(oem_data.meta, "comments", [])),
        "source_report": source_report,
    }
    try:
        if cli_args.fit_model == "numerical":
            verbose_message(show_progress, "building numerical propagator configuration")
            fit_config = fit_numerical.config_from_fit_options(cli_args)
            fit_numerical.validate_numerical_fit(states, fit_config)
            verbose_message(show_progress, "numerical fit configuration validated")
            debug_message(cli_args.debug, f"numerical fit configuration: {fit_config.to_report_dict()}")
            propagator_config = fit_config.to_propagator_config(
                satellite_name=object_name or "FIT_TARGET"
            )
            verbose_message(show_progress, "numerical propagator configuration ready")
            propagator_factory = fit_numerical.make_numerical_propagator_factory(
                propagator_config, states[0][0]
            )
            propagation_callback = fit_numerical.make_propagation_callback(
                propagator_factory, states[0][0]
            )
            trajectory_callback = fit_numerical.make_numerical_trajectory_callback(
                propagator_factory, states[0][0], fit_config.fit_span_s
            )
            verbose_message(
                show_progress,
                "starting numerical fit; each residual evaluation propagates the sampled OEM arc",
            )
            iteration_callback = None
            if cli_args.debug:
                iteration_callback = lambda iteration, residual, step, updated, converged: debug_message(
                    True,
                    f"fit try {iteration}: residual={residual:g}, velocity_step={step:g}, updated_residual={updated:g}, converged={converged}",
                )
                _, initial_diagnostics = fit_numerical.build_weighted_residuals(
                    propagation_callback,
                    states[0][1],
                    states,
                    fit_config,
                    propagate_trajectory=trajectory_callback,
                )
                debug_message(
                    True,
                    f"initial OEM state position_rms={initial_diagnostics.position_rms_m:g}m",
                )
            numerical_result = fit_numerical.optimize_initial_state(
                propagation_callback,
                states[0][1],
                states,
                fit_config,
                iteration_callback=iteration_callback,
                propagate_trajectory=trajectory_callback,
                max_iterations=fit_config.max_iterations,
                stagnation_tries=fit_config.stagnation_tries,
            )
            verbose_message(
                show_progress,
                f"numerical fit complete: iterations={numerical_result.iterations}, converged={numerical_result.converged}, position_rms={numerical_result.diagnostics.position_rms_m:g}m",
            )
            debug_message(
                cli_args.debug,
                f"selected best fit position_rms={numerical_result.diagnostics.position_rms_m:g}m",
            )
            fitted_state = numerical_result.initial_state
            initial_position_rms_m = (
                numerical_result.initial_position_rms_m
                if numerical_result.initial_position_rms_m is not None
                else numerical_result.diagnostics.position_rms_m
            )
            diagnostics = fit_common.FitDiagnostics(
                rms_position_m=numerical_result.diagnostics.position_rms_m,
                iterations=numerical_result.iterations,
                n_records=numerical_result.diagnostics.n_records,
                span_s=fit_span_s,
                epoch_pos_delta_m=float(np.linalg.norm(fitted_state[:3] - states[0][1][:3])),
                epoch_vel_delta_m_s=float(np.linalg.norm(fitted_state[3:] - states[0][1][3:])),
                fit_method="numerical",
                initial_position_rms_m=initial_position_rms_m,
            )
            fit_transformation = "numerical fit"
            fit_target_model = "numerical-propagator"
            fit_configuration = {
                **fit_config.to_report_dict(),
                "mu_m3_s2": cli_args.mu_m3_s2,
                "source_frame": oem_data.meta.ref_frame or "unknown",
                "source_time_system": oem_data.meta.time_system or "unknown",
                "source_comments": list(getattr(oem_data.meta, "comments", [])),
                "source_report": source_report,
            }
        else:
            verbose_message(show_progress, "running two-body fit")
            fitted_elements, diagnostics = fit_osculating_kepler.fit_osculating_kepler(
                states,
                fit_span_s,
                cli_args.mu_m3_s2,
            )
    except Exception as error:
        report_error(f"Error fitting {cli_args.fit_model} model: {error}")

    # The numerical fit already evaluates the target propagator at its sampled
    # epochs; the legacy comparison table remains specific to the Kepler fit.
    comparison: list[fit_common.PropagationComparison] = []
    if cli_args.fit_model == "numerical":
        comparison = fit_numerical.compute_numerical_propagation_comparison(
            trajectory_callback, fitted_state, states, fit_span_s
        )
    else:
        comparison = fit_osculating_kepler.compute_kepler_propagation_comparison(
            fitted_elements, states, cli_args.mu_m3_s2, fit_span_s, interval_s=600.0
        )

    # Format and report output
    first_epoch: datetime = time_utils.tt_s_to_datetime(states[0][0])
    if cli_args.fit_model == "numerical":
        output_text = fit_numerical.format_numerical_output(
            first_epoch, diagnostics, states[0][1], fitted_state, comparison
        )
    else:
        output_text = fit_osculating_kepler.format_kepler_output(
            first_epoch, fitted_elements, diagnostics, comparison,
            fit_method=cli_args.fit_model,
        )
    verbose_message(show_progress, "serializing OPM output")
    if cli_args.fit_model == "two-body":
        debug_message(cli_args.debug, f"fitted Keplerian elements: {fitted_elements.tolist()}")

    # Report results to stderr in verbose mode when output is stdout
    if show_progress and cli_args.output_opm == "-":
        print(output_text, file=sys.stderr)
    elif show_progress:
        report_results(output_text, "-", cli_args.verbose)

    # Save the fitted Cartesian state. Keplerian elements are only part of the
    # two-body output; numerical fitting is intentionally Cartesian-only.
    if cli_args.output_opm:
        try:
            output_initial_state = (
                fitted_state if cli_args.fit_model == "numerical" else states[0][1]
            )
            opm_obj = build_opm(
                first_epoch,
                output_initial_state,
                fitted_elements,
                object_name=object_name,
                object_id=object_id,
                center_name=oem_data.meta.center_name or "EARTH",
                ref_frame=oem_data.meta.ref_frame or "ICRF",
                time_system=oem_data.meta.time_system or "UTC",
                mu_m3_s2=cli_args.mu_m3_s2,
            )
            opm_obj.header.comments.extend([
                provenance.provenance_comment(source=f"OEM/{source_model}", transformation=fit_transformation, target_model=fit_target_model),
                provenance.fit_comment(
                    span_s=provenance.diagnostic_value(diagnostics, "span_s", fit_span_s),
                    samples=provenance.diagnostic_value(diagnostics, "n_records", len(states)),
                    position_rms=provenance.diagnostic_value(
                        diagnostics,
                        "rms_position_m",
                        provenance.diagnostic_value(diagnostics, "position_rms_m", 0.0),
                    ),
                    velocity_rms=provenance.diagnostic_value(
                        diagnostics, "velocity_rms_m_s"
                    ),
                ),
            ])
            # Output to stdout if dest is "-", otherwise to file
            if cli_args.output_opm == "-":
                opm_obj.to_file(sys.stdout)
            else:
                opm_obj.to_file(cli_args.output_opm)
                if show_progress:
                    print(
                        f"OPM file written to: {cli_args.output_opm}",
                        file=sys.stderr,
                    )
            if fit_report:
                provenance.write_fit_report(
                    fit_report,
                    provenance={"source": f"OEM/{source_model}", "transformation": fit_transformation, "target_model": fit_target_model},
                    diagnostics=diagnostics,
                    configuration=fit_configuration,
                    source_report=source_report,
                    residuals=provenance.comparison_residuals(comparison),
                )
                verbose_message(show_progress, f"fit report written to: {fit_report}")
        except Exception as error:
            report_error(f"Error writing OPM file: {error}")


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
