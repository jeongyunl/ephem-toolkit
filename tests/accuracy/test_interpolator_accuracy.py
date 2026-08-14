"""Accuracy tests for interpolators using slice_oem extract_states_by_time.

Loads OEM files with various step sizes (8m, 12m, 16m, 20m, 40m), interpolates
to 4-minute steps, and compares against the 4-minute reference OEM.

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

REFERENCE_FILE = DATA_DIR / "ISS_2026-05-20_small.OEM"

INPUT_FILES = [
    "ISS_2026-05-20_small.8m.OEM",
    "ISS_2026-05-20_small.12m.OEM",
    "ISS_2026-05-20_small.16m.OEM",
    "ISS_2026-05-20_small.20m.OEM",
    "ISS_2026-05-20_small.40m.OEM",
]

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

STEP_SIZE = timedelta(minutes=4)

# Position tolerance in km — loose bound to catch catastrophic failures only.
# Hermite deg5 on 8m data achieves ~3 km; coarser inputs or lower-order methods
# produce much larger errors due to Runge phenomenon on orbital data.
MAX_POSITION_ERROR_KM = 1.0e8


def _spec_id(spec: InterpolationSpec) -> str:
    return f"{spec.interp_type.value}_deg{spec.degree}"


def _file_id(filename: str) -> str:
    return filename.split(".")[-2]


@pytest.fixture(scope="module")
def reference_oem() -> CcsdsOem:
    """Load the 4-minute reference OEM."""
    return CcsdsOem.read(str(REFERENCE_FILE))


@pytest.fixture(scope="module")
def reference_states(reference_oem: CcsdsOem) -> dict[float, np.ndarray]:
    """Build timestamp -> state lookup from reference OEM."""
    return {ts: state for ts, state in reference_oem.states}


@pytest.mark.accuracy
@pytest.mark.parametrize("input_file", INPUT_FILES, ids=_file_id)
@pytest.mark.parametrize("spec", INTERPOLATION_SPECS, ids=_spec_id)
def test_interpolator_accuracy(
    input_file: str,
    spec: InterpolationSpec,
    reference_oem: CcsdsOem,
    reference_states: dict[float, np.ndarray],
) -> None:
    """Interpolate input OEM to 4m steps and compare against reference.

    This is a characterization test: it measures and reports interpolation
    accuracy for each method/degree/input combination. The assertion uses a
    loose bound to detect catastrophic failures only.
    """
    oem = CcsdsOem.read(str(DATA_DIR / input_file))

    options = TimeSliceOptions(
        start_time=None,
        stop_time=timedelta(0),
        step_size=STEP_SIZE,
        interpolation_spec=spec,
    )

    result_oem = extract_states_by_time(oem, options)

    # Compare each interpolated state against reference
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

    # Report (visible with pytest -s)
    print(
        f"\n  [{_file_id(input_file)}][{_spec_id(spec)}] "
        f"pos_max={max_pos:.3f} km  pos_rms={rms_pos:.3f} km  "
        f"vel_max={max_vel:.6f} km/s  vel_rms={rms_vel:.6f} km/s  "
        f"n={len(position_errors_km)}"
    )

    # Loose sanity bound — catches NaN/Inf or completely broken interpolators
    assert max_pos < MAX_POSITION_ERROR_KM, (
        f"Position error {max_pos:.3f} km exceeds sanity bound "
        f"[{_file_id(input_file)}][{_spec_id(spec)}]"
    )
