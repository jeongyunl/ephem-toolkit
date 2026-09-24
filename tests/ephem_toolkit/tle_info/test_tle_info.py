"""Tests for src/tle_info/tle_info.py — TLE information utility script."""

from __future__ import annotations

import io
import sys
import builtins
import warnings
from types import SimpleNamespace

import pytest

import ephem_toolkit.tle_info.__main__ as tle_info_entry
from ephem_toolkit.tle_info.tle_info_cli import build_arg_parser, parse_arguments


def test_tle_info_help_uses_command_name() -> None:
    """The CLI help should use the canonical command name."""
    old_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    help_text = captured_output.getvalue()
    assert "usage: tle-info" in help_text


def test_get_tle_epoch_converts_tdb_epoch_to_datetime(monkeypatch) -> None:
    class FakeDateTime:
        @classmethod
        def from_epoch(cls, epoch: str) -> str:
            return f"datetime:{epoch}"

    monkeypatch.setattr(
        tle_info_entry,
        "spice",
        SimpleNamespace(get_approximate_utc_from_tdb=lambda epoch: f"utc:{epoch}"),
        raising=False,
    )
    monkeypatch.setattr(tle_info_entry, "DateTime", FakeDateTime, raising=False)

    epoch_datetime, epoch_tt_s = tle_info_entry.get_tle_epoch(
        SimpleNamespace(reference_epoch=1234.5)
    )

    assert epoch_datetime == "datetime:utc:1234.5"
    assert epoch_tt_s == 1234.5


def test_load_spice_kernels_requests_required_kernels(monkeypatch) -> None:
    loaded_kernels = []
    monkeypatch.setattr(
        tle_info_entry,
        "spice_utils",
        SimpleNamespace(load_kernel=loaded_kernels.append),
        raising=False,
    )

    tle_info_entry._load_spice_kernels()

    assert loaded_kernels == ["naif0012.tls", "pck00011.tpc"]


def test_main_reports_missing_tudatpy_dependency(monkeypatch) -> None:
    real_import = builtins.__import__

    def import_without_tudatpy(name, *args, **kwargs):
        if name.startswith("tudatpy"):
            raise ImportError("dependency unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_tudatpy)

    with warnings.catch_warnings():
        with pytest.raises(ImportError, match="tle-info requires tudatpy"):
            tle_info_entry.main(["orbit.tle"])
