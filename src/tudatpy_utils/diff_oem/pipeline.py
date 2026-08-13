"""Transformation pipeline for OEM comparison operations."""

from __future__ import annotations

import sys
from typing import Any, Callable

from tudatpy_utils.core.interpolator import hermite, lagrange

from . import data_structures
from . import transformation_stages
from . import types as diff_types


def create_interpolator(
    states: list[diff_types.State],
    enabled: bool,
    interpolator_type: str = "hermite",
) -> lagrange.LagrangeInterpolator | hermite.HermiteInterpolator | None:
    """Create an interpolator for state history when enabled.

    Parameters
    ----------
    states : list[State]
        State history as (timestamp, state_vector) tuples.
    enabled : bool
        Whether to create the interpolator.
    interpolator_type : str
        Type of interpolator: "lagrange" or "hermite" (default).

    Returns
    -------
    LagrangeInterpolator | HermiteInterpolator | None
        Configured interpolator or None if disabled.
    """
    if not enabled:
        return None

    if interpolator_type == "hermite":
        interpolator = hermite.HermiteInterpolator(
            dimension=6,
            degree=transformation_stages.DEFAULT_INTERPOLATION_DEGREE,
            is_cartesian_state=True,
        )
        interpolator.set_data(states)
        # Set derivative data from velocity components
        derivative_data = [(t, state[3:6]) for t, state in states]
        interpolator.set_derivative_data(derivative_data)
    else:  # lagrange
        interpolator = lagrange.LagrangeInterpolator(
            dimension=6, degree=transformation_stages.DEFAULT_INTERPOLATION_DEGREE
        )
        interpolator.set_data(states)

    return interpolator


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
        interpolator_type: str = "hermite",
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
        interpolator_type : str
            Type of interpolator: "lagrange" or "hermite" (default).
        debug : bool, default=False
            Whether to print pipeline progress to stderr.
        """
        self.reference_states = reference_states
        self.comparison_states = comparison_states
        self.stages = stages
        self.build_pairs = build_pairs
        self.interpolate_ref = interpolate_ref
        self.interpolate_data = interpolate_data
        self.interpolator_type = interpolator_type
        self.debug = debug

    def execute(
        self,
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
                f"[diff_oem] Pipeline start: stages={len(self.stages)}, "
                f"reference_states={len(self.reference_states)}, "
                f"comparison_states={len(self.comparison_states)}",
                file=sys.stderr,
            )
        reference_interpolator = create_interpolator(
            self.reference_states,
            self.interpolate_ref
            or any(stage.requires_reference_interpolation for stage in self.stages),
            self.interpolator_type,
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
                self.interpolator_type,
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
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"complete: {stage.name}, "
                    f"output_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )

        if self.debug:
            print("[diff_oem] Pipeline complete", file=sys.stderr)
        return stage_outputs
