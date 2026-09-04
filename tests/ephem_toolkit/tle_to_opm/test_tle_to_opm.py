"""Tests for the TLE-to-OPM numerical wrapper."""

import pytest

from ephem_toolkit.tle_to_opm.__main__ import main


def test_tle_to_opm_requires_numerical_fit_model() -> None:
    with pytest.raises(SystemExit) as error:
        main(["input.tle", "-o", "output.opm"])

    assert error.value.code == 2
