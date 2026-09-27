"""Tests for the OMM-to-OPM numerical wrapper."""

import io
import json
from pathlib import Path
import sys
from datetime import timedelta
import numpy as np

import pytest
from types import SimpleNamespace

from ephem_toolkit.core.ccsds.omm import (
    CcsdsOmm,
    OmmCovariance,
    OmmSpacecraftParameters,
    TleParameters,
)
from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.core.ccsds.opm import CcsdsOpm
import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.omm_to_opm as omm_package
import ephem_toolkit.omm_to_opm.__main__ as omm_wrapper
from ephem_toolkit.omm_to_opm.__main__ import _forward_arguments, main


def _add_optional_omm_blocks(source_omm: CcsdsOmm) -> None:
    source_omm.classification = "C"
    source_omm.message_id = "OMM-SOURCE-MESSAGE"
    source_omm.ref_frame_epoch = "2024-01-01T00:00:00"
    source_omm.spacecraft_parameters = OmmSpacecraftParameters(
        mass=420.0,
        solar_rad_area=12.0,
        solar_rad_coeff=1.3,
        drag_area=10.0,
        drag_coeff=2.2,
    )
    source_omm.covariance = OmmCovariance(np.eye(6), ref_frame=source_omm.ref_frame)
    source_omm.data["USER_DEFINED_AUDIT"] = "OMM-only value"
    if source_omm.mean_element_theory.upper() in {"SGP4", "SGP/SGP4"}:
        source_omm.tle_parameters = TleParameters(
            ephemeris_type=2,
            classification_type="C",
            norad_cat_id=25544,
            element_set_no=1234,
            rev_at_epoch=56789,
            bstar="1.2345E-5",
            mean_motion_dot="2.5E-6",
            mean_motion_ddot="3.5E-7",
            bterm="4.5E-8",
            agom="5.5E-9",
        )


def _assert_optional_omm_blocks_omitted(output_path: Path, converted: CcsdsOpm) -> None:
    assert converted.spacecraft_parameters is None
    assert converted.covariance is None
    serialized = output_path.read_text(encoding="utf-8")
    for field in (
        "REF_FRAME_EPOCH",
        "MASS",
        "SOLAR_RAD_AREA",
        "SOLAR_RAD_COEFF",
        "DRAG_AREA",
        "DRAG_COEFF",
        "COV_REF_FRAME",
        "CX_X",
        "USER_DEFINED_AUDIT",
        "BSTAR",
        "BTERM",
        "AGOM",
        "EPHEMERIS_TYPE",
        "CLASSIFICATION_TYPE",
        "NORAD_CAT_ID",
        "ELEMENT_SET_NO",
        "REV_AT_EPOCH",
        "MEAN_MOTION_DOT",
        "MEAN_MOTION_DDOT",
    ):
        assert field not in serialized


def _capture_intermediate_oem(monkeypatch) -> list[CcsdsOem]:
    original_main = omm_wrapper.oem_to_opm_main
    captured = []

    def capture_and_delegate(*args) -> None:
        serialized_oem = sys.stdin.read()
        captured.append(CcsdsOem.read(io.StringIO(serialized_oem)))
        sys.stdin = io.StringIO(serialized_oem)
        original_main(*args)

    monkeypatch.setattr(omm_wrapper, "oem_to_opm_main", capture_and_delegate)
    return captured


def test_sgp4_omm_to_opm_preserves_source_comments_in_serialized_header(
    tmp_path: Path, monkeypatch
) -> None:
    source = Path(__file__).parents[2] / "data" / "ISS-ZARYA_1998-067A.omm"
    source_omm = CcsdsOmm.from_source(source)
    source_omm.comments.append("SOURCE_COMMENT: SGP4 OMM to OPM")
    _add_optional_omm_blocks(source_omm)
    input_path = tmp_path / "source.omm"
    source_omm.to_file(input_path)
    parsed_source_omm = CcsdsOmm.from_source(input_path)
    assert parsed_source_omm.tle_parameters is not None
    assert parsed_source_omm.tle_parameters.ephemeris_type == 2
    assert parsed_source_omm.tle_parameters.classification_type == "C"
    assert parsed_source_omm.tle_parameters.norad_cat_id == 25544
    assert parsed_source_omm.tle_parameters.element_set_no == 1234
    assert parsed_source_omm.tle_parameters.rev_at_epoch == 56789
    for field in (
        "bstar",
        "mean_motion_dot",
        "mean_motion_ddot",
        "bterm",
        "agom",
    ):
        assert float(getattr(parsed_source_omm.tle_parameters, field)) == pytest.approx(
            float(getattr(source_omm.tle_parameters, field))
        )
    output_path = tmp_path / "converted.opm"
    fit_report = tmp_path / "converted.fit.json"
    intermediate_oems = _capture_intermediate_oem(monkeypatch)

    main(
        [
            str(input_path),
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

    converted_opm = CcsdsOpm.from_source(output_path)
    intermediate_oem = intermediate_oems[0]
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    start = time_utils.iso8601_to_datetime(parsed_source_omm.epoch)
    assert intermediate_oem.meta.object_name == source_omm.object_name
    assert intermediate_oem.meta.object_id == source_omm.object_id
    assert intermediate_oem.meta.center_name == "EARTH"
    assert intermediate_oem.meta.ref_frame == "EME2000"
    assert intermediate_oem.meta.time_system == "UTC"
    assert intermediate_oem.header.classification == source_omm.classification
    assert intermediate_oem.header.message_id == source_omm.message_id
    assert intermediate_oem.header.originator == "ephem-toolkit"
    assert intermediate_oem.header.creation_date
    assert intermediate_oem.header.creation_date != source_omm.creation_date
    assert abs(
        time_utils.iso8601_to_datetime(intermediate_oem.meta.start_time) - start
    ) <= timedelta(milliseconds=1)
    assert abs(
        time_utils.iso8601_to_datetime(intermediate_oem.meta.stop_time)
        - (start + timedelta(hours=2))
    ) <= timedelta(milliseconds=1)
    assert converted_opm.metadata["OBJECT_NAME"] == source_omm.object_name
    assert converted_opm.metadata["OBJECT_ID"] == source_omm.object_id
    assert converted_opm.metadata["CENTER_NAME"] == "EARTH"
    assert converted_opm.metadata["REF_FRAME"] == "EME2000"
    assert converted_opm.metadata["TIME_SYSTEM"] == "UTC"
    assert converted_opm.header.classification == source_omm.classification
    assert converted_opm.header.message_id == source_omm.message_id
    _assert_optional_omm_blocks_omitted(output_path, converted_opm)
    assert "SOURCE_COMMENT: SGP4 OMM to OPM" in converted_opm.header.comments
    assert any("source=OMM" in comment for comment in converted_opm.header.comments)
    assert report["provenance"]["target_model"] == "numerical-propagator"
    assert (
        "SOURCE_COMMENT: SGP4 OMM to OPM" in report["configuration"]["source_comments"]
    )


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


def test_omm_to_opm_preserves_source_comments_in_serialized_header(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        Path(__file__).parents[1] / "oem_to_tle" / "data" / "TEST-DSST_2020-001A.omm"
    )
    source_omm = CcsdsOmm.from_source(source)
    source_omm.comments.append("SOURCE_COMMENT: preserve through OMM-to-OPM")
    _add_optional_omm_blocks(source_omm)
    input_path = tmp_path / "source.omm"
    source_omm.to_file(input_path)
    output_path = tmp_path / "converted.opm"
    fit_report = tmp_path / "converted.fit.json"
    intermediate_oems = _capture_intermediate_oem(monkeypatch)

    main(
        [
            str(input_path),
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

    converted_opm = CcsdsOpm.from_source(output_path)
    intermediate_oem = intermediate_oems[0]
    start = time_utils.iso8601_to_datetime(source_omm.epoch)
    assert intermediate_oem.meta.object_name == source_omm.object_name
    assert intermediate_oem.meta.object_id == source_omm.object_id
    assert intermediate_oem.meta.center_name == "EARTH"
    assert intermediate_oem.meta.ref_frame == "EME2000"
    assert intermediate_oem.meta.time_system == "UTC"
    assert intermediate_oem.header.classification == source_omm.classification
    assert intermediate_oem.header.message_id == source_omm.message_id
    assert intermediate_oem.header.originator == "ephem-toolkit"
    assert intermediate_oem.header.creation_date
    assert intermediate_oem.header.creation_date != source_omm.creation_date
    assert abs(
        time_utils.iso8601_to_datetime(intermediate_oem.meta.start_time) - start
    ) <= timedelta(milliseconds=1)
    assert abs(
        time_utils.iso8601_to_datetime(intermediate_oem.meta.stop_time)
        - (start + timedelta(hours=2))
    ) <= timedelta(milliseconds=1)
    assert converted_opm.metadata["OBJECT_NAME"] == source_omm.object_name
    assert converted_opm.metadata["OBJECT_ID"] == source_omm.object_id
    assert converted_opm.metadata["CENTER_NAME"] == "EARTH"
    assert converted_opm.metadata["REF_FRAME"] == "EME2000"
    assert converted_opm.metadata["TIME_SYSTEM"] == "UTC"
    assert converted_opm.header.classification == source_omm.classification
    assert converted_opm.header.message_id == source_omm.message_id
    assert converted_opm.header.originator == "oem_to_opm"
    assert converted_opm.header.creation_date
    _assert_optional_omm_blocks_omitted(output_path, converted_opm)
    assert (
        "SOURCE_COMMENT: preserve through OMM-to-OPM" in converted_opm.header.comments
    )
    assert any(
        "source=OMM/DSST" in comment for comment in converted_opm.header.comments
    )
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert report["provenance"]["source"] == "OEM/DSST"
    assert (
        report["configuration"]["source_comments"] == converted_opm.header.comments[:2]
    )


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


def test_main_uses_sys_argv_and_kepler_dispatch(monkeypatch) -> None:
    import sys

    import ephem_toolkit.propagate_omm.propagation as propagation

    source = SimpleNamespace(
        epoch="2026-01-01T00:00:00.000000",
        mean_element_theory="KEPLER",
        tle_parameters=None,
    )
    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["omm-to-opm", "input.omm", "--fit-model", "numerical", "-o", "out.opm"],
    )
    monkeypatch.setattr(propagation, "read_omm_input", lambda _path: source)
    monkeypatch.setattr(
        propagation, "propagate_omm_kepler", lambda *_args: print("generated OEM")
    )
    monkeypatch.setattr(omm_wrapper, "oem_to_opm_main", lambda args: calls.append(args))

    main()

    assert calls[0][:3] == ["--fit-model", "numerical", "-"]
    assert "--source-model" in calls[0]


def test_package_entry_points_forward_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(omm_wrapper, "main", lambda argv: calls.append(("main", argv)))
    monkeypatch.setattr(
        omm_wrapper, "cli", lambda argv: calls.append(("cli", argv)) or 3
    )

    assert omm_package.main(["input.omm"]) is None
    assert omm_package.cli(["input.omm"]) == 3
    assert calls == [("main", ["input.omm"]), ("cli", ["input.omm"])]


def test_cli_forwards_to_shared_runner(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        core_cli, "run_cli", lambda main, argv: calls.append((main, argv)) or 5
    )

    assert omm_wrapper.cli(["input.omm"]) == 5
    assert calls == [(omm_wrapper.main, ["input.omm"])]
