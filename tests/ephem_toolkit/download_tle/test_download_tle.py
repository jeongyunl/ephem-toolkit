"""Tests for src/download_tle/download_tle.py — TLE download utility script."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from ephem_toolkit.download_tle import __main__ as download_tle_entry
from ephem_toolkit.download_tle.download_tle_cli import (
    build_arg_parser,
    parse_arguments,
)


def test_download_tle_help_uses_command_name_and_positional_satellite_ids() -> None:
    """The CLI help should show positional satellite IDs."""
    captured_output = io.StringIO()

    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass

    # Capture help output by redirecting stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output
    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    help_text = captured_output.getvalue()
    assert "usage: download-tle" in help_text
    assert "<id> [<id> ...]" in help_text


def test_safe_name_normalizes_satellite_names() -> None:
    assert download_tle_entry.safe_name("ISS (ZARYA)") == "ISS-ZARYA"
    assert download_tle_entry.safe_name("A   B") == "A-B"


def test_main_downloads_format_alias_and_writes_named_file(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    responses = iter(
        [
            b"ISS (ZARYA)\n1 25544U\n2 25544\n",
            b"OMM DATA\n",
        ]
    )
    requested_urls = []

    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def read(self) -> bytes:
            return self.content

    def fake_urlopen(url: str) -> FakeResponse:
        requested_urls.append(url)
        return FakeResponse(next(responses))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    download_tle_entry.main(["--format", "omm", "1998-067A"])

    output_path = tmp_path / "ISS-ZARYA_1998-067A.omm"
    assert output_path.read_text(encoding="utf-8") == "OMM DATA\n"
    assert "FORMAT=3le" in requested_urls[0]
    assert "FORMAT=kvn" in requested_urls[1]
    assert "Saved ISS-ZARYA_1998-067A.omm" in capsys.readouterr().out


def test_main_reports_network_errors_without_raising(monkeypatch, capsys) -> None:
    def fail_urlopen(_url: str) -> None:
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)

    download_tle_entry.main(["1998-067A"])

    assert "Error downloading data for 1998-067A: offline" in capsys.readouterr().out
