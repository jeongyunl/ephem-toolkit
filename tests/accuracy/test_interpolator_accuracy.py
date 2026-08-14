"""Accuracy tests for interpolators using slice_oem extract_states_by_time.

Loads OEM files with various step sizes, interpolates to the reference step
size, and compares against the reference OEM.

Test datasets:
  - ISS: reference at 4m, inputs at 8m/12m/16m/20m/40m
  - JPSS-1: reference at 1m, inputs at 2m/3m/5m/10m/15m

Run with: pytest -m accuracy -s
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from core.ccsds.oem import CcsdsOem
from core.interpolator.interpolation_spec import InterpolationSpec, InterpolationType
from core.slice_oem import TimeSliceOptions, extract_states_by_time

DATA_DIR = Path(__file__).parent.parent / "data"

# --- ISS dataset: 4-minute reference ---
ISS_REFERENCE_FILE = DATA_DIR / "ISS_2026-05-20_small.OEM"
ISS_INPUT_FILES = [
    "ISS_2026-05-20_small.8m.OEM",
    "ISS_2026-05-20_small.12m.OEM",
    "ISS_2026-05-20_small.16m.OEM",
    "ISS_2026-05-20_small.20m.OEM",
    "ISS_2026-05-20_small.40m.OEM",
]
ISS_STEP_SIZE = timedelta(minutes=4)

# --- JPSS-1 dataset: 1-minute reference ---
JPSS1_REFERENCE_FILE = DATA_DIR / "JPSS-1_small.oem"
JPSS1_INPUT_FILES = [
    "JPSS-1_small.2m.oem",
    "JPSS-1_small.3m.oem",
    "JPSS-1_small.5m.oem",
    "JPSS-1_small.10m.oem",
    "JPSS-1_small.15m.oem",
]
JPSS1_STEP_SIZE = timedelta(minutes=1)

INTERPOLATION_SPECS = [
    InterpolationSpec(interp_type=InterpolationType.HERMITE, degree=3),
    InterpolationSpec(interp_type=InterpolationType.HERMITE, degree=5),
    InterpolationSpec(interp_type=InterpolationType.HERMITE, degree=7),
    InterpolationSpec(interp_type=InterpolationType.LAGRANGE, degree=3),
    InterpolationSpec(interp_type=InterpolationType.LAGRANGE, degree=5),
    InterpolationSpec(interp_type=InterpolationType.LAGRANGE, degree=7),
    InterpolationSpec(interp_type=InterpolationType.LAGRANGE, degree=9),
    InterpolationSpec(interp_type=InterpolationType.CHEBYSHEV, degree=3),
    InterpolationSpec(interp_type=InterpolationType.CHEBYSHEV, degree=5),
    InterpolationSpec(interp_type=InterpolationType.CHEBYSHEV, degree=7),
    InterpolationSpec(interp_type=InterpolationType.CUBIC),
]

# Position tolerance in km — loose bound to catch catastrophic failures only.
MAX_POSITION_ERROR_KM = 1.0e8


def _spec_id(spec: InterpolationSpec) -> str:
    return f"{spec.interp_type.value}_deg{spec.degree}"


def _file_id(filename: str) -> str:
    return filename.split(".")[-2]


# --- Fixtures: ISS ---


@pytest.fixture(scope="module")
def iss_reference_oem() -> CcsdsOem:
    """Load the ISS 4-minute reference OEM."""
    return CcsdsOem.read(str(ISS_REFERENCE_FILE))


@pytest.fixture(scope="module")
def iss_reference_states(iss_reference_oem: CcsdsOem) -> dict[float, np.ndarray]:
    """Build timestamp -> state lookup from ISS reference OEM."""
    return {ts: state for ts, state in iss_reference_oem.states}


# --- Fixtures: JPSS-1 ---


@pytest.fixture(scope="module")
def jpss1_reference_oem() -> CcsdsOem:
    """Load the JPSS-1 1-minute reference OEM."""
    return CcsdsOem.read(str(JPSS1_REFERENCE_FILE))


@pytest.fixture(scope="module")
def jpss1_reference_states(jpss1_reference_oem: CcsdsOem) -> dict[float, np.ndarray]:
    """Build timestamp -> state lookup from JPSS-1 reference OEM."""
    return {ts: state for ts, state in jpss1_reference_oem.states}


# --- Helper ---


def _run_accuracy_test(
    input_file: str,
    spec: InterpolationSpec,
    step_size: timedelta,
    reference_states: dict[float, np.ndarray],
) -> None:
    """Interpolate input OEM and compare against reference states."""
    oem = CcsdsOem.read(str(DATA_DIR / input_file))

    options = TimeSliceOptions(
        start_time=None,
        stop_time=timedelta(0),
        step_size=step_size,
        interpolation_spec=spec,
    )

    result_oem = extract_states_by_time(oem, options)

    position_errors_km: list[float] = []
    velocity_errors_kms: list[float] = []

    for ts, interp_state in result_oem.states:
        if ts not in reference_states:
            continue
        ref_state = reference_states[ts]

        pos_err = np.linalg.norm(interp_state[:3] - ref_state[:3])
        position_errors_km.append(pos_err)

        vel_err = np.linalg.norm(interp_state[3:6] - ref_state[3:6])
        velocity_errors_kms.append(vel_err)

    assert len(position_errors_km) > 0, "No matching timestamps found"

    max_pos = max(position_errors_km)
    rms_pos = float(np.sqrt(np.mean(np.array(position_errors_km) ** 2)))
    max_vel = max(velocity_errors_kms)
    rms_vel = float(np.sqrt(np.mean(np.array(velocity_errors_kms) ** 2)))

    print(
        f"\n  [{_file_id(input_file)}][{_spec_id(spec)}] "
        f"pos_max={max_pos:.3f} km  pos_rms={rms_pos:.3f} km  "
        f"vel_max={max_vel:.6f} km/s  vel_rms={rms_vel:.6f} km/s  "
        f"n={len(position_errors_km)}"
    )

    assert max_pos < MAX_POSITION_ERROR_KM, (
        f"Position error {max_pos:.3f} km exceeds sanity bound "
        f"[{_file_id(input_file)}][{_spec_id(spec)}]"
    )


# --- ISS tests ---


@pytest.mark.accuracy
@pytest.mark.parametrize("input_file", ISS_INPUT_FILES, ids=_file_id)
@pytest.mark.parametrize("spec", INTERPOLATION_SPECS, ids=_spec_id)
def test_iss_interpolator_accuracy(
    input_file: str,
    spec: InterpolationSpec,
    iss_reference_states: dict[float, np.ndarray],
) -> None:
    """ISS: interpolate to 4m steps and compare against reference."""
    _run_accuracy_test(input_file, spec, ISS_STEP_SIZE, iss_reference_states)


# --- JPSS-1 tests ---


@pytest.mark.accuracy
@pytest.mark.parametrize("input_file", JPSS1_INPUT_FILES, ids=_file_id)
@pytest.mark.parametrize("spec", INTERPOLATION_SPECS, ids=_spec_id)
def test_jpss1_interpolator_accuracy(
    input_file: str,
    spec: InterpolationSpec,
    jpss1_reference_states: dict[float, np.ndarray],
) -> None:
    """JPSS-1: interpolate to 1m steps and compare against reference."""
    _run_accuracy_test(input_file, spec, JPSS1_STEP_SIZE, jpss1_reference_states)


# --- Useable time range tests ---


def _expected_margin_intervals(spec: InterpolationSpec) -> int:
    """Return expected margin in number of source data intervals."""
    import math

    if spec.interp_type == InterpolationType.CUBIC:
        return 2
    return math.ceil(spec.degree / 2)


@pytest.mark.accuracy
@pytest.mark.parametrize("spec", INTERPOLATION_SPECS, ids=_spec_id)
def test_useable_time_range_metadata(spec: InterpolationSpec) -> None:
    """Verify OEM USEABLE_START_TIME/USEABLE_STOP_TIME metadata is set correctly after interpolation."""
    input_file = "JPSS-1_small.5m.oem"
    oem = CcsdsOem.read(str(DATA_DIR / input_file))

    options = TimeSliceOptions(
        start_time=None,
        stop_time=timedelta(0),
        step_size=timedelta(minutes=1),
        interpolation_spec=spec,
    )

    result_oem = extract_states_by_time(oem, options)

    # Useable times must be set
    assert result_oem.meta.useable_start_time, "USEABLE_START_TIME not set"
    assert result_oem.meta.useable_stop_time, "USEABLE_STOP_TIME not set"

    # Parse timestamps
    from core.time_utils import iso8601_to_datetime

    start_dt = iso8601_to_datetime(result_oem.meta.start_time)
    stop_dt = iso8601_to_datetime(result_oem.meta.stop_time)
    useable_start_dt = iso8601_to_datetime(result_oem.meta.useable_start_time)
    useable_stop_dt = iso8601_to_datetime(result_oem.meta.useable_stop_time)

    # Useable range must be inside start/stop
    assert useable_start_dt > start_dt
    assert useable_stop_dt < stop_dt
    assert useable_start_dt < useable_stop_dt

    # Verify margin matches expected intervals
    # Source data interval is 5 minutes
    source_interval_s = 5 * 60
    expected_margin_s = _expected_margin_intervals(spec) * source_interval_s

    actual_start_margin = (useable_start_dt - start_dt).total_seconds()
    actual_stop_margin = (stop_dt - useable_stop_dt).total_seconds()

    assert (
        abs(actual_start_margin - expected_margin_s) < 1.0
    ), f"Start margin {actual_start_margin}s != expected {expected_margin_s}s"
    assert (
        abs(actual_stop_margin - expected_margin_s) < 1.0
    ), f"Stop margin {actual_stop_margin}s != expected {expected_margin_s}s"

    print(
        f"\n  [{_spec_id(spec)}] margin={expected_margin_s/60:.0f}m "
        f"useable={result_oem.meta.useable_start_time} to {result_oem.meta.useable_stop_time}"
    )
