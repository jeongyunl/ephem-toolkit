"""Verify covariance validation in retaining and non-retaining OEM reads."""

import io

import numpy as np
import pytest

import ephem_toolkit.core.ccsds.oem as oem


_PREFIX = (
    "CCSDS_OEM_VERS = 2.0\n"
    "META_START\n"
    "OBJECT_NAME = TEST\n"
    "CENTER_NAME = EARTH\n"
    "REF_FRAME = GCRF\n"
    "TIME_SYSTEM = UTC\n"
    "META_STOP\n"
    "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
    "COVARIANCE_START\n"
)
_EPOCH = "EPOCH = 2026-01-01T00:00:00\n"
_ROWS = "1\n2 3\n4 5 6\n7 8 9 10\n11 12 13 14 15\n16 17 18 19 20 21\n"


@pytest.mark.parametrize(
    "covariance",
    [
        _ROWS + "COVARIANCE_STOP\n",
        _EPOCH + "1\n2 3\nCOVARIANCE_STOP\n",
        _EPOCH + _ROWS.replace("2 3\n", "2\n") + "COVARIANCE_STOP\n",
        _EPOCH + _ROWS.replace("2 3\n", "2 nope\n") + "COVARIANCE_STOP\n",
        _EPOCH + _ROWS.replace("2 3\n", "2=3=4\n") + "COVARIANCE_STOP\n",
        _EPOCH + _ROWS + "22\nCOVARIANCE_STOP\n",
        _EPOCH + _ROWS,
        "EPOCH = invalid\n" + _ROWS + "COVARIANCE_STOP\n",
        _EPOCH + _ROWS + "COMMENT late\nCOVARIANCE_STOP\n",
    ],
)
def test_covariance_errors_match_retained_and_discarded(covariance: str) -> None:
    errors = []
    for retain in (True, False):
        with pytest.raises(ValueError) as error:
            oem.CcsdsOem._read_oem_impl(
                io.StringIO(_PREFIX + covariance), retain_covariances=retain
            )
        errors.append(str(error.value))
    assert errors[0] == errors[1]


def test_discarded_covariance_is_validated_without_matrix_allocation(monkeypatch) -> None:
    source = _PREFIX + _EPOCH + _ROWS + "COVARIANCE_STOP\n"
    original_zeros = np.zeros
    allocations = []

    def track_zeros(shape, *args, **kwargs):
        allocations.append(shape)
        return original_zeros(shape, *args, **kwargs)

    monkeypatch.setattr(oem.np, "zeros", track_zeros)
    retained = oem.CcsdsOem._read_oem_impl(io.StringIO(source))
    assert len(retained[4]) == 1
    assert (6, 6) in allocations
    allocations.clear()
    discarded = oem.CcsdsOem._read_oem_impl(
        io.StringIO(source), retain_covariances=False
    )
    assert discarded[4] == []
    assert (6, 6) not in allocations
    assert retained[0:2] == discarded[0:2]
    np.testing.assert_array_equal(retained[3][0][1], discarded[3][0][1])


@pytest.mark.parametrize("retain_covariances", [True, False])
def test_assignment_detection_skips_non_assignment_lines(
    monkeypatch, retain_covariances: bool
) -> None:
    original = oem.odm.parse_kvn_assignment
    assignments = []

    def parse_assignment(line: str):
        assignments.append(line)
        return original(line)

    monkeypatch.setattr(oem.odm, "parse_kvn_assignment", parse_assignment)
    oem.CcsdsOem._read_oem_impl(
        io.StringIO(_PREFIX + _EPOCH + _ROWS + "COVARIANCE_STOP\n"),
        retain_covariances=retain_covariances,
    )
    assert assignments
    assert all("=" in line for line in assignments)
