"""Tests for oem_to_tle/parse_cli_args.py — CLI argument parsing for OEM to TLE conversion."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oem_to_tle.parse_cli_args as parse_cli_args

# ===================================================================
# 1. Command-line argument parsing
# ===================================================================


def test_parse_arguments_with_defaults() -> None:
    """Should parse arguments with default values when no args provided."""
    with patch("sys.argv", ["oem_to_tle.py"]):
        args = parse_cli_args.parse_cli_arguments()

    assert args.input == "-"
    assert args.output == "-"
    assert args.satellite_number == 99999
    assert args.classification == "U"
    assert args.int_designator_year == 0
    assert args.int_designator_launch_number == 0
    assert args.int_designator_piece == "A"
    assert args.ephemeris_type == 0
    assert args.element_set_number == 1
    assert args.bstar == "00000+0"
    assert args.mean_motion_second_derivative == "00000+0"
    assert args.revolution_number_at_epoch == 0
    assert args.refinement == "cartesian"


def test_parse_arguments_with_input_file() -> None:
    """Should parse input file path correctly."""
    with patch("sys.argv", ["oem_to_tle.py", "test.oem"]):
        args = parse_cli_args.parse_cli_arguments()

    assert args.input == "test.oem"


def test_parse_arguments_with_output_file() -> None:
    """Should parse output file path with -o flag."""
    with patch("sys.argv", ["oem_to_tle.py", "-o", "output.tle"]):
        args = parse_cli_args.parse_cli_arguments()

    assert args.output == "output.tle"


def test_parse_arguments_with_satellite_metadata() -> None:
    """Should parse satellite metadata fields."""
    with patch(
        "sys.argv",
        [
            "oem_to_tle.py",
            "--name",
            "TEST SAT",
            "--satellite-number",
            "12345",
            "--classification",
            "C",
            "--int-designator-year",
            "23",
            "--int-designator-launch-number",
            "100",
            "--int-designator-piece",
            "B",
        ],
    ):
        args = parse_cli_args.parse_cli_arguments()

    assert args.name == "TEST SAT"
    assert args.satellite_number == 12345
    assert args.classification == "C"
    assert args.int_designator_year == 23
    assert args.int_designator_launch_number == 100
    assert args.int_designator_piece == "B"


def test_parse_arguments_with_tle_parameters() -> None:
    """Should parse TLE-specific parameters."""
    with patch(
        "sys.argv",
        [
            "oem_to_tle.py",
            "--bstar",
            "12345-3",
            "--mean-motion-second-derivative",
            "00000+0",
            "--ephemeris-type",
            "4",
            "--element-set-number",
            "999",
            "--revolution-number-at-epoch",
            "12345",
        ],
    ):
        args = parse_cli_args.parse_cli_arguments()

    assert args.bstar == "12345-3"
    assert args.mean_motion_second_derivative == "00000+0"
    assert args.ephemeris_type == 4
    assert args.element_set_number == 999
    assert args.revolution_number_at_epoch == 12345


def test_parse_arguments_with_refinement_methods() -> None:
    """Should parse different refinement method options."""
    for method in ["none", "cartesian", "keplerian"]:
        with patch("sys.argv", ["oem_to_tle.py", "--refinement", method]):
            args = parse_cli_args.parse_cli_arguments()
            assert args.refinement == method
