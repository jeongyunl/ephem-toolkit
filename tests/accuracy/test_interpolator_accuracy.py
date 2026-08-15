"""Accuracy tests for interpolators using slice_oem extract_states_by_time.

Loads OEM files with various step sizes, interpolates to the reference step
size, and compares against the reference OEM.

Test datasets:
  - ISS: reference at 4m, inputs at 8m/12m/16m
  - JPSS-1: reference at 1m, inputs at 2m/3m/5m/10m/15m

Run with: pytest -m accuracy -s
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from core.ccsds import oem
from core.interpolator import interpolation_spec as interp_spec
from core import slice_oem
import core.time_utils as time_utils

DATA_DIR = Path(__file__).parent.parent / "data"
"""Directory containing test OEM data files."""


@dataclass
class DatasetConfig:
    """Configuration for a test dataset."""

    reference_file: Path
    """Path to reference OEM file with finest time resolution."""
    input_files: list[str]
    """List of input OEM filenames with coarser time steps."""
    step_size: timedelta
    """Time step for interpolation output."""


# Test datasets configuration
DATASETS = {
    "JPSS-1": DatasetConfig(
        reference_file=DATA_DIR / "JPSS-1_small.oem",
        input_files=[
            "JPSS-1_small.2m.oem",
            "JPSS-1_small.3m.oem",
            "JPSS-1_small.5m.oem",
            "JPSS-1_small.10m.oem",
            # "JPSS-1_small.15m.oem",
        ],
        step_size=timedelta(minutes=1),
    ),
    "ISS": DatasetConfig(
        reference_file=DATA_DIR / "ISS_2026-05-20_small.OEM",
        input_files=[
            "ISS_2026-05-20_small.8m.OEM",
            "ISS_2026-05-20_small.12m.OEM",
            # "ISS_2026-05-20_small.16m.OEM",
        ],
        step_size=timedelta(minutes=4),
    ),
}

INTERPOLATION_SPECS = [
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.HERMITE, degree=3
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.HERMITE, degree=5
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.HERMITE, degree=7
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.LAGRANGE, degree=7
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.LAGRANGE, degree=9
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.LAGRANGE, degree=11
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.CHEBYSHEV, degree=5
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.CHEBYSHEV, degree=7
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.CHEBYSHEV, degree=9
    ),
    interp_spec.InterpolationSpec(
        interp_type=interp_spec.InterpolationType.CHEBYSHEV, degree=11
    ),
    interp_spec.InterpolationSpec(interp_type=interp_spec.InterpolationType.CUBIC),
]
"""List of interpolation specifications to test."""

MAX_POSITION_ERROR_KM: float = 1.0e8
"""Position tolerance (km) — loose bound to catch catastrophic failures only."""


def _spec_id(spec: interp_spec.InterpolationSpec) -> str:
    return f"{spec.interp_type.value}_deg{spec.degree}"


def _file_id(filename: str) -> str:
    return filename.split(".")[-2]


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def iss_reference_states() -> dict[float, np.ndarray]:
    """Build timestamp -> state lookup from ISS reference OEM."""
    iss_oem = oem.CcsdsOem.read(str(DATASETS["ISS"].reference_file))
    return {ts: state for ts, state in iss_oem.states}


@pytest.fixture(scope="module")
def jpss1_reference_states() -> dict[float, np.ndarray]:
    """Build timestamp -> state lookup from JPSS-1 reference OEM."""
    jpss_oem = oem.CcsdsOem.read(str(DATASETS["JPSS-1"].reference_file))
    return {ts: state for ts, state in jpss_oem.states}


# ===================================================================
# Helper functions
# ===================================================================


def _run_useable_range_accuracy_test(
    input_file: str,
    spec: interp_spec.InterpolationSpec,
    step_size: timedelta,
    reference_states: dict[float, np.ndarray],
) -> dict[str, float | int | interp_spec.InterpolationSpec]:
    """Interpolate input OEM and compare against reference within useable range only."""
    input_oem = oem.CcsdsOem.read(str(DATA_DIR / input_file))

    options = slice_oem.TimeSliceOptions(
        start_time=None,
        stop_time=timedelta(0),
        step_size=step_size,
        interpolation_spec=spec,
    )

    result_oem = slice_oem.extract_states_by_time(input_oem, options)

    # Determine useable time bounds
    if result_oem.meta.useable_start_time and result_oem.meta.useable_stop_time:
        useable_start_ts = time_utils.iso8601_to_datetime(
            result_oem.meta.useable_start_time
        ).timestamp()
        useable_stop_ts = time_utils.iso8601_to_datetime(
            result_oem.meta.useable_stop_time
        ).timestamp()
    else:
        useable_start_ts = result_oem.states[0][0]
        useable_stop_ts = result_oem.states[-1][0]

    position_errors_km: list[float] = []
    velocity_errors_kms: list[float] = []

    for ts, interp_state in result_oem.states:
        if ts < useable_start_ts or ts > useable_stop_ts:
            continue
        if ts not in reference_states:
            continue
        ref_state = reference_states[ts]

        pos_err = np.linalg.norm(interp_state[:3] - ref_state[:3])
        position_errors_km.append(pos_err)

        vel_err = np.linalg.norm(interp_state[3:6] - ref_state[3:6])
        velocity_errors_kms.append(vel_err)

    assert len(position_errors_km) > 0, "No matching timestamps in useable range"

    pos_array = np.array(position_errors_km)
    vel_array = np.array(velocity_errors_kms)

    max_pos = max(position_errors_km)
    rms_pos = float(np.sqrt(np.mean(pos_array**2)))
    mean_pos = float(np.mean(pos_array))
    std_pos = float(np.std(pos_array))

    max_vel = max(velocity_errors_kms)
    rms_vel = float(np.sqrt(np.mean(vel_array**2)))
    mean_vel = float(np.mean(vel_array))
    std_vel = float(np.std(vel_array))

    assert max_pos < MAX_POSITION_ERROR_KM, (
        f"Position error {max_pos:.3f} km exceeds sanity bound "
        f"[{_file_id(input_file)}][{_spec_id(spec)}]"
    )

    return {
        "spec": spec,
        "label": "useable_range",
        "max_pos": max_pos,
        "rms_pos": rms_pos,
        "mean_pos": mean_pos,
        "std_pos": std_pos,
        "max_vel": max_vel,
        "rms_vel": rms_vel,
        "mean_vel": mean_vel,
        "std_vel": std_vel,
        "count": len(position_errors_km),
    }


def _run_unuseable_range_accuracy_test(
    input_file: str,
    spec: interp_spec.InterpolationSpec,
    step_size: timedelta,
    reference_states: dict[float, np.ndarray],
) -> dict[str, float | int | interp_spec.InterpolationSpec] | None:
    """Interpolate input OEM and compare against reference in unuseable boundary regions only."""
    input_oem = oem.CcsdsOem.read(str(DATA_DIR / input_file))

    options = slice_oem.TimeSliceOptions(
        start_time=None,
        stop_time=timedelta(0),
        step_size=step_size,
        interpolation_spec=spec,
    )

    result_oem = slice_oem.extract_states_by_time(input_oem, options)

    # Determine unuseable time bounds
    if result_oem.meta.useable_start_time and result_oem.meta.useable_stop_time:
        useable_start_ts = time_utils.iso8601_to_datetime(
            result_oem.meta.useable_start_time
        ).timestamp()
        useable_stop_ts = time_utils.iso8601_to_datetime(
            result_oem.meta.useable_stop_time
        ).timestamp()
    else:
        return None  # No unuseable range defined

    position_errors_km: list[float] = []
    velocity_errors_kms: list[float] = []

    for ts, interp_state in result_oem.states:
        # Only test boundary regions: [start, useable_start) and (useable_stop, stop]
        if ts >= useable_start_ts and ts <= useable_stop_ts:
            continue
        if ts not in reference_states:
            continue
        ref_state = reference_states[ts]

        pos_err = np.linalg.norm(interp_state[:3] - ref_state[:3])
        position_errors_km.append(pos_err)

        vel_err = np.linalg.norm(interp_state[3:6] - ref_state[3:6])
        velocity_errors_kms.append(vel_err)

    if len(position_errors_km) == 0:
        return None  # No points in unuseable range

    pos_array = np.array(position_errors_km)
    vel_array = np.array(velocity_errors_kms)

    max_pos = max(position_errors_km)
    rms_pos = float(np.sqrt(np.mean(pos_array**2)))
    mean_pos = float(np.mean(pos_array))
    std_pos = float(np.std(pos_array))

    max_vel = max(velocity_errors_kms)
    rms_vel = float(np.sqrt(np.mean(vel_array**2)))
    mean_vel = float(np.mean(vel_array))
    std_vel = float(np.std(vel_array))

    return {
        "spec": spec,
        "label": "unuseable_range",
        "max_pos": max_pos,
        "rms_pos": rms_pos,
        "mean_pos": mean_pos,
        "std_pos": std_pos,
        "max_vel": max_vel,
        "rms_vel": rms_vel,
        "mean_vel": mean_vel,
        "std_vel": std_vel,
        "count": len(position_errors_km),
    }


def _expected_margin_s(
    spec: interp_spec.InterpolationSpec, source_interval_s: float
) -> float:
    """Return expected margin in seconds matching _compute_unusable_margin logic."""
    if spec.interp_type == interp_spec.InterpolationType.CUBIC:
        # Natural cubic spline: 1 interval as UNUSABLE margin
        base = 1
    elif spec.interp_type == interp_spec.InterpolationType.HERMITE:
        # Hermite (both variants): no UNUSABLE margin
        base = 0
    elif spec.interp_type == interp_spec.InterpolationType.LAGRANGE:
        # Lagrange: degree 5-7 get 2 intervals, degree 9+ get 1 interval
        if spec.degree <= 7:
            base = 2
        else:
            base = 1
    else:
        # Chebyshev: no UNUSABLE margin
        base = 0

    return base * source_interval_s


# ===================================================================
# Useable range accuracy tests
# ===================================================================


@pytest.mark.accuracy
def test_useable_range_accuracy(
    iss_reference_states: dict[float, np.ndarray],
    jpss1_reference_states: dict[float, np.ndarray],
) -> None:
    """Interpolate to reference steps, compare within useable range only."""
    reference_map = {"ISS": iss_reference_states, "JPSS-1": jpss1_reference_states}

    for dataset_name, config in DATASETS.items():
        for input_file in config.input_files:
            print(
                f"\n=== {dataset_name} USEABLE RANGE ACCURACY TEST: {_file_id(input_file)} ==="
            )
            results: list[dict[str, float | int | interp_spec.InterpolationSpec]] = []
            for spec in INTERPOLATION_SPECS:
                result = _run_useable_range_accuracy_test(
                    input_file, spec, config.step_size, reference_map[dataset_name]
                )
                if result is not None:
                    results.append(result)

            for result in sorted(results, key=lambda item: float(item["rms_pos"])):
                spec = result["spec"]
                print(
                    f"  [{_spec_id(spec):16s}] useable_range "
                    f"pos_rms={result['rms_pos']:10.3f} km  "
                    f"pos_mean={result['mean_pos']:10.3f} km  "
                    f"pos_std={result['std_pos']:10.3f} km  "
                    f"pos_max={result['max_pos']:10.3f} km  "
                    f"vel_rms={result['rms_vel']:10.6f} km/s  "
                    f"vel_mean={result['mean_vel']:10.6f} km/s  "
                    f"vel_std={result['std_vel']:10.6f} km/s  "
                    f"vel_max={result['max_vel']:10.6f} km/s  "
                    f"n={result['count']:4d}"
                )


# ===================================================================
# Unuseable range accuracy tests
# ===================================================================


@pytest.mark.accuracy
def test_unuseable_range_accuracy(
    iss_reference_states: dict[float, np.ndarray],
    jpss1_reference_states: dict[float, np.ndarray],
) -> None:
    """Interpolate to reference steps, report errors in unuseable boundary regions."""
    reference_map = {"ISS": iss_reference_states, "JPSS-1": jpss1_reference_states}

    for dataset_name, config in DATASETS.items():
        for input_file in config.input_files:
            print(
                f"\n=== {dataset_name} UNUSEABLE RANGE ACCURACY TEST: {_file_id(input_file)} ==="
            )
            results: list[dict[str, float | int | interp_spec.InterpolationSpec]] = []
            for spec in INTERPOLATION_SPECS:
                result = _run_unuseable_range_accuracy_test(
                    input_file, spec, config.step_size, reference_map[dataset_name]
                )
                if result is not None:
                    results.append(result)

            for result in sorted(results, key=lambda item: float(item["rms_pos"])):
                spec = result["spec"]
                print(
                    f"  [{_spec_id(spec):16s}] unuseable_range "
                    f"pos_rms={result['rms_pos']:10.3f} km  "
                    f"pos_mean={result['mean_pos']:10.3f} km  "
                    f"pos_std={result['std_pos']:10.3f} km  "
                    f"pos_max={result['max_pos']:10.3f} km  "
                    f"vel_rms={result['rms_vel']:10.6f} km/s  "
                    f"vel_mean={result['mean_vel']:10.6f} km/s  "
                    f"vel_std={result['std_vel']:10.6f} km/s  "
                    f"vel_max={result['max_vel']:10.6f} km/s  "
                    f"n={result['count']:4d}"
                )


# ===================================================================
# Useable time range metadata tests
# ===================================================================


@pytest.mark.accuracy
def test_useable_time_range_metadata() -> None:
    """Verify OEM USEABLE_START_TIME/USEABLE_STOP_TIME metadata is set correctly after interpolation."""
    print(f"\n=== USEABLE TIME RANGE METADATA TEST ===")
    input_file = "JPSS-1_small.5m.oem"

    for spec in INTERPOLATION_SPECS:
        input_oem = oem.CcsdsOem.read(str(DATA_DIR / input_file))

        options = slice_oem.TimeSliceOptions(
            start_time=None,
            stop_time=timedelta(0),
            step_size=timedelta(minutes=1),
            interpolation_spec=spec,
        )

        result_oem = slice_oem.extract_states_by_time(input_oem, options)

        # Parse timestamps
        start_dt = time_utils.iso8601_to_datetime(result_oem.meta.start_time)
        stop_dt = time_utils.iso8601_to_datetime(result_oem.meta.stop_time)

        # Check if useable times are set (may be empty if margin is too large)
        if result_oem.meta.useable_start_time and result_oem.meta.useable_stop_time:
            useable_start_dt = time_utils.iso8601_to_datetime(
                result_oem.meta.useable_start_time
            )
            useable_stop_dt = time_utils.iso8601_to_datetime(
                result_oem.meta.useable_stop_time
            )

            # Useable range must be inside start/stop
            assert useable_start_dt > start_dt
            assert useable_stop_dt < stop_dt
            assert useable_start_dt < useable_stop_dt

            # Verify margin matches expected intervals
            source_interval_s = 5 * 60  # Source data interval is 5 minutes
            expected = _expected_margin_s(spec, source_interval_s)

            actual_start_margin = (useable_start_dt - start_dt).total_seconds()
            actual_stop_margin = (stop_dt - useable_stop_dt).total_seconds()

            if expected != float("inf"):
                assert (
                    abs(actual_start_margin - expected) < 60.0
                ), f"Start margin {actual_start_margin}s != expected {expected}s"
                assert (
                    abs(actual_stop_margin - expected) < 60.0
                ), f"Stop margin {actual_stop_margin}s != expected {expected}s"
                margin_str = f"{expected/60:5.1f}m"
            else:
                margin_str = "half-span"

            print(
                f"  [{_spec_id(spec):16s}] margin={margin_str} "
                f"useable={result_oem.meta.useable_start_time} to {result_oem.meta.useable_stop_time}"
            )
        else:
            # Margin too large, no useable range
            print(
                f"  [{_spec_id(spec):16s}] margin=too-large "
                f"useable=(empty - margin exceeds data span)"
            )
