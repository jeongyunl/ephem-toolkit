"""Tests for the OMM-to-OPM numerical wrapper."""

import pytest

from ephem_toolkit.omm_to_opm.__main__ import _forward_arguments, main


def test_forward_arguments_replaces_input_output_and_fit_model() -> None:
    assert _forward_arguments(
        ["input.omm", "--fit-model", "numerical", "-o", "output.opm", "--verbose"],
        "input.omm",
        "-",
    ) == ["--verbose", "--output", "-"]


def test_omm_to_opm_requires_numerical_fit_model() -> None:
    with pytest.raises(SystemExit) as error:
        main(["input.omm", "-o", "output.opm"])

    assert error.value.code == 2
