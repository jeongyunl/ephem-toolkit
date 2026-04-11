#!/usr/bin/env python3

import argparse
import sys
from dataclasses import dataclass
from typing import Iterable

from tudatpy.astro.time_representation import DateTime
from enum import StrEnum


class TimeFormat(StrEnum):
    UTC_ISO = "iso"  # ISO 8601 format: "YYYY-MM-DDTHH:MM:SS.sss"
    UTC_YMDHMS = "ymdhms"  # Year, Month, Day, Hour, Minute, Seconds format: "YYYY,MM,DD,HH,MM,SS.sss"
    UTC_J2000 = "j2000"  # Time in UTC; in seconds since J2000 epoch (January 1, 2000, 12:00:00 UTC)


SUPPORTED_FORMATS = [c.value for c in TimeFormat]


@dataclass
class TimeData:
    """Container for time format and value."""

    time_format: TimeFormat
    time_string: str = ""

    def __init__(self, time_format: TimeFormat, string: str):
        self.time_format = time_format
        self.time_string = string

    def can_convert_to(self, other_format: TimeFormat) -> bool:
        return self.time_format != other_format

    def to_iso(self) -> str:
        raise NotImplementedError("to_iso() not implemented for this time format")

    def to_ymdhms(self) -> str:
        raise NotImplementedError("to_ymdhms() not implemented for this time format")

    def to_j2000(self) -> float:
        raise NotImplementedError("to_j2000() not implemented for this time format")


@dataclass
class UtcIsoTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.UTC_ISO, string)

    def to_iso(self) -> str:
        return self.time_string

    def to_ymdhms(self) -> str:
        self.date_time = DateTime.from_iso_string(self.time_string)
        return f"{self.date_time.year},{self.date_time.month},{self.date_time.day},{self.date_time.hour},{self.date_time.minute},{self.date_time.seconds}"

    def to_j2000(self) -> float:
        self.date_time = DateTime.from_iso_string(self.time_string)
        return self.date_time.to_epoch()


@dataclass
class UtcYmdhmsTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.UTC_YMDHMS, string)

    def to_iso(self) -> str:
        ymdhms = str.split(self.time_string, sep=",", maxsplit=6)
        date_time = DateTime(
            ymdhms[0], ymdhms[1], ymdhms[2], ymdhms[3], ymdhms[4], ymdhms[5]
        )
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_ymdhms(self) -> str:
        return self.time_string

    def to_j2000(self) -> float:
        ymdhms = str.split(self.time_string, sep=",", maxsplit=6)
        date_time = DateTime(
            ymdhms[0], ymdhms[1], ymdhms[2], ymdhms[3], ymdhms[4], ymdhms[5]
        )
        return date_time.to_epoch()


@dataclass
class UtcJ2000TimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.UTC_J2000, string)

    def to_iso(self) -> str:
        date_time = DateTime.from_epoch(float(self.time_string))
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_ymdhms(self) -> str:
        date_time = DateTime.from_epoch(float(self.time_string))
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    def to_j2000(self) -> float:
        return float(self.time_string)


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


def parse_time_value(value: str, fmt: str) -> TimeData:
    if fmt == TimeFormat.UTC_ISO:
        return UtcIsoTimeData(value)
    if fmt == TimeFormat.UTC_YMDHMS:
        return UtcYmdhmsTimeData(value)
    if fmt == TimeFormat.UTC_J2000:
        return UtcJ2000TimeData(value)
    raise ValueError(f"Unsupported input format: {fmt}")


def convert_time_value(dt: TimeData, fmt: str) -> str:
    if fmt == TimeFormat.UTC_ISO:
        return dt.to_iso()
    if fmt == TimeFormat.UTC_YMDHMS:
        return dt.to_ymdhms()
    if fmt == TimeFormat.UTC_J2000:
        return str(dt.to_j2000())
    raise ValueError(f"Unsupported output format: {fmt}")


def main() -> None:
    args = parse_args()
    for value in iter_input_times(args):
        dt = parse_time_value(value, args.input_format)
        print(convert_time_value(dt, args.output_format))


if __name__ == "__main__":
    main()
