"""Tests for the OEM-to-TLE command wrapper."""

from __future__ import annotations

from ephem_toolkit.oem_to_tle import __main__ as oem_to_tle


def test_main_delegates_to_oem_to_omm_in_tle_mode(monkeypatch) -> None:
    """The wrapper should add the TLE conversion mode and preserve arguments."""
    delegated_arguments: list[list[str]] = []

    def fake_main(argv) -> None:
        delegated_arguments.append(argv)

    monkeypatch.setattr(oem_to_tle.oem_to_omm, "main", fake_main)

    oem_to_tle.main(["input.oem", "-o", "output.omm", "--fit-span", "2h"])

    assert delegated_arguments == [
        ["--mode", "tle", "input.oem", "-o", "output.omm", "--fit-span", "2h"]
    ]


def test_main_replaces_existing_mode(monkeypatch) -> None:
    """The wrapper should force TLE mode when another mode is supplied."""
    delegated_arguments: list[list[str]] = []

    def fake_main(argv) -> None:
        delegated_arguments.append(argv)

    monkeypatch.setattr(oem_to_tle.oem_to_omm, "main", fake_main)

    oem_to_tle.main(["--mode", "brouwer", "input.oem"])

    assert delegated_arguments == [["--mode", "tle", "input.oem"]]
