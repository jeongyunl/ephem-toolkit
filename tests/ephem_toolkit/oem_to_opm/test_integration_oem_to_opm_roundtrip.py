"""Integration tests for OEM to OPM conversion."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ephem_toolkit.core.ccsds import oem
from ephem_toolkit.core.interpolator import factory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.diff_oem.comparison import compare_states, read_states

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
TEST_DATA_DIR: Path = TEST_DIR.parent.parent / "data"

MAX_VELOCITY_ERROR_KM_S: float = 0.03


def _build_env() -> dict[str, str]:
    """Build an environment with the project source roots on PYTHONPATH."""
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    source_roots = [
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "src" / "ephem_toolkit",
    ]
    env["PYTHONPATH"] = os.pathsep.join(
        [*(str(path) for path in source_roots), existing]
        if existing
        else [*(str(path) for path in source_roots)]
    )
    return env


def _run_roundtrip(
    reference_oem: Path,
    tmp_path: Path,
    *,
    fit_span: str = "2h",
    duration: str = "2h",
    step: str = "30m",
) -> tuple[Path, Path]:
    """Generate an OPM and propagate it back to OEM using the project CLIs."""
    opm_path = tmp_path / "roundtrip.opm"
    propagated_oem = tmp_path / "roundtrip_propagated.oem"

    oem_to_opm_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.oem_to_opm.__main__",
            str(reference_oem),
            "-o",
            str(opm_path),
            "--fit-span",
            fit_span,
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )
    assert oem_to_opm_result.returncode == 0, oem_to_opm_result.stderr

    propagate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.propagate_kepler.__main__",
            str(opm_path),
            "-d",
            duration,
            "-s",
            step,
            "-o",
            str(propagated_oem),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )
    assert propagate_result.returncode == 0, propagate_result.stderr

    return opm_path, propagated_oem


def _max_roundtrip_error_km(
    reference_oem: Path,
    propagated_oem: Path,
) -> tuple[float, float, int]:
    """Compare the original OEM against a propagated OEM using a Hermite interpolator."""
    hermite_spec = InterpolationSpec(InterpolationType.HERMITE, 5)
    reference_states = read_states(reference_oem)
    propagated_states = read_states(propagated_oem)
    reference_interpolator = factory.InterpolatorFactory.create(
        spec=hermite_spec,
        dimension=6,
        is_cartesian_state=True,
        data=reference_states,
    )
    propagated_interpolator = factory.InterpolatorFactory.create(
        spec=hermite_spec,
        dimension=6,
        is_cartesian_state=True,
        data=propagated_states,
    )

    max_position_km = 0.0
    max_velocity_km_s = 0.0
    sample_count = 0

    for propagated_epoch, propagated_state in propagated_states:
        reference_state = reference_interpolator.interpolate(propagated_epoch)
        comparison = compare_states(
            (propagated_epoch, reference_state),
            (propagated_epoch, propagated_state),
            reference_interpolator,
            propagated_interpolator,
        )
        max_position_km = max(max_position_km, comparison.position_diff_magnitude_km)
        max_velocity_km_s = max(
            max_velocity_km_s, comparison.velocity_diff_magnitude_km_s
        )
        sample_count += 1

    return max_position_km, max_velocity_km_s, sample_count


def test_oem_to_opm_requires_input_file_name() -> None:
    """The CLI should require an explicit input filename or '-' for stdin."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.oem_to_opm.__main__",
            "-o",
            "-",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode != 0
    assert "required: <input_oem|->" in result.stderr.lower()

    stdin_oem = (TEST_DATA_DIR / "ISS_2026-05-20_small.OEM").read_text(encoding="utf-8")
    stdin_result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.oem_to_opm.__main__",
            "-",
            "--output",
            "-",
        ],
        input=stdin_oem,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert stdin_result.returncode == 0, stdin_result.stderr
    assert "CCSDS_OPM_VERS" in stdin_result.stdout


@pytest.mark.accuracy
@pytest.mark.parametrize(
    ("reference_filename", "max_position_error_km"),
    [
        ("JPSS-1_small.oem", 10.0),
        ("ISS_2026-05-20_small.OEM", 25.0),
    ],
)
def test_oem_to_opm_roundtrip_accuracy(
    tmp_path: Path,
    reference_filename: str,
    max_position_error_km: float,
) -> None:
    """A propagated Keplerian OPM should remain close to the source OEM."""
    reference_oem = TEST_DATA_DIR / reference_filename
    _, propagated_oem = _run_roundtrip(reference_oem, tmp_path)

    max_position_km, max_velocity_km_s, sample_count = _max_roundtrip_error_km(
        reference_oem,
        propagated_oem,
    )

    assert sample_count > 0
    assert (
        max_position_km < max_position_error_km
    ), f"Roundtrip position error {max_position_km:.3f} km exceeds {max_position_error_km:g} km"
    assert (
        max_velocity_km_s < MAX_VELOCITY_ERROR_KM_S
    ), f"Roundtrip velocity error {max_velocity_km_s:.6f} km/s exceeds {MAX_VELOCITY_ERROR_KM_S:g} km/s"
