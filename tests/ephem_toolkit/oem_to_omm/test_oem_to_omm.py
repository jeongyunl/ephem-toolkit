import sys
from datetime import timedelta
from io import StringIO
from pathlib import Path

import numpy as np
import pytest

import ephem_toolkit.oem_to_omm.__main__ as oem_to_omm
from ephem_toolkit.oem_to_omm import oem_to_omm_cli


class DummyMeta:
    def __init__(self, object_name="OBJ", object_id="UNKNOWN"):
        self.object_name = object_name
        self.object_id = object_id
        self.ref_frame = "ICRF"
        self.center_name = "EARTH"


class DummyOemData:
    def __init__(self, states, meta=None):
        self.states = states
        self.meta = meta or DummyMeta()


class DummyOmmObj:
    def __init__(self):
        self.originator = None
        self.comments = []
        self.output = ""

    def to_file(self, dest):
        if hasattr(dest, "write"):
            dest.write("OMM_OUTPUT")
        else:
            Path(dest).write_text("OMM_OUTPUT", encoding="utf-8")


def test_parse_arguments_fit_span_accepts_duration_strings(monkeypatch):
    """--fit-span should accept duration strings and store a timedelta."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "brouwer",
            "--fit-span",
            "90m",
            "input.oem",
            "--output",
            "-",
        ],
    )

    args = oem_to_omm_cli.parse_arguments(oem_to_omm_cli.build_arg_parser())

    assert args.fit_span == timedelta(minutes=90)


def test_parse_arguments_fit_span_default_is_two_hours(monkeypatch):
    """Default fit span should remain 2h when no override is provided."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "brouwer",
            "input.oem",
            "--output",
            "-",
        ],
    )

    args = oem_to_omm_cli.parse_arguments(oem_to_omm_cli.build_arg_parser())

    assert args.fit_span == timedelta(hours=2)


def test_report_results_handles_stdout_file_and_stream():
    """Should write text to stdout, files, or an already-open stream."""
    stream = StringIO()

    oem_to_omm.report_results("hello", "-", verbose=False)
    oem_to_omm.report_results("file-data", "tmp_report.txt")
    oem_to_omm.report_results("stream-data", stream)

    assert Path("tmp_report.txt").read_text(encoding="utf-8") == "file-data\n"
    assert stream.getvalue() == "stream-data"

    Path("tmp_report.txt").unlink(missing_ok=True)


def test_report_error_exits_with_code():
    """Should raise SystemExit with the provided exit code."""
    with pytest.raises(SystemExit) as excinfo:
        oem_to_omm.report_error("bad input", exit_code=7)

    assert excinfo.value.code == 7


def test_main_brouwer_mode_uses_duration_and_writes_omm(monkeypatch, tmp_path):
    """Brouwer mode should convert the fit duration to seconds and write OMM output."""
    states = [
        (0.0, np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0], dtype=float)),
        (600.0, np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0], dtype=float)),
    ]
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem_to_omm.oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(
        oem_to_omm.fit_brouwer,
        "fit_brouwer",
        lambda *_args, **_kwargs: (
            np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            {"status": "ok"},
        ),
    )
    monkeypatch.setattr(
        oem_to_omm.fit_brouwer,
        "compute_brouwer_propagation_comparison",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        oem_to_omm.fit_brouwer,
        "format_brouwer_output",
        lambda *_args, **_kwargs: "MEAN_OUTPUT",
    )
    monkeypatch.setattr(
        oem_to_omm.brouwer,
        "brouwer_mean_to_osculating",
        lambda *_args, **_kwargs: np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
    )

    dummy_omm = DummyOmmObj()
    monkeypatch.setattr(
        oem_to_omm.omm, "keplerian_to_omm", lambda *_args, **_kwargs: dummy_omm
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "brouwer",
            "--fit-span",
            "90m",
            "input.oem",
            "-o",
            str(tmp_path / "mean.omm"),
        ],
    )

    oem_to_omm.main()

    assert dummy_omm.originator == "oem_to_omm"
    assert Path(tmp_path / "mean.omm").read_text(encoding="utf-8") == "OMM_OUTPUT"


def test_main_tle_mode_writes_omm_from_duration(monkeypatch, tmp_path):
    """TLE mode should consume the timedelta-based fit span and write OMM output."""
    states = [
        (0.0, np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0], dtype=float)),
        (600.0, np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0], dtype=float)),
    ]
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem_to_omm.oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(
        oem_to_omm.fit_tle,
        "fit_tle",
        lambda *_args, **_kwargs: ({}, {"status": "ok"}),
    )
    monkeypatch.setattr(
        oem_to_omm.fit_tle,
        "compute_tle_propagation_comparison",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        oem_to_omm.fit_tle,
        "format_tle_output",
        lambda *_args, **_kwargs: "TLE_OUTPUT",
    )

    dummy_omm = DummyOmmObj()
    monkeypatch.setattr(
        oem_to_omm.convert_tle, "tle_to_omm", lambda *_args, **_kwargs: dummy_omm
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "tle",
            "--fit-span",
            "90m",
            "input.oem",
            "-o",
            str(tmp_path / "tle.omm"),
        ],
    )

    oem_to_omm.main()

    assert dummy_omm.originator == "oem_to_omm"
    assert Path(tmp_path / "tle.omm").read_text(encoding="utf-8") == "OMM_OUTPUT"
