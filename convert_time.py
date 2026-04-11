#!/usr/bin/env python3

import argparse
import sys
from typing import Iterable

from tudatpy.astro.time_representation import DateTime
from enum import StrEnum


class TimeFormat(StrEnum):
    UTC_ISO = "iso"  # ISO 8601 format: "YYYY-MM-DDTHH:MM:SS.sss"
    UTC_YMDHMS = "ymdhms"  # Year, Month, Day, Hour, Minute, Seconds format: "YYYY,MM,DD,HH,MM,SS.sss"
    UTC_J2000 = "j2000"  # Time in UTC; in seconds since J2000 epoch (January 1, 2000, 12:00:00 UTC)


SUPPORTED_FORMATS = [c.value for c in TimeFormat]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Convert time values between supported TudatPy time formats.",
        epilog="Supported time formats:\n"
        + "  "
        + TimeFormat.UTC_ISO
        + ": UTC. ISO 8601 format (e.g., '2024-06-01T12:00:00.000')\n"
        + "  "
        + TimeFormat.UTC_YMDHMS
        + ": UTC. Year, Month, Day, Hour, Minute, Seconds format (e.g., '2024,06,01,12,00,00.000')\n"
        + "  "
        + TimeFormat.UTC_J2000
        + ": UTC. Seconds since J2000 epoch (January 1, 2000, 12:00:00 UTC) (e.g., '31557600.000')\n",
    )
    parser.add_argument(
        "-i",
        "--input-format",
        required=True,
        choices=SUPPORTED_FORMATS,
        help="Name of the input time format.",
    )
    parser.add_argument(
        "-o",
        "--output-format",
        required=True,
        choices=SUPPORTED_FORMATS,
        help="Name of the output time format.",
    )
    parser.add_argument(
        "times",
        nargs="*",
        help="Time values to convert. If omitted, values are read from stdin.",
    )
    return parser.parse_args()


def iter_input_times(args: argparse.Namespace) -> Iterable[str]:
    if args.times:
        yield from args.times
    else:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            for token in line.split():
                yield token


def parse_time_value(value: str, fmt: str) -> DateTime:
    if fmt == TimeFormat.UTC_ISO:
        return DateTime.from_iso_string(value)
    if fmt == TimeFormat.UTC_YMDHMS:
        ymdhms = str.split(value, sep=",", maxsplit=6)
        return DateTime(
            ymdhms[0], ymdhms[1], ymdhms[2], ymdhms[3], ymdhms[4], ymdhms[5]
        )
    if fmt == TimeFormat.UTC_J2000:
        return DateTime.from_epoch(float(value))
    raise ValueError(f"Unsupported input format: {fmt}")


def format_time_value(dt: DateTime, fmt: str) -> str:
    if fmt == TimeFormat.UTC_ISO:
        return dt.to_iso_string(number_of_digits_seconds=3)
    if fmt == TimeFormat.UTC_YMDHMS:
        return f"{dt.year},{dt.month},{dt.day},{dt.hour},{dt.minute},{dt.seconds}"
    if fmt == TimeFormat.UTC_J2000:
        return f"{dt.to_epoch():.3f}"
    raise ValueError(f"Unsupported output format: {fmt}")


def main() -> None:
    args = parse_args()
    for value in iter_input_times(args):
        dt = parse_time_value(value, args.input_format)
        print(format_time_value(dt, args.output_format))


if __name__ == "__main__":
    main()
