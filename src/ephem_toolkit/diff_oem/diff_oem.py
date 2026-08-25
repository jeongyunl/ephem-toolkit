#!/usr/bin/env python3
"""Compare corresponding states from two OEM files.

Usage:
    diff-oem <reference_oem.oem> <comparison_oem.oem>
    diff-oem - <comparison_oem.oem>
    diff-oem <reference_oem.oem> -

The utility reports time, position, and velocity differences. Use ``-`` for one
stdin input. Interpolation options compare states at matching epochs.
"""

from __future__ import annotations

import sys
from typing import TextIO

from .comparison import read_states
from .debug import debug_print_time_range, set_debug
from .diff_oem_cli import DiffOemArgs, parse_arguments
from .output import ComparisonOutput
from .pipeline import TransformationPipeline
from .transformation_stages import (
    RotationStage,
    RotationXYStage,
    RotationZStage,
    TimeShiftStage,
    TransformationStage,
)
from .utils import (
    build_comparison_pairs,
    compare_pairs,
    find_overlapping_time_range,
    resolve_time_bound,
)
from ephem_toolkit.core.interpolator import factory


def main() -> None:
    """Main entry point for the state comparison CLI.

    Parses command-line arguments, reads OEM state vectors from files or
    stdin, compares corresponding OEM states, and prints a header followed by
    one tab-separated result row per comparison to stdout.
    Exits with status 1 on error.
    """
    cli_args: DiffOemArgs = parse_arguments()

    # --debug implies --verbose.
    if cli_args.debug:
        cli_args.verbose = True

    # Propagate the debug flag to all submodules.
    if cli_args.debug:
        set_debug(True)

    try:
        # Load OEM files

        reference_source: TextIO | str = (
            sys.stdin if cli_args.reference_oem == "-" else cli_args.reference_oem
        )
        comparison_source: TextIO | str = (
            sys.stdin if cli_args.comparison_oem == "-" else cli_args.comparison_oem
        )
        reference_states = read_states(reference_source)
        comparison_states = read_states(comparison_source)

        # Find overlapping time range between OEM files

        overlapping_time_range = find_overlapping_time_range(
            reference_states, comparison_states
        )
        if cli_args.debug:
            debug_print_time_range(
                "Reference data time range",
                reference_states[0][0],
                reference_states[-1][0],
            )
            debug_print_time_range(
                "Comparison data time range",
                comparison_states[0][0],
                comparison_states[-1][0],
            )
            if overlapping_time_range is None:
                debug_print_time_range("Overlapping time range", None, None)
            else:
                debug_print_time_range(
                    "Overlapping time range", *overlapping_time_range
                )

        # Error if there's no overlap

        if overlapping_time_range is None:
            raise ValueError(
                "Reference and comparison OEM files have no overlapping time period"
            )

        overlap_start, overlap_stop = overlapping_time_range

        # Resolve user requested time range (--start and --stop)

        reference_start_epoch_s: float = reference_states[0][0]
        requested_start: float = (
            overlap_start
            if cli_args.start is None
            else resolve_time_bound(cli_args.start, reference_start_epoch_s)
        )
        requested_stop = (
            overlap_stop
            if cli_args.stop is None
            else resolve_time_bound(cli_args.stop, requested_start)
        )
        if requested_start > requested_stop:
            raise ValueError("--start must be earlier than or equal to --stop")

        if cli_args.debug:
            debug_print_time_range(
                "Requested time range", requested_start, requested_stop
            )

        # Resolve and test comparison time range

        comparison_start = max(overlap_start, requested_start)
        comparison_stop = min(overlap_stop, requested_stop)

        if comparison_start > comparison_stop:
            raise ValueError("--start or --stop is out of overlapping range")

        if cli_args.debug:
            debug_print_time_range(
                "Comparison time range", comparison_start, comparison_stop
            )

        fit_overlap_start = comparison_start
        fit_overlap_stop = comparison_stop

        if cli_args.debug:
            if (
                cli_args.rotate
                or cli_args.rotate_xy
                or cli_args.rotate_z
                or cli_args.time_shift
            ):
                if fit_overlap_start is None or fit_overlap_stop is None:
                    debug_print_time_range("Transformation fitting range", None, None)
                else:
                    debug_print_time_range(
                        "Transformation fitting range",
                        fit_overlap_start,
                        fit_overlap_stop,
                    )
            if cli_args.rotate or cli_args.rotate_xy:
                if fit_overlap_start is None or fit_overlap_stop is None:
                    debug_print_time_range("Rotation fitting range", None, None)
                else:
                    debug_print_time_range(
                        "Rotation fitting range",
                        fit_overlap_start,
                        min(
                            fit_overlap_stop,
                            fit_overlap_start + cli_args.rot_fit_span,
                        ),
                    )

        # Both interpolators are always created.
        reference_interpolator = factory.InterpolatorFactory.create(
            spec=cli_args.interpolate_type,
            dimension=6,
            is_cartesian_state=True,
            verbose=cli_args.verbose,
            context="diff_oem.reference_interpolator",
            data=reference_states,
        )

        comparison_interpolator = factory.InterpolatorFactory.create(
            spec=cli_args.interpolate_type,
            dimension=6,
            is_cartesian_state=True,
            verbose=cli_args.verbose,
            context="diff_oem.comparison_interpolator",
            data=comparison_states,
        )

        def build_pairs(ref_states, cmp_states):
            """Build comparison pairs with current configuration."""
            return build_comparison_pairs(
                ref_states,
                cmp_states,
                comparison_start,
                comparison_stop,
            )

        comparison_pairs = build_pairs(reference_states, comparison_states)

        stages: list[TransformationStage] = []
        stage_sequence: list[str] = list(cli_args.stage_sequence)
        if cli_args.rotate and "rotate" not in stage_sequence:
            stage_sequence.append("rotate")
        if cli_args.rotate_xy and "rotate_xy" not in stage_sequence:
            stage_sequence.append("rotate_xy")
        if cli_args.rotate_z and "rotate_z" not in stage_sequence:
            stage_sequence.append("rotate_z")
        if cli_args.time_shift and "time_shift" not in stage_sequence:
            stage_sequence.append("time_shift")

        for stage_key in stage_sequence:
            if fit_overlap_start is None or fit_overlap_stop is None:
                raise ValueError(
                    "Transformation stages require overlapping reference and "
                    "comparison histories"
                )

            if stage_key == "rotate":
                stages.append(
                    RotationStage(
                        fit_overlap_start,
                        fit_overlap_stop,
                        cli_args.rot_fit_span,
                    )
                )
            elif stage_key == "rotate_xy":
                stages.append(
                    RotationXYStage(
                        fit_overlap_start,
                        fit_overlap_stop,
                        cli_args.rot_fit_span,
                    )
                )
            elif stage_key == "rotate_z":
                stages.append(
                    RotationZStage(
                        fit_overlap_start,
                        fit_overlap_stop,
                        cli_args.rot_fit_span,
                    )
                )
            elif stage_key == "time_shift":
                stages.append(
                    TimeShiftStage(
                        fit_overlap_start,
                        fit_overlap_stop,
                    )
                )

        normal_results = compare_pairs(
            comparison_pairs,
            reference_interpolator,
            comparison_interpolator,
            None,
        )
        if not normal_results:
            return
        ComparisonOutput(
            comparison_results=normal_results,
            reference_interpolator=reference_interpolator,
            comparison_interpolator=comparison_interpolator,
            verbose=cli_args.verbose,
            rtn=cli_args.rtn,
            title="Normal comparison" if stages else None,
        ).print()
        if stages:
            pipeline = TransformationPipeline(
                reference_states=reference_states,
                comparison_states=comparison_states,
                stages=stages,
                build_pairs=build_pairs,
                interpolation_spec=cli_args.interpolate_type,
                debug=cli_args.debug,
            )
            stage_outputs = pipeline.execute(cli_args.verbose)

            for stage_index, (
                stage,
                fit_result,
                transformed_comparison_states,
            ) in enumerate(
                stage_outputs,
                start=1,
            ):
                transformed_comparison_pairs = build_pairs(
                    reference_states,
                    transformed_comparison_states,
                )
                transformed_comparison_interpolator = (
                    factory.InterpolatorFactory.create(
                        spec=cli_args.interpolate_type,
                        dimension=6,
                        is_cartesian_state=True,
                        verbose=cli_args.verbose,
                        context=f"diff_oem.transformed_stage_{stage_index}",
                        data=transformed_comparison_states,
                    )
                )
                transformed_results = compare_pairs(
                    transformed_comparison_pairs,
                    reference_interpolator,
                    transformed_comparison_interpolator,
                    None,
                )
                ComparisonOutput(
                    comparison_results=transformed_results,
                    reference_interpolator=reference_interpolator,
                    comparison_interpolator=transformed_comparison_interpolator,
                    verbose=cli_args.verbose,
                    rtn=cli_args.rtn,
                    title=f"Comparison after stage {stage_index}: {stage.name}",
                    fit_description=stage.describe_fit(fit_result),
                ).print()

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
