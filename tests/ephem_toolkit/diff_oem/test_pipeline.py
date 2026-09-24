"""Tests for the OEM comparison transformation pipeline."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np

import ephem_toolkit.diff_oem.pipeline as pipeline
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)


class IncrementStage:
    def __init__(self, name: str, increment: float) -> None:
        self.name = name
        self.increment = increment
        self.fit_inputs = []

    def build_fit_pairs(self, reference_states, comparison_states):
        return [(reference_states[0], comparison_states[0])]

    def fit(self, stage_input):
        self.fit_inputs.append(stage_input)
        return self.increment

    def transform(self, states, fit_result):
        return [(epoch, state + fit_result) for epoch, state in states]


def test_pipeline_executes_stages_in_order_and_reports_debug_progress(
    monkeypatch, capsys
) -> None:
    reference_states = [
        (100.0, np.full(6, 1.0)),
        (200.0, np.full(6, 2.0)),
    ]
    comparison_states = [
        (100.0, np.full(6, 10.0)),
        (200.0, np.full(6, 20.0)),
    ]
    stages = [IncrementStage("first", 1.0), IncrementStage("second", 2.0)]
    interpolators = [object(), object(), object()]
    create_interpolator = Mock(side_effect=interpolators)
    monkeypatch.setattr(
        pipeline.factory.InterpolatorFactory,
        "create",
        create_interpolator,
    )
    built_pairs = []

    def build_pairs(reference, comparison):
        built_pairs.append(comparison)
        return [(reference[0], comparison[0])]

    transformation_pipeline = pipeline.TransformationPipeline(
        reference_states=reference_states,
        comparison_states=comparison_states,
        stages=stages,
        build_pairs=build_pairs,
        interpolation_spec=InterpolationSpec(
            interp_type=InterpolationType.HERMITE, degree=3
        ),
        debug=True,
    )

    outputs = transformation_pipeline.execute(verbose=False)

    assert [fit_result for _, fit_result, _ in outputs] == [1.0, 2.0]
    np.testing.assert_array_equal(outputs[0][2][0][1], np.full(6, 11.0))
    np.testing.assert_array_equal(outputs[1][2][0][1], np.full(6, 13.0))
    assert len(stages[0].fit_inputs) == 1
    assert len(stages[1].fit_inputs) == 1
    assert create_interpolator.call_count == 3
    assert [states[0][1][0] for states in built_pairs] == [11.0, 13.0]
    stderr = capsys.readouterr().err
    assert "Pipeline start: stages=2" in stderr
    assert "Pipeline stage 1/2 complete: first" in stderr
    assert "Pipeline complete" in stderr
