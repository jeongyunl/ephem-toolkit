"""Transformation pipeline for OEM comparison operations."""

from __future__ import annotations

import sys
from typing import Any, Callable

import common.interpolator.lagrange as lagrange

from .data_structures import TransformationStageInput
from .transformation_stages import TransformationStage, INTERPOLATION_DEGREE
from .types import State, StatePair


def create_interpolator(
    states: list[State],
    enabled: bool,
) -> lagrange.LagrangeInterpolator | None:
    """Create a Lagrange interpolator for state history when enabled."""
    if not enabled:
        return None
    interpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=INTERPOLATION_DEGREE
    )
    interpolator.set_data(states)
    return interpolator


class TransformationPipeline:
    """Manage and execute an ordered sequence of transformation stages."""

    def __init__(
        self,
        reference_states: list[State],
        comparison_states: list[State],
        stages: list[TransformationStage],
        build_pairs: Callable[[list[State], list[State]], list[StatePair]],
        interpolate_ref: bool,
        interpolate_data: bool,
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
        debug : bool, default=False
            Whether to print pipeline progress to stderr.
        """
        self.reference_states = reference_states
        self.comparison_states = comparison_states
        self.stages = stages
        self.build_pairs = build_pairs
        self.interpolate_ref = interpolate_ref
        self.interpolate_data = interpolate_data
        self.debug = debug

    def execute(self) -> list[tuple[TransformationStage, Any, list[State]]]:
        """Fit and apply each stage in order.

        Returns
        -------
        list[tuple[TransformationStage, Any, list[State]]]
            Each stage, its fitted result, and its transformed comparison states.
        """
        stage_outputs: list[tuple[TransformationStage, Any, list[State]]] = []
        current_comparison_states = self.comparison_states
        if self.debug:
            print(
                f"[diff_oem] Pipeline start: stages={len(self.stages)}, "
                f"reference_states={len(self.reference_states)}, "
                f"comparison_states={len(self.comparison_states)}",
                file=sys.stderr,
            )
        reference_interpolator = create_interpolator(
            self.reference_states,
            self.interpolate_ref
            or any(stage.requires_reference_interpolation for stage in self.stages),
        )

        for stage_index, stage in enumerate(self.stages, start=1):
            if self.debug:
                print(
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"start: {stage.name}, "
                    f"input_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )
            comparison_interpolator = create_interpolator(
                current_comparison_states,
                self.interpolate_data,
            )
            fit_pairs = stage.build_fit_pairs(
                self.reference_states,
                current_comparison_states,
            )
            if self.debug:
                print(
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"fitting: fit_pairs={len(fit_pairs)}",
                    file=sys.stderr,
                )
            stage_input = TransformationStageInput(
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
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"complete: {stage.name}, "
                    f"output_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )

        if self.debug:
            print("[diff_oem] Pipeline complete", file=sys.stderr)
        return stage_outputs
