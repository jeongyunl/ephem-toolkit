"""Tests for the OMM-to-OPM numerical wrapper."""

import pytest
from types import SimpleNamespace

import ephem_toolkit.omm_to_opm.__main__ as omm_wrapper
from ephem_toolkit.omm_to_opm.__main__ import _forward_arguments, main


def test_forward_arguments_replaces_input_output_and_fit_model() -> None:
    assert _forward_arguments(
        ["input.omm", "--fit-model", "numerical", "-o", "output.opm", "--verbose"],
        "input.omm",
        "-",
    ) == ["--verbose", "--output", "-"]


def test_forward_arguments_removes_input_after_options() -> None:
    assert _forward_arguments(
        ["--fit-model", "numerical", "input.omm", "-o", "output.opm"],
        "input.omm",
        "-",
    ) == ["--output", "-"]


def test_omm_to_opm_requires_numerical_fit_model() -> None:
    with pytest.raises(SystemExit) as error:
        main(["input.omm", "-o", "output.opm"])

    assert error.value.code == 2


def test_omm_to_opm_dispatches_declared_theory_and_delegates(monkeypatch) -> None:
    import ephem_toolkit.propagate_omm.propagation as propagation

    calls = []
    source = SimpleNamespace(
        epoch="2026-01-01T00:00:00.000000",
        mean_element_theory="DSST",
        tle_parameters=None,
    )
    monkeypatch.setattr(propagation, "read_omm_input", lambda _path: source)
    monkeypatch.setattr(
        propagation,
        "propagate_omm_dsst",
        lambda *_args: print("generated OEM"),
    )
    monkeypatch.setattr(
        omm_wrapper,
        "oem_to_opm_main",
        lambda args: calls.append((args, __import__("sys").stdin.read())),
    )

    main(
        [
            "input.omm",
            "--fit-model",
            "numerical",
            "--fit-report",
            "fit.json",
            "-o",
            "output.opm",
        ]
    )

    assert calls[0][0][:3] == ["--fit-model", "numerical", "-"]
    assert "--source-model" in calls[0][0]
    assert calls[0][0][calls[0][0].index("--source-model") + 1] == "DSST"
    assert calls[0][1] == "generated OEM\n"
