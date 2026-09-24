"""Tests for src/tle_info/tle_info.py — TLE information utility script."""

from __future__ import annotations

import io
import sys
import builtins
import warnings
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
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


def test_main_prints_tle_summary_with_fake_tudatpy(
    monkeypatch, tmp_path, capsys
) -> None:
    def module(name, **attributes):
        result = ModuleType(name)
        for key, value in attributes.items():
            setattr(result, key, value)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    class FakeDateTime:
        @classmethod
        def from_epoch(cls, epoch):
            return cls()

        def to_iso_string(self, number_of_digits_seconds):
            return f"2025-01-01T00:00:00.{number_of_digits_seconds}"

    indices = SimpleNamespace(
        semi_major_axis_index=0,
        eccentricity_index=1,
        inclination_index=2,
        argument_of_periapsis_index=3,
        longitude_of_ascending_node_index=4,
        true_anomaly_index=5,
    )
    tle = SimpleNamespace(
        norad_catalog_number=12345,
        element_set_number=7,
        revolution_number_at_epoch=99,
        reference_epoch=123.0,
        b_star=0.0001,
        inclination=0.5,
        right_ascension=0.6,
        eccentricity=0.01,
        argument_of_perigee=0.7,
        mean_anomaly=0.8,
        mean_motion=0.001,
        raw_line_2=" " * 52 + "15.50000000",
        mean_motion_first_derivative=0.0,
        mean_motion_second_derivative=0.0,
    )
    ephemeris = SimpleNamespace(
        tle=tle,
        cartesian_state=lambda _epoch: np.array([7000, 0, 0, 0, 7, 1], dtype=float),
    )
    fake_environment = SimpleNamespace(
        get_default_body_settings=lambda *_args: object(),
        create_system_of_bodies=lambda _settings: SimpleNamespace(
            get=lambda _name: SimpleNamespace(gravitational_parameter=3.986e14)
        ),
        ephemeris=SimpleNamespace(sgp4=lambda *_args: object()),
        create_body_ephemeris=lambda *_args, **_kwargs: ephemeris,
    )

    module("tudatpy")
    module("tudatpy.astro")
    module("tudatpy.astro.element_conversion", KeplerianElementIndices=indices)
    module("tudatpy.astro.time_representation", DateTime=FakeDateTime)
    module("tudatpy.dynamics", environment_setup=fake_environment)
    module("tudatpy.interface")
    module(
        "tudatpy.interface.spice",
        get_approximate_utc_from_tdb=lambda epoch: f"utc:{epoch}",
    )
    module(
        "ephem_toolkit.core.propagator.kepler",
        cartesian_to_keplerian=lambda *_args: np.array(
            [7.0e6, 0.01, 0.5, 0.7, 0.6, 0.8]
        ),
    )
    module("ephem_toolkit.core.spice_utils", load_kernel=lambda _path: None)

    tle_file = tmp_path / "sample.tle"
    tle_file.write_text("name\n1 line\n2 line\n", encoding="utf-8")
    tle_info_entry.main([str(tle_file)])

    output = capsys.readouterr().out
    assert "NORAD catalog number: 12345" in output
    assert "Mean Motion: 15.50 revolutions per day" in output
    assert "Semi-major axis:" in output
