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

import argparse
import sys
from typing import TextIO

from .cli import parse_arguments
from .comparison import read_states
from .output import ComparisonOutput
from .pipeline import TransformationPipeline, create_interpolator
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
    print_debug_range,
    resolve_time_bound,
)


def main() -> None:
    """Main entry point for the state comparison CLI.

    Parses command-line arguments, reads OEM state vectors from files or
    stdin, compares corresponding OEM states, and prints a header followed by
    one tab-separated result row per comparison to stdout.
    Exits with status 1 on error.
    """
    args: argparse.Namespace = parse_arguments()

    try:
        reference_source: TextIO | str = (
            sys.stdin if args.reference_oem == "-" else args.reference_oem
        )
        comparison_source: TextIO | str = (
            sys.stdin if args.comparison_oem == "-" else args.comparison_oem
        )
        reference_states = read_states(reference_source)
        comparison_states = read_states(comparison_source)
        reference_oem = reference_states[0]
        has_time_window: bool = args.start is not None or args.stop is not None

        overlapping_time_range = find_overlapping_time_range(
            reference_states, comparison_states
        )
        if args.debug:
            print_debug_range(
                "Reference range", reference_states[0][0], reference_states[-1][0]
            )
            print_debug_range(
                "Comparison range", comparison_states[0][0], comparison_states[-1][0]
            )
            if overlapping_time_range is None:
                print_debug_range("Initial overlap", None, None)
            else:
                print_debug_range("Initial overlap", *overlapping_time_range)

        # Explicit windows are only meaningful when the histories overlap.
        if overlapping_time_range is None and has_time_window:
            if args.debug:
                print_debug_range("Effective range", None, None)
            return

        if overlapping_time_range is not None:
            overlap_start, overlap_stop = overlapping_time_range
        else:
            overlap_start = overlap_stop = None
        fit_overlap_start = overlap_start
        fit_overlap_stop = overlap_stop

        if has_time_window:
            reference_epoch_s: float = reference_states[0][0]
            requested_start: float = (
                overlap_start
                if args.start is None
                else resolve_time_bound(args.start, reference_epoch_s)
            )
            requested_stop: float = (
                overlap_stop
                if args.stop is None
                else resolve_time_bound(args.stop, requested_start)
            )
            if requested_start > requested_stop:
                raise ValueError("--start must be earlier than or equal to --stop")
            overlap_start = max(overlap_start, requested_start)
            overlap_stop = min(overlap_stop, requested_stop)
            if overlap_start > overlap_stop:
                if args.debug:
                    print_debug_range("Effective range", None, None)
                return

            if args.debug:
                print_debug_range("Requested range", requested_start, requested_stop)

        if args.debug:
            print_debug_range("Effective range", overlap_start, overlap_stop)
            if args.rot or args.rot_xy or args.rot_z or args.time_shift:
                if fit_overlap_start is None or fit_overlap_stop is None:
                    print_debug_range("Transformation fitting range", None, None)
                else:
                    print_debug_range(
                        "Transformation fitting range",
                        fit_overlap_start,
                        fit_overlap_stop,
                    )
            if args.rot or args.rot_xy:
                if fit_overlap_start is None or fit_overlap_stop is None:
                    print_debug_range("Rotation fitting range", None, None)
                else:
                    print_debug_range(
                        "Rotation fitting range",
                        fit_overlap_start,
                        min(
                            fit_overlap_stop,
                            fit_overlap_start + args.rot_fit_span,
                        ),
                    )

        def build_pairs(ref_states, cmp_states):
            """Build comparison pairs with current configuration."""
            return build_comparison_pairs(
                ref_states,
                cmp_states,
                reference_oem,
                args.interpolate_ref,
                args.interpolate_data,
                has_time_window,
                overlap_start,
                overlap_stop,
            )

        # Each interpolator evaluates one history at epochs from the other.
        reference_interpolator = create_interpolator(
            reference_states,
            args.interpolate_ref,
            args.interpolate_type,
        )
        comparison_interpolator = create_interpolator(
            comparison_states,
            args.interpolate_data,
            args.interpolate_type,
        )
        comparison_pairs = build_pairs(reference_states, comparison_states)

        stages: list[TransformationStage] = []
        stage_sequence: list[str] = list(args.stage_sequence)
        if args.rot and "rot" not in stage_sequence:
            stage_sequence.append("rot")
        if args.rot_xy and "rot_xy" not in stage_sequence:
            stage_sequence.append("rot_xy")
        if args.rot_z and "rot_z" not in stage_sequence:
            stage_sequence.append("rot_z")
        if args.time_shift and "time_shift" not in stage_sequence:
            stage_sequence.append("time_shift")

        for stage_key in stage_sequence:
            if fit_overlap_start is None or fit_overlap_stop is None:
                raise ValueError(
                    "Transformation stages require overlapping reference and "
                    "comparison histories"
                )

            if stage_key == "rot":
                stages.append(
                    RotationStage(
                        reference_oem,
                        args.interpolate_ref,
                        args.interpolate_data,
                        fit_overlap_start,
                        fit_overlap_stop,
                        args.rot_fit_span,
                    )
                )
            elif stage_key == "rot_xy":
                stages.append(
                    RotationXYStage(
                        reference_oem,
                        args.interpolate_ref,
                        args.interpolate_data,
                        fit_overlap_start,
                        fit_overlap_stop,
                        args.rot_fit_span,
                    )
                )
            elif stage_key == "rot_z":
                stages.append(
                    RotationZStage(
                        reference_oem,
                        args.interpolate_ref,
                        args.interpolate_data,
                        fit_overlap_start,
                        fit_overlap_stop,
                        args.rot_fit_span,
                    )
                )
            elif stage_key == "time_shift":
                stages.append(
                    TimeShiftStage(
                        reference_oem,
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
            verbose=args.verbose,
            rtn=args.rtn,
            title="Normal comparison" if stages else None,
        ).print()
        if stages:
            pipeline = TransformationPipeline(
                reference_states=reference_states,
                comparison_states=comparison_states,
                stages=stages,
                build_pairs=build_pairs,
                interpolate_ref=args.interpolate_ref,
                interpolate_data=args.interpolate_data,
                interpolator_type=args.interpolate_type,
                debug=args.debug,
            )
            stage_outputs = pipeline.execute()

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
                transformed_comparison_interpolator = create_interpolator(
                    transformed_comparison_states,
                    args.interpolate_data,
                    args.interpolate_type,
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
                    verbose=args.verbose,
                    rtn=args.rtn,
                    title=f"Comparison after stage {stage_index}: {stage.name}",
                    fit_description=stage.describe_fit(fit_result),
                ).print()

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
