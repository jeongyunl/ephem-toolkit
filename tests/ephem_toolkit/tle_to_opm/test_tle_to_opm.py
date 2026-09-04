"""Tests for the TLE-to-OPM numerical wrapper."""

import pytest
from types import SimpleNamespace

import ephem_toolkit.tle_to_opm.__main__ as tle_wrapper
from ephem_toolkit.tle_to_opm.__main__ import main


def test_tle_to_opm_requires_numerical_fit_model() -> None:
    with pytest.raises(SystemExit) as error:
        main(["input.tle", "-o", "output.opm"])

    assert error.value.code == 2


def test_tle_to_opm_dispatches_sgp4_and_delegates(monkeypatch) -> None:
    import ephem_toolkit.propagate_omm.propagation as propagation

    calls = []
    tle_data = SimpleNamespace(epoch_year=26, epoch_day=1.0)
    monkeypatch.setattr(propagation, "read_tle_input", lambda _path: tle_data)
    monkeypatch.setattr(
        propagation,
        "propagate_tle_sgp4",
        lambda *_args: print("generated OEM"),
    )
    monkeypatch.setattr(
        tle_wrapper,
        "oem_to_opm_main",
        lambda args: calls.append((args, __import__("sys").stdin.read())),
    )

    main(["input.tle", "--fit-model", "numerical", "-o", "output.opm"])

    assert calls[0][0][:3] == ["--fit-model", "numerical", "-"]
    assert calls[0][0][-2:] == ["--source-model", "sgp4"]
    assert calls[0][1] == "generated OEM\n"
