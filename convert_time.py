#!/usr/bin/env python3

import argparse
import sys
from typing import Iterable

import tudatpy.astro.time_representation as time_representation
from tudatpy.astro.time_representation import DateTime, TimeScales

from enum import Enum


class TimeFormat(Enum):
    UTC_ISO = "iso"  # ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
    UTC_YMDHMS = "ymdhms"  # Year, Month, Day, Hour, Minute, Seconds format in UTC: "YYYY,MM,DD,HH,MM,SS.sss"
    UTC_J2000 = "j2000"  # Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
    TAI_J2000 = "tai"  # Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI = 2000-01-01 11:59:28 UTC)
    TT_J2000 = "tt"  # Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT = 2000-01-01 11:58:55.816 UTC)
    TDB_J2000 = "tdb"  # Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)


SUPPORTED_FORMATS = [c.value for c in TimeFormat]


class TimeData:
    """Container for time format and value."""

    def __init__(self, time_format: TimeFormat, time_string: str):
        self.time_format = time_format
        self.time_string = time_string

        self.native_time_scale = None
        self.native_epoch = None

    def to_utc_iso(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)

        # Check if this epoch might be leap second
        if (
            (date_time.month == 7 or date_time.month == 1)
            and date_time.day == 1
            and date_time.hour == 0
            and date_time.minute == 0
            and date_time.seconds <= 1.0
        ):
            epoch_utc_plus_1 = (
                time_representation.default_time_scale_converter().convert_time(
                    input_value=self.native_epoch + 1,
                    input_scale=self.native_time_scale,
                    output_scale=TimeScales.utc_scale,
                )
            )

            # Leap second
            if epoch_utc == epoch_utc_plus_1:
                # It is leap second
                epoch_utc_minus_1 = (
                    time_representation.default_time_scale_converter().convert_time(
                        input_value=self.native_epoch - 1,
                        input_scale=self.native_time_scale,
                        output_scale=TimeScales.utc_scale,
                    )
                )
                date_time = DateTime.from_epoch(epoch_utc_minus_1)
                # FIXME
                # Due to tudat DateTime's bug, this will fail when date_time.seconds is greater than 59.0
                date_time.seconds += 1.0

        return date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        epoch_utc = self.to_utc_j2000()
        date_time = DateTime.from_epoch(epoch_utc)
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    def to_utc_j2000(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.utc_scale,
        )

    def to_tai_j2000(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.tdb_scale,
        )


class UtcTimeData(TimeData):

    def __init__(self, time_format: TimeFormat, time_string: str):
        super().__init__(time_format, time_string)

        self.native_time_scale = TimeScales.utc_scale
        self.date_time = None
        self.leap_second = 0.0

    def update_utc_epoch(self):
        self.native_epoch = self.date_time.to_epoch()

        # If the seconds value is 60 or more, it indicates a leap second.
        if self.date_time.seconds >= 60.0:
            self.leap_second = 1.0

    def to_utc_iso(self) -> str:
        return self.date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_ymdhms(self) -> str:
        return f"{self.date_time.year},{self.date_time.month},{self.date_time.day},{self.date_time.hour},{self.date_time.minute},{self.date_time.seconds}"

    def to_utc_j2000(self) -> float:
        return self.native_epoch

    def to_tai_j2000(self) -> float:
        return super().to_tai_j2000() - self.leap_second

    def to_tt_j2000(self) -> float:
        return super().to_tt_j2000() - self.leap_second

    def to_tdb_j2000(self) -> float:
        return super().to_tdb_j2000() - self.leap_second


class UtcIsoTimeData(UtcTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.UTC_ISO, time_string)

        self.date_time = DateTime.from_iso_string(self.time_string)
        self.update_utc_epoch()


class UtcYmdhmsTimeData(UtcTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.UTC_YMDHMS, time_string)

        ymdhms = str.split(self.time_string, sep=",", maxsplit=6)
        self.date_time = DateTime(
            int(ymdhms[0]),
            int(ymdhms[1]),
            int(ymdhms[2]),
            int(ymdhms[3]),
            int(ymdhms[4]),
            float(ymdhms[5]),
        )
        self.update_utc_epoch()


class UtcJ2000TimeData(UtcTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.UTC_J2000, time_string)

        self.date_time = DateTime.from_epoch(float(self.time_string))
        self.update_utc_epoch()


class TaiTimeData(TimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.TAI_J2000, time_string)

        self.native_time_scale = TimeScales.tai_scale
        self.native_epoch = float(self.time_string)

    def to_tai_j2000(self) -> float:
        return self.native_epoch


class TtTimeData(TimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.TT_J2000, time_string)

        self.native_time_scale = TimeScales.tt_scale
        self.native_epoch = float(self.time_string)

    def to_tt_j2000(self) -> float:
        return self.native_epoch


class TdbTimeData(TimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.TDB_J2000, time_string)

        self.native_time_scale = TimeScales.tdb_scale
        self.native_epoch = float(self.time_string)

    def to_tdb_j2000(self) -> float:
        return self.native_epoch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Convert time values between supported TudatPy time formats.",
        epilog="Supported time formats:\n"
        + "  "
        + TimeFormat.UTC_ISO.value
        + ": UTC. ISO 8601 format (e.g., '2024-06-01T12:00:00.000')\n"
        + "  "
        + TimeFormat.UTC_YMDHMS.value
        + ": UTC. Year, Month, Day, Hour, Minute, Seconds format (e.g., '2024,06,01,12,00,00.000')\n"
        + "  "
        + TimeFormat.UTC_J2000.value
        + ": UTC. Seconds since UTC J2000 epoch (January 1, 2000, 12:00:00 UTC) (e.g., '31557600.000')\n"
        + "  "
        + TimeFormat.TAI_J2000.value
        + ": TAI. "
        + "Seconds since TAI J2000 epoch (January 1, 2000, 12:00:00 TAI = January 1, 2000, 11:59:28 UTC) (e.g., '31557628.000')\n"
        + "  "
        + TimeFormat.TT_J2000.value
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
    if fmt == TimeFormat.UTC_ISO.value:
        return UtcIsoTimeData(value)
    if fmt == TimeFormat.UTC_YMDHMS.value:
        return UtcYmdhmsTimeData(value)
    if fmt == TimeFormat.UTC_J2000.value:
        return UtcJ2000TimeData(value)
    if fmt == TimeFormat.TAI_J2000.value:
        return TaiTimeData(value)
    if fmt == TimeFormat.TT_J2000.value:
        return TtTimeData(value)
    if fmt == TimeFormat.TDB_J2000.value:
        return TdbTimeData(value)

    raise ValueError(f"Unsupported input format: {fmt}")


def convert_time_value(time: TimeData, format_name: str):
    if format_name == TimeFormat.UTC_ISO.value:
        return time.to_utc_iso()
    if format_name == TimeFormat.UTC_YMDHMS.value:
        return time.to_utc_ymdhms()
    if format_name == TimeFormat.UTC_J2000.value:
        return time.to_utc_j2000()
    if format_name == TimeFormat.TAI_J2000.value:
        return time.to_tai_j2000()
    if format_name == TimeFormat.TT_J2000.value:
        return time.to_tt_j2000()
    if format_name == TimeFormat.TDB_J2000.value:
        return time.to_tdb_j2000()

    raise ValueError(f"Unsupported output format: {format_name}")


def main() -> None:
    args = parse_args()
    for value in iter_input_times(args):
        dt = parse_time_value(value, args.input_format)
        output = convert_time_value(dt, args.output_format)
        print(f"{value}\t", end="")
        if isinstance(output, float):
            print(f"{output:.3f}")
        else:
            print(output)


if __name__ == "__main__":
    main()
