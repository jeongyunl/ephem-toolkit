"""Transformation pipeline for OEM comparison operations."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Callable

import ephem_toolkit.core.interpolator.interpolation_spec as interpolation_spec
import ephem_toolkit.core.time_utils as time_utils

from . import data_structures
from . import transformation_stages
from . import types as diff_types


def _format_epoch(epoch_s: float | None) -> str:
    """Format a POSIX epoch for debug output."""
    if epoch_s is None:
        return "none"
    return time_utils.datetime_to_iso8601(
        datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    )


class TransformationPipeline:
    """Manage and execute an ordered sequence of transformation stages."""

    def __init__(
        self,
        reference_states: list[diff_types.State],
        comparison_states: list[diff_types.State],
        stages: list[transformation_stages.TransformationStage],
        build_pairs: Callable[
            [list[diff_types.State], list[diff_types.State]], list[diff_types.StatePair]
        ],
        interpolate_ref: bool,
        interpolate_data: bool,
        interpolation_spec: interpolation_spec.InterpolationSpec,
        debug: bool = False,
    ) -> None:
        """Initialize an ordered transformation pipeline.

        Parameters
        ----------
        reference_states : list[State]
            Reference state history.
        comparison_states : list[State]
            Comparison state history.
        stages : list[TransformationStage]
            Transformation stages to fit and apply in order.
        build_pairs : Callable
            Function that builds comparison pairs for a pair of histories.
        interpolate_ref : bool
            Whether to interpolate reference states during comparison.
        interpolate_data : bool
            Whether to interpolate comparison states during comparison.
        interpolation_spec : InterpolationSpec
            Interpolation specification with type and degree.
        debug : bool, default=False
            Whether to print pipeline progress to stderr.
        """
        self.reference_states = reference_states
        self.comparison_states = comparison_states
        self.stages = stages
        self.build_pairs = build_pairs
        self.interpolate_ref = interpolate_ref
        self.interpolate_data = interpolate_data
        self.interpolation_spec = interpolation_spec
        self.debug = debug

    def execute(
        self,
        verbose: bool,
    ) -> list[
        tuple[transformation_stages.TransformationStage, Any, list[diff_types.State]]
    ]:
        """Fit and apply each stage in order.

        Returns
        -------
        list[tuple[TransformationStage, Any, list[State]]]
            Each stage, its fitted result, and its transformed comparison states.
        """
        stage_outputs: list[
            tuple[
                transformation_stages.TransformationStage, Any, list[diff_types.State]
            ]
        ] = []
        current_comparison_states = self.comparison_states
        if self.debug:
            print(
                f"[diff_oem.pipeline] Pipeline start: stages={len(self.stages)}, "
                f"reference_states={len(self.reference_states)}, "
                f"comparison_states={len(self.comparison_states)}",
                file=sys.stderr,
            )
            if self.reference_states:
                print(
                    f"[diff_oem.pipeline] Reference time range: "
                    f"[{_format_epoch(self.reference_states[0][0])} .. "
                    f"{_format_epoch(self.reference_states[-1][0])}]",
                    file=sys.stderr,
                )
            if self.comparison_states:
                print(
                    f"[diff_oem.pipeline] Comparison time range: "
                    f"[{_format_epoch(self.comparison_states[0][0])} .. "
                    f"{_format_epoch(self.comparison_states[-1][0])}]",
                    file=sys.stderr,
                )
        reference_interpolator = (
            factory.InterpolatorFactory.create(
                spec=self.interpolation_spec,
                dimension=6,
                is_cartesian_state=True,
                verbose=verbose,
                context="TransformationPipeline.reference_interpolator",
                data=self.reference_states,
            )
            if (
                self.interpolate_ref
                or any(stage.requires_reference_interpolation for stage in self.stages)
            )
            else None
        )

        for stage_index, stage in enumerate(self.stages, start=1):
            if self.debug:
                print(
                    f"[diff_oem.pipeline] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"start: {stage.name}, "
                    f"input_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )
                if current_comparison_states:
                    print(
                        f"[diff_oem.pipeline] Stage {stage_index} input time range: "
                        f"[{_format_epoch(current_comparison_states[0][0])} .. "
                        f"{_format_epoch(current_comparison_states[-1][0])}]",
                        file=sys.stderr,
                    )
            comparison_interpolator = (
                factory.InterpolatorFactory.create(
                    spec=self.interpolation_spec,
                    dimension=6,
                    is_cartesian_state=True,
                    verbose=verbose,
                    context=f"TransformationPipeline.comparison_interpolator",
                    data=current_comparison_states,
                )
                if self.interpolate_data
                else None
            )
            fit_pairs = stage.build_fit_pairs(
                self.reference_states,
                current_comparison_states,
            )
            if self.debug:
                print(
                    f"[diff_oem.pipeline] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"fitting: fit_pairs={len(fit_pairs)}",
                    file=sys.stderr,
                )
                if fit_pairs:
                    fit_ref_start = fit_pairs[0][0][0]
                    fit_ref_stop = fit_pairs[-1][0][0]
                    fit_cmp_start = fit_pairs[0][1][0]
                    fit_cmp_stop = fit_pairs[-1][1][0]
                    print(
                        f"[diff_oem.pipeline] Stage {stage_index} fit ref time range: "
                        f"[{_format_epoch(fit_ref_start)} .. {_format_epoch(fit_ref_stop)}], "
                        f"fit cmp time range: "
                        f"[{_format_epoch(fit_cmp_start)} .. {_format_epoch(fit_cmp_stop)}]",
                        file=sys.stderr,
                    )
            stage_input = data_structures.TransformationStageInput(
                state_pairs=fit_pairs,
                reference_interpolator=reference_interpolator,
                comparison_interpolator=comparison_interpolator,
            )
            fit_result = stage.fit(stage_input)
            current_comparison_states = stage.transform(
                current_comparison_states, fit_result
            )
            stage_outputs.append((stage, fit_result, current_comparison_states))

            self.build_pairs(self.reference_states, current_comparison_states)
            if self.debug:
                print(
                    f"[diff_oem.pipeline] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"complete: {stage.name}, "
                    f"output_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )
                if current_comparison_states:
                    print(
                        f"[diff_oem.pipeline] Stage {stage_index} output time range: "
                        f"[{_format_epoch(current_comparison_states[0][0])} .. "
                        f"{_format_epoch(current_comparison_states[-1][0])}]",
                        file=sys.stderr,
                    )

        if self.debug:
            print("[diff_oem.pipeline] Pipeline complete", file=sys.stderr)
        return stage_outputs
