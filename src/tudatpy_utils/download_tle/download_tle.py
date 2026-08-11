#!/usr/bin/env python3
"""Download TLE/OMM data from CelesTrak by international designator.

Provides a CLI entry point that fetches satellite data in the requested
format and saves each result to a named file.
"""

from __future__ import annotations

import argparse
import re
import urllib.parse
import urllib.request

FORMATS = {
    "tle": ".tle",
    "3le": ".tle",
    "2le": ".tle",
    "xml": ".xml",
    "kvn": ".omm",
    "omm": ".omm",
    "json": ".json",
    "json-pretty": ".json",
    "csv": ".csv",
}
"""Mapping of CelesTrak format names to output file extensions."""

FORMAT_ALIASES = {
    "omm": "kvn",
}
"""Aliases that map user-facing format names to CelesTrak API format tokens."""


# ===================================================================
# Utilities
# ===================================================================


def safe_name(name: str) -> str:
    """Escape a satellite name for use in a filename.

    Parameters
    ----------
    name : str
        Satellite name to escape.

    Returns
    -------
    str
        Escaped name suitable for use in a filename.
    """
    result = name.replace(" ", "-").replace("(", "-").replace(")", "")
    return re.sub(r"-+", "-", result)


# ===================================================================
# CLI entry point
# ===================================================================


def main() -> None:
    """Download TLE/OMM data from CelesTrak for each provided satellite designator.

    Parses CLI arguments, fetches data in the requested format, and saves each
    result to a file named after the satellite and its international designator.

    Returns
    -------
    None
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Download TLE/OMM data from CelesTrak"
    )
    parser.add_argument(
        "satellite_ids",
        nargs="+",
        help="One or more satellite international designators",
    )
    parser.add_argument(
        "--format",
        dest="format",
        default="tle",
        choices=FORMATS.keys(),
        help="Output format (default: tle). Valid options: "
        + ", ".join(FORMATS.keys()),
    )
    args: argparse.Namespace = parser.parse_args()

    satellite_ids: list[str] = args.satellite_ids
    output_format: str = FORMAT_ALIASES.get(args.format, args.format)
    print(f"Satellite IDs: {satellite_ids}")
    print(f"Format: {output_format}\n")

    for satellite_id in satellite_ids:
        print(f"Downloading data for {satellite_id}")

        # Encode satellite ID for URL
        encoded_id: str = urllib.parse.quote(satellite_id, safe="*")

        try:
            # Retrieve satellite name from 3LE format (first line is the name)
            name_url: str = (
                f"https://celestrak.org/NORAD/elements/gp.php?INTDES={encoded_id}&FORMAT=3le"
            )
            name_data: str = urllib.request.urlopen(name_url).read().decode("utf-8")
            lines: list[str] = name_data.strip().splitlines()
            if lines:
                satellite_name: str = lines[0].strip()
            else:
                satellite_name = satellite_id
            print(f"Satellite name: {satellite_name}")

            # Download the data in the requested format
            url: str = (
                f"https://celestrak.org/NORAD/elements/gp.php?INTDES={encoded_id}&FORMAT={output_format}"
            )
            data: str = urllib.request.urlopen(url).read().decode("utf-8")

            if not data.strip():
                print(f"No data found for {satellite_id}")
                continue

            # Save the data to a file
            ext: str = FORMATS[output_format]
            filename: str = f"{safe_name(satellite_name)}_{satellite_id}{ext}"
            with open(filename, "w") as f:
                f.write(data)

            print(f"Saved {filename}")
            print()

        except Exception as exception:
            print(f"Error downloading data for {satellite_id}: {exception}")


if __name__ == "__main__":
    main()
