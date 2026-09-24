"""Tests for the TLE-to-OPM numerical wrapper."""

import pytest
from types import SimpleNamespace

import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.tle_to_opm as tle_package
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


def test_package_entry_points_forward_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(tle_wrapper, "main", lambda argv: calls.append(("main", argv)))
    monkeypatch.setattr(
        tle_wrapper, "cli", lambda argv: calls.append(("cli", argv)) or 4
    )

    assert tle_package.main(["input.tle"]) is None
    assert tle_package.cli(["input.tle"]) == 4
    assert calls == [("main", ["input.tle"]), ("cli", ["input.tle"])]


def test_cli_forwards_to_shared_runner(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        core_cli,
        "run_cli",
        lambda main_func, argv: calls.append((main_func, argv)) or 6,
    )

    assert tle_wrapper.cli(["input.tle"]) == 6
    assert calls == [(tle_wrapper.main, ["input.tle"])]
