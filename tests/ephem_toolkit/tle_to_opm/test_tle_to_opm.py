"""Tests for the TLE-to-OPM numerical wrapper."""

import io
import json
import sys
from pathlib import Path

import pytest
from types import SimpleNamespace

import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.core.tle as tle
import ephem_toolkit.tle_to_opm as tle_package
import ephem_toolkit.tle_to_opm.__main__ as tle_wrapper
from ephem_toolkit.tle_to_opm.__main__ import main


def test_tle_to_opm_requires_numerical_fit_model() -> None:
    with pytest.raises(SystemExit) as error:
        main(["input.tle", "-o", "output.opm"])

    assert error.value.code == 2


def test_tle_to_opm_preserves_identity_and_records_sgp4_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(__file__).parents[2] / "data" / "ISS-ZARYA_1998-067A.tle"
    tle_data = tle.read_tle(source)
    output_path = tmp_path / "converted.opm"
    fit_report = tmp_path / "converted.fit.json"
    original_oem_to_opm_main = tle_wrapper.oem_to_opm_main
    intermediate_oems = []

    def capture_intermediate_oem(*args) -> None:
        serialized_oem = sys.stdin.read()
        intermediate_oems.append(oem.CcsdsOem.read(io.StringIO(serialized_oem)))
        sys.stdin = io.StringIO(serialized_oem)
        original_oem_to_opm_main(*args)

    monkeypatch.setattr(tle_wrapper, "oem_to_opm_main", capture_intermediate_oem)

    main(
        [
            str(source),
            "--fit-model",
            "numerical",
            "--fit-span",
            "2h",
            "--fit-report",
            str(fit_report),
            "--output",
            str(output_path),
        ]
    )

    converted_opm = opm.CcsdsOpm.from_source(output_path)
    intermediate_oem = intermediate_oems[0]
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    first_epoch = time_utils.tt_s_to_datetime(intermediate_oem.states[0][0])
    last_epoch = time_utils.tt_s_to_datetime(intermediate_oem.states[-1][0])
    assert intermediate_oem.meta.object_name == tle_data.object_name
    assert intermediate_oem.meta.object_id == tle_data.get_object_id()
    assert intermediate_oem.meta.center_name.lower() == "earth"
    assert intermediate_oem.meta.ref_frame == "EME2000"
    assert intermediate_oem.meta.time_system == "UTC"
    assert any("source=TLE" in comment for comment in intermediate_oem.meta.comments)
    assert any("target_model=SGP4" in comment for comment in intermediate_oem.meta.comments)
    assert intermediate_oem.header.originator == "ephem-toolkit"
    assert intermediate_oem.header.creation_date
    assert abs(
        time_utils.iso8601_to_datetime(intermediate_oem.meta.start_time) - first_epoch
    ) <= time_utils.timedelta(milliseconds=1)
    assert abs(
        time_utils.iso8601_to_datetime(intermediate_oem.meta.stop_time) - last_epoch
    ) <= time_utils.timedelta(milliseconds=1)
    assert converted_opm.metadata["OBJECT_NAME"] == tle_data.object_name
    assert converted_opm.metadata["OBJECT_ID"] == tle_data.get_object_id()
    assert converted_opm.metadata["CENTER_NAME"] == "EARTH"
    assert converted_opm.metadata["REF_FRAME"] == "EME2000"
    assert converted_opm.metadata["TIME_SYSTEM"] == "UTC"
    assert converted_opm.header.originator == "oem_to_opm"
    assert converted_opm.header.creation_date
    assert any("source=TLE" in comment for comment in converted_opm.header.comments)
    assert any(
        "source=OEM/sgp4" in comment for comment in converted_opm.header.comments
    )
    assert report["provenance"]["source"] == "OEM/sgp4"
    assert report["provenance"]["target_model"] == "numerical-propagator"


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
