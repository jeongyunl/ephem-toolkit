"""Tests for Hermite interpolation in slice_oem.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

import core.slice_oem as slice_oem
from core.ccsds.oem import CcsdsOem
from core.interpolator.interpolation_spec import InterpolationSpec, InterpolationType


def test_hermite_interpolation_with_step_size() -> None:
    """Test Hermite interpolation with step size."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    interp_spec = InterpolationSpec(interp_type=InterpolationType.HERMITE)

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=10),
        step_size=timedelta(minutes=2),
        interpolation_spec=interp_spec,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    assert len(sliced_oem.states) == 6
    assert sliced_oem.states[0][0] == base_time.timestamp() + 2 * 60
    assert sliced_oem.states[-1][0] == base_time.timestamp() + 12 * 60


def test_hermite_interpolation_single_state() -> None:
    """Test Hermite interpolation for single state extraction."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    interp_spec = InterpolationSpec(interp_type=InterpolationType.HERMITE)

    target_time = datetime(2024, 1, 1, 0, 2, 30, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=target_time,
        stop_time=None,
        interpolation_spec=interp_spec,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    assert len(sliced_oem.states) == 1
    assert sliced_oem.states[0][0] == target_time.timestamp()


def test_hermite_interpolation_with_boundaries() -> None:
    """Test Hermite interpolation with exact start and stop times."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    interp_spec = InterpolationSpec(interp_type=InterpolationType.HERMITE)

    start_time = datetime(2024, 1, 1, 0, 2, 30, tzinfo=timezone.utc)
    stop_time = datetime(2024, 1, 1, 0, 8, 30, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=stop_time,
        interpolation_spec=interp_spec,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    assert len(sliced_oem.states) > 6
    assert sliced_oem.states[0][0] == start_time.timestamp()
    assert sliced_oem.states[-1][0] == stop_time.timestamp()


def test_hermite_interpolation_verbose_output(capsys) -> None:
    """Test verbose output for Hermite interpolation."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    interp_spec = InterpolationSpec(interp_type=InterpolationType.HERMITE)

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=10),
        step_size=timedelta(minutes=2),
        interpolation_spec=interp_spec,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "Mode: interpolated (hermite degree 5)" in captured.err
    assert "Step size:" in captured.err
