import sys
from datetime import timedelta
from io import StringIO
from pathlib import Path

import numpy as np
import pytest

import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.propagator.dsst as dsst
import ephem_toolkit.core.propagator.brouwer_j2 as brouwer
import ephem_toolkit.core.provenance as provenance
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.oem_to_omm as oem_to_omm
import ephem_toolkit.oem_to_omm.__main__ as oem_to_omm_entry
import ephem_toolkit.oem_to_omm.fit_brouwer as fit_brouwer
import ephem_toolkit.oem_to_omm.fit_tle_main as fit_tle
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
            "--verbose",
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


def test_parse_arguments_accepts_canonical_fit_model(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["oem-to-omm", "--fit-model", "sgp4", "input.oem", "--output", "-"],
    )

    args = oem_to_omm_cli.parse_arguments(oem_to_omm_cli.build_arg_parser())

    assert args.fit_model == "sgp4"
    assert args.mode == "tle"


def test_parse_arguments_rejects_conflicting_fit_model_and_mode(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--fit-model",
            "brouwer",
            "--mode",
            "tle",
            "input.oem",
            "--output",
            "-",
        ],
    )

    with pytest.raises(SystemExit) as error:
        oem_to_omm_cli.parse_arguments(oem_to_omm_cli.build_arg_parser())

    assert error.value.code == 2


def test_parse_arguments_accepts_provenance_report_options(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--source-model",
            "sgp4",
            "--source-report",
            "source.json",
            "--fit-report",
            "fit.json",
            "input.oem",
            "--output",
            "output.omm",
        ],
    )

    args = oem_to_omm_cli.parse_arguments(oem_to_omm_cli.build_arg_parser())

    assert args.source_model == "sgp4"
    assert args.source_report == "source.json"
    assert args.fit_report == "fit.json"


def test_parse_arguments_accepts_no_fit_report(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["oem-to-omm", "--no-fit-report", "input.oem", "-o", "output.omm"]
    )
    args = oem_to_omm_cli.parse_arguments(oem_to_omm_cli.build_arg_parser())
    assert args.no_fit_report is True


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
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(
        fit_brouwer,
        "fit_brouwer",
        lambda *_args, **_kwargs: (
            np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            {"status": "ok"},
        ),
    )
    monkeypatch.setattr(
        fit_brouwer,
        "compute_brouwer_propagation_comparison",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        fit_brouwer,
        "format_brouwer_output",
        lambda *_args, **_kwargs: "MEAN_OUTPUT",
    )
    monkeypatch.setattr(
        brouwer,
        "brouwer_mean_to_osculating",
        lambda *_args, **_kwargs: np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
    )

    dummy_omm = DummyOmmObj()
    monkeypatch.setattr(omm, "keplerian_to_omm", lambda *_args, **_kwargs: dummy_omm)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oem-to-omm",
            "--mode",
            "brouwer",
            "--fit-span",
            "90m",
            "--verbose",
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
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(
        fit_tle,
        "fit_tle",
        lambda *_args, **_kwargs: ({}, {"status": "ok"}),
    )
    monkeypatch.setattr(
        fit_tle,
        "compute_tle_propagation_comparison",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        fit_tle,
        "format_tle_output",
        lambda *_args, **_kwargs: "TLE_OUTPUT",
    )

    dummy_omm = DummyOmmObj()
    monkeypatch.setattr(convert_tle, "tle_to_omm", lambda *_args, **_kwargs: dummy_omm)

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


def test_main_dsst_mode_fits_and_writes_omm_to_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    states = [
        (0.0, np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])),
        (600.0, np.array([6999.0, 1.0, 0.0, 0.0, 7.5, 0.0])),
    ]
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(dsst, "DsstPerturbations", lambda **_kwargs: object())
    diagnostics = {"span_s": 600.0, "n_records": 2, "rms_position_m": 12.0}
    fit_calls = []
    mean_elements = np.arange(6, dtype=float)
    monkeypatch.setattr(
        fit_brouwer,
        "fit_dsst_mean_elements",
        lambda fit_states, span, mu, perturbations: fit_calls.append(
            (fit_states, span, mu, perturbations)
        )
        or (mean_elements, diagnostics),
    )
    monkeypatch.setattr(time_utils, "tt_s_to_datetime", lambda _epoch: "fit epoch")
    monkeypatch.setattr(
        provenance, "resolve_source_model", lambda *_args: ("SGP4", None)
    )
    monkeypatch.setattr(
        provenance, "provenance_comment", lambda **_kwargs: "PROVENANCE"
    )
    monkeypatch.setattr(provenance, "fit_comment", lambda **_kwargs: "FIT SUMMARY")
    dummy_omm = DummyOmmObj()
    converted = []
    monkeypatch.setattr(
        omm,
        "keplerian_to_omm",
        lambda epoch, elements, **kwargs: converted.append((epoch, elements, kwargs))
        or dummy_omm,
    )

    oem_to_omm.main(["--mode", "dsst", "--no-fit-report", "input.oem", "--output", "-"])

    captured = capsys.readouterr()
    assert captured.out == "OMM_OUTPUT"
    assert len(fit_calls) == 1
    assert fit_calls[0][0] is states
    assert fit_calls[0][1] == 7_200.0
    assert fit_calls[0][3] is not None
    assert converted[0][0] == "fit epoch"
    assert converted[0][1] is mean_elements
    assert dummy_omm.originator == "oem_to_omm"
    assert "DSST mean elements (J2 secular fit)" in dummy_omm.comments


@pytest.mark.parametrize(
    ("states", "argv", "error"),
    [
        (
            [],
            ["--mode", "dsst", "input.oem", "--no-fit-report"],
            "At least 2 state vectors",
        ),
        (
            [(0.0, np.ones(6)), (1.0, np.ones(6))],
            [
                "--mode",
                "dsst",
                "input.oem",
                "--no-fit-report",
                "--source-model",
                "invalid",
            ],
            "source model",
        ),
        (
            [(0.0, np.ones(6)), (1.0, np.ones(6))],
            [
                "--mode",
                "dsst",
                "input.oem",
                "--fit-report",
                "fit.json",
                "--no-fit-report",
            ],
            "cannot be used together",
        ),
    ],
)
def test_main_rejects_invalid_input_and_report_options(
    monkeypatch, states, argv, error
):
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    if "--source-model" in argv:
        monkeypatch.setattr(
            provenance,
            "resolve_source_model",
            lambda *_args: (_ for _ in ()).throw(ValueError("invalid source model")),
        )

    with pytest.raises(SystemExit):
        oem_to_omm.main(argv + ["--output", "-"])


def test_main_reports_missing_input_file(tmp_path, capsys):
    missing_input = tmp_path / "missing.oem"

    with pytest.raises(SystemExit):
        oem_to_omm.main(
            ["--mode", "dsst", str(missing_input), "--no-fit-report", "--output", "-"]
        )

    assert "Input file not found" in capsys.readouterr().err


def test_main_reads_oem_from_stdin(monkeypatch):
    stdin = StringIO("piped OEM")
    states = [(0.0, np.ones(6))]
    sources = []
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda source: sources.append(source) or DummyOemData(states, DummyMeta()),
    )

    with pytest.raises(SystemExit, match="1"):
        oem_to_omm.main(["--mode", "dsst", "-", "--no-fit-report", "--output", "-"])

    assert sources == [stdin]


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--norad-cat-id", "-1", "norad-cat-id"),
        ("--ephemeris-type", "10", "ephemeris-type"),
        ("--element-set-no", "10000", "element-set-no"),
        ("--rev-at-epoch", "100000", "rev-at-epoch"),
    ],
)
def test_main_rejects_out_of_range_tle_metadata(
    monkeypatch, capsys, option, value, message
):
    states = [(0.0, np.ones(6)), (1.0, np.ones(6))]
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(
        provenance, "resolve_source_model", lambda *_args: ("SGP4", None)
    )

    with pytest.raises(SystemExit):
        oem_to_omm.main(
            [
                "--mode",
                "tle",
                "input.oem",
                "--no-fit-report",
                "--output",
                "-",
                option,
                value,
            ]
        )

    assert message in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["dsst", "brouwer", "tle"])
def test_main_reports_fitting_errors(monkeypatch, mode):
    states = [(0.0, np.ones(6)), (1.0, np.ones(6))]
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(
        provenance, "resolve_source_model", lambda *_args: ("SGP4", None)
    )
    if mode == "dsst":
        monkeypatch.setattr(dsst, "DsstPerturbations", lambda **_kwargs: object())
        monkeypatch.setattr(
            fit_brouwer,
            "fit_dsst_mean_elements",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fit failed")),
        )
    elif mode == "brouwer":
        monkeypatch.setattr(
            fit_brouwer,
            "fit_brouwer",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fit failed")),
        )
    else:
        monkeypatch.setattr(
            fit_tle,
            "fit_tle",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fit failed")),
        )

    with pytest.raises(SystemExit):
        oem_to_omm.main(
            ["--mode", mode, "input.oem", "--no-fit-report", "--output", "-"]
        )


def test_main_reports_dsst_omm_conversion_error(monkeypatch):
    states = [(0.0, np.ones(6)), (1.0, np.ones(6))]
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_args, **_kwargs: DummyOemData(states, DummyMeta()),
    )
    monkeypatch.setattr(dsst, "DsstPerturbations", lambda **_kwargs: object())
    monkeypatch.setattr(
        fit_brouwer,
        "fit_dsst_mean_elements",
        lambda *_args, **_kwargs: (np.arange(6, dtype=float), {}),
    )
    monkeypatch.setattr(time_utils, "tt_s_to_datetime", lambda _epoch: "fit epoch")
    monkeypatch.setattr(
        provenance, "resolve_source_model", lambda *_args: ("SGP4", None)
    )
    monkeypatch.setattr(
        omm,
        "keplerian_to_omm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("conversion failed")
        ),
    )

    with pytest.raises(SystemExit):
        oem_to_omm.main(
            [
                "--mode",
                "dsst",
                "input.oem",
                "--object-id",
                "2000-001A",
                "--no-fit-report",
                "--output",
                "-",
            ]
        )


def test_cli_forwards_main_and_argv(monkeypatch):
    calls = []
    monkeypatch.setattr(
        core_cli, "run_cli", lambda main, argv: calls.append((main, argv)) or 7
    )
    argv = ["input.oem", "--output", "output.omm"]

    assert oem_to_omm.cli(argv) == 7
    assert calls == [(oem_to_omm.main, argv)]


def test_entry_cli_uses_shared_runner(monkeypatch):
    calls = []
    monkeypatch.setattr(
        core_cli, "run_cli", lambda main, argv: calls.append((main, argv)) or 8
    )

    assert oem_to_omm_entry.cli(["input.oem"]) == 8
    assert calls == [(oem_to_omm_entry.main, ["input.oem"])]
