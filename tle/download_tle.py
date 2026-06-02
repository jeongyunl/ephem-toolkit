#!/usr/bin/env python3


import argparse
import re
import sys
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

FORMAT_ALIASES = {
    "omm": "kvn",
}


def safe_name(name: str) -> str:
    """Escape a satellite name for use in a filename."""
    result = name.replace(" ", "-").replace("(", "-").replace(")", "")
    return re.sub(r"-+", "-", result)


def main():
    parser = argparse.ArgumentParser(description="Download TLE/OMM data from CelesTrak")
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
        help="Output format (default: tle). Valid options: " + ", ".join(FORMATS.keys()),
    )
    args = parser.parse_args()

    satellite_ids = args.satellite_ids
    output_format = FORMAT_ALIASES.get(args.format, args.format)
    print(f"Satellite IDs: {satellite_ids}")
    print(f"Format: {output_format}\n")

    for satellite_id in satellite_ids:
        print(f"Downloading data for {satellite_id}")

        # Encode satellite ID for URL
        encoded_id = urllib.parse.quote(satellite_id, safe="*")

        try:
            # Retrieve satellite name from 3LE format (first line is the name)
            name_url = f"https://celestrak.org/NORAD/elements/gp.php?INTDES={encoded_id}&FORMAT=3le"
            name_data = urllib.request.urlopen(name_url).read().decode("utf-8")
            lines = name_data.strip().splitlines()
            if lines:
                satellite_name = lines[0].strip()
            else:
                satellite_name = satellite_id
            print(f"Satellite name: {satellite_name}")

            # Download the data in the requested format
            url = f"https://celestrak.org/NORAD/elements/gp.php?INTDES={encoded_id}&FORMAT={output_format}"
            data = urllib.request.urlopen(url).read().decode("utf-8")

            if not data.strip():
                print(f"No data found for {satellite_id}")
                continue

            # Save the data to a file
            ext = FORMATS[output_format]
            filename = f"{safe_name(satellite_name)}_{satellite_id}{ext}"
            with open(filename, "w") as f:
                f.write(data)

            print(f"Saved {filename}")
            print()

        except Exception as e:
            print(f"Error downloading data for {satellite_id}: {e}")


if __name__ == "__main__":
    main()
