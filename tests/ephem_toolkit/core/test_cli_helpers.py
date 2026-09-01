"""Tests for shared CLI helper conventions."""

from __future__ import annotations


import pytest

from ephem_toolkit.core.cli import (
    PACKAGE_NAME,
    PACKAGE_VERSION,
    add_common_arguments,
    build_arg_parser,
)


def test_build_arg_parser_uses_lowercase_placeholders() -> None:
    """Shared CLI helpers should render descriptive lowercase placeholders."""
    parser = build_arg_parser("demo tool")
    add_common_arguments(parser, positional_name="input_oem")

    help_text = parser.format_help()
    assert "input_oem" in help_text
    assert "<input_oem|->" in help_text
    assert "--output <path|->" in help_text
    assert "'-'" in help_text
    assert "stdout" in help_text
    assert "--duration <duration>" in help_text
    assert "--start <timestamp|duration>" in help_text
    assert "ISO-8601" in help_text
    assert "2001-11-06T11:17:33" in help_text
    assert "2001-11-06T11:17:33.1234" in help_text
    assert "--stop <timestamp|duration>" in help_text
    assert "--verbose" in help_text
    assert "--debug" in help_text
    assert "--version" in help_text
    assert f"{PACKAGE_NAME} {PACKAGE_VERSION}" in help_text


def test_build_arg_parser_supports_version(capsys) -> None:
    """The shared parser should report the installed package version."""
    parser = build_arg_parser("demo tool")

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"{parser.prog} {PACKAGE_VERSION}\n"


def test_build_arg_parser_adds_package_footer_without_epilog() -> None:
    """The package identity should appear even when a command has no epilog."""
    parser = build_arg_parser("demo tool")

    assert f"{PACKAGE_NAME} {PACKAGE_VERSION}" in parser.format_help()


def test_build_arg_parser_supports_format_aware_output_name() -> None:
    """Output arguments should support format-aware dest names when needed."""
    parser = build_arg_parser("demo tool")
    add_common_arguments(parser, positional_name="input_oem", output_name="output_tle")

    args = parser.parse_args(["input.oem", "--output", "out.tle"])
    assert args.output_tle == "out.tle"


def test_build_arg_parser_accepts_help_footer() -> None:
    """Parser factories should keep a consistent help footer."""
    parser = build_arg_parser("demo tool", epilog="examples:\n  demo --output out.csv")
    assert "examples:" in parser.format_help()
