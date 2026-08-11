"""CSV utilities for orbit delta plotting."""

from __future__ import annotations

import csv
from pathlib import Path


def sanitize_filename_component(value: str) -> str:
    """Sanitize a string for safe use as a filename component.

    Parameters
    ----------
    value : str
        String to sanitize.

    Returns
    -------
    str
        Sanitized string safe for use in filenames.
    """
    safe: list[str] = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")

    result: str = "".join(safe).strip("._")
    return result or "data"


def write_csv(dest: Path, header: list[str], rows: list[list[object]]) -> None:
    """Write rows to CSV with a header.

    Parameters
    ----------
    dest : Path
        Output CSV file path.
    header : list[str]
        Column header names.
    rows : list[list[object]]
        Data rows to write.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(header)
        writer.writerows(rows)


def generate_csv_path(
    output_file: str | None,
    plot_suffix: str,
    dataset_label: str,
) -> Path | None:
    """Generate a CSV output path derived from the plot output filename.

    Parameters
    ----------
    output_file : str | None
        Base output filename, or None to skip CSV generation.
    plot_suffix : str
        Suffix identifying the plot type.
    dataset_label : str
        Label identifying the dataset.

    Returns
    -------
    Path | None
        Generated CSV path, or None if output_file is None.
    """
    if output_file is None:
        return None

    out_path = Path(output_file)
    base_dir = out_path.parent
    base_stem = out_path.stem

    label_part = sanitize_filename_component(dataset_label)
    suffix_part = sanitize_filename_component(plot_suffix)

    return base_dir / f"{base_stem}_{suffix_part}_{label_part}.csv"
