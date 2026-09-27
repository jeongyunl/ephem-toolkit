"""Tests for the OMM-to-OPM numerical wrapper."""

import json
import pytest
from types import SimpleNamespace
from pathlib import Path

from ephem_toolkit.core.ccsds.omm import CcsdsOmm
from ephem_toolkit.core.ccsds.opm import CcsdsOpm
import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.omm_to_opm as omm_package
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


def test_omm_to_opm_preserves_source_comments_in_serialized_header(
    tmp_path: Path,
) -> None:
    source = (
        Path(__file__).parents[1] / "oem_to_tle" / "data" / "TEST-DSST_2020-001A.omm"
    )
    source_omm = CcsdsOmm.from_source(source)
    source_omm.comments.append("SOURCE_COMMENT: preserve through OMM-to-OPM")
    input_path = tmp_path / "source.omm"
    source_omm.to_file(input_path)
    output_path = tmp_path / "converted.opm"
    fit_report = tmp_path / "converted.fit.json"

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
    assert converted_opm.metadata["OBJECT_NAME"] == source_omm.object_name
    assert converted_opm.metadata["OBJECT_ID"] == source_omm.object_id
    assert converted_opm.metadata["CENTER_NAME"] == "EARTH"
    assert converted_opm.metadata["REF_FRAME"] == "EME2000"
    assert converted_opm.metadata["TIME_SYSTEM"] == "UTC"
    assert converted_opm.header.originator == "oem_to_opm"
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
