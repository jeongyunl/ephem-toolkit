#!/usr/bin/env python3

import argparse
import sys
from dataclasses import dataclass
from typing import Iterable

import tudatpy.astro.time_representation as time_representation
from tudatpy.astro.time_representation import DateTime, TimeScales
from enum import StrEnum


class TimeFormat(StrEnum):
    UTC_ISO = "iso"  # ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
    UTC_YMDHMS = "ymdhms"  # Year, Month, Day, Hour, Minute, Seconds format in UTC: "YYYY,MM,DD,HH,MM,SS.sss"
    UTC_J2000 = "j2000"  # Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
    TAI_J2000 = "tai"  # Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI = 2000-01-01 11:59:28 UTC)
    TT_J2000 = "tt"  # Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT = 2000-01-01 11:58:55.816 UTC)
    TDB_J2000 = "tdb"  # Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)


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

    def to_utc_iso(self) -> str:
        raise NotImplementedError("to_utc_iso() not implemented for this time format")

    def to_utc_ymdhms(self) -> str:
        raise NotImplementedError(
            "to_utc_ymdhms() not implemented for this time format"
        )

    def to_utc_j2000(self) -> float:
        raise NotImplementedError("to_utc_j2000() not implemented for this time format")

    def to_tai_j2000(self) -> float:
        raise NotImplementedError("to_tai_j2000() not implemented for this time format")

    def to_tt_j2000(self) -> float:
        raise NotImplementedError("to_tt_j2000() not implemented for this time format")

    def to_tdb_j2000(self) -> float:
        raise NotImplementedError("to_tdb_j2000() not implemented for this time format")


@dataclass
class UtcIsoTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.UTC_ISO, string)

    def to_utc_iso(self) -> str:
        return self.time_string

    def to_utc_ymdhms(self) -> str:
        self.date_time = DateTime.from_iso_string(self.time_string)
        return f"{self.date_time.year},{self.date_time.month},{self.date_time.day},{self.date_time.hour},{self.date_time.minute},{self.date_time.seconds}"

    def to_utc_j2000(self) -> float:
        self.date_time = DateTime.from_iso_string(self.time_string)
        return self.date_time.to_epoch()

    def to_tai_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tdb_scale,
        )


@dataclass
class UtcYmdhmsTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.UTC_YMDHMS, string)

    def to_utc_iso(self) -> str:
        ymdhms = str.split(self.time_string, sep=",", maxsplit=6)
        date_time = DateTime(
            ymdhms[0], ymdhms[1], ymdhms[2], ymdhms[3], ymdhms[4], ymdhms[5]
        )
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        return self.time_string

    def to_utc_j2000(self) -> float:
        ymdhms = str.split(self.time_string, sep=",", maxsplit=6)
        date_time = DateTime(
            ymdhms[0], ymdhms[1], ymdhms[2], ymdhms[3], ymdhms[4], ymdhms[5]
        )
        return date_time.to_epoch()

    def to_tai_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tdb_scale,
        )


@dataclass
class UtcJ2000TimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.UTC_J2000, string)

    def to_utc_iso(self) -> str:
        date_time = DateTime.from_epoch(self.to_utc_j2000())
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        date_time = DateTime.from_epoch(self.to_utc_j2000())
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    def to_utc_j2000(self) -> float:
        return float(self.time_string)

    def to_tai_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000(self) -> float:
        epoch_utc = self.to_utc_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_utc,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tdb_scale,
        )


@dataclass
class TaiTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.TAI_J2000, string)

    def to_utc_iso(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    def to_utc_j2000(self) -> float:
        epoch_tai = self.to_tai_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tai,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.utc_scale,
        )

    def to_tai_j2000(self) -> float:
        return float(self.time_string)

    def to_tt_j2000(self) -> float:
        epoch_tai = self.to_tai_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tai,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000(self) -> float:
        epoch_tai = self.to_tai_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tai,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.tdb_scale,
        )


@dataclass
class TtTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.TT_J2000, string)

    def to_utc_iso(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    def to_utc_j2000(self) -> float:
        epoch_tt = self.to_tt_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tt,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.utc_scale,
        )

    def to_tai_j2000(self) -> float:
        epoch_tt = self.to_tt_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tt,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000(self) -> float:
        return float(self.time_string)

    def to_tdb_j2000(self) -> float:
        epoch_tt = self.to_tt_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tt,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.tdb_scale,
        )


@dataclass
class TdbTimeData(TimeData):

    def __init__(self, string: str):
        super().__init__(TimeFormat.TDB_J2000, string)

    def to_utc_iso(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    def to_utc_j2000(self) -> float:
        epoch_tdb = self.to_tdb_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tdb,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.utc_scale,
        )

    def to_tai_j2000(self) -> float:
        epoch_tdb = self.to_tdb_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tdb,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000(self) -> float:
        epoch_tdb = self.to_tdb_j2000()
        return time_representation.default_time_scale_converter().convert_time(
            input_value=epoch_tdb,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000(self) -> float:
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
        + ": UTC. Seconds since UTC J2000 epoch (January 1, 2000, 12:00:00 UTC) (e.g., '31557600.000')\n"
        + "  "
        + TimeFormat.TAI_J2000
        + ": TAI. "
        + "Seconds since TAI J2000 epoch (January 1, 2000, 12:00:00 TAI = January 1, 2000, 11:59:28 UTC) (e.g., '31557628.000')\n"
        + "  "
        + TimeFormat.TT_J2000
        + ": Terrestrial Time. Seconds since TT J2000 epoch (January 1, 2000, 12:00:00 TT = January 1, 2000, 11:58:55.816 UTC) (e.g., '31558127.816')\n",
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
    if fmt == TimeFormat.TAI_J2000:
        return TaiTimeData(value)
    if fmt == TimeFormat.TT_J2000:
        return TtTimeData(value)
    if fmt == TimeFormat.TDB_J2000:
        return TdbTimeData(value)

    raise ValueError(f"Unsupported input format: {fmt}")


def convert_time_value(time: TimeData, format_name: str) -> str | float:
    if format_name == TimeFormat.UTC_ISO:
        return time.to_utc_iso()
    if format_name == TimeFormat.UTC_YMDHMS:
        return time.to_utc_ymdhms()
    if format_name == TimeFormat.UTC_J2000:
        return time.to_utc_j2000()
    if format_name == TimeFormat.TAI_J2000:
        return time.to_tai_j2000()
    if format_name == TimeFormat.TT_J2000:
        return time.to_tt_j2000()
    if format_name == TimeFormat.TDB_J2000:
        return time.to_tdb_j2000()

    raise ValueError(f"Unsupported output format: {format_name}")


def main() -> None:
    args = parse_args()
    for value in iter_input_times(args):
        dt = parse_time_value(value, args.input_format)
        output = convert_time_value(dt, args.output_format)
        if isinstance(output, float):
            print(f"{output:.3f}")
        else:
            print(output)


if __name__ == "__main__":
    main()
