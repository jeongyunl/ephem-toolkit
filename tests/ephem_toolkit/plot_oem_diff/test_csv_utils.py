from pathlib import Path

from ephem_toolkit.plot_oem_diff.csv_utils import (
    generate_csv_path,
    sanitize_filename_component,
    write_csv,
)


def test_sanitize_filename_component_replaces_unsafe_characters() -> None:
    assert sanitize_filename_component("ISS / alpha:1") == "ISS___alpha_1"
    assert sanitize_filename_component("..__") == "data"
    assert sanitize_filename_component("sat-1.part_2") == "sat-1.part_2"


def test_generate_csv_path_uses_plot_directory_and_sanitized_parts() -> None:
    assert generate_csv_path(
        "reports/orbit.delta.png", "Δ position", "ISS / 1"
    ) == Path("reports/orbit.delta_Δ_position_ISS___1.csv")
    assert generate_csv_path(None, "position", "ISS") is None


def test_write_csv_creates_parent_and_writes_header_and_rows(tmp_path) -> None:
    destination = tmp_path / "nested" / "delta.csv"

    write_csv(destination, ["epoch", "dx"], [[1.5, 2], [2.5, 3]])

    assert destination.read_text(encoding="utf-8") == "epoch,dx\n1.5,2\n2.5,3\n"
