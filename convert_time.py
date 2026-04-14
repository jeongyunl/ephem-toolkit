#!/usr/bin/env python3

import argparse
import math
import sys
from typing import Iterable
from enum import Enum
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.WARNING)

import tudatpy.astro.time_representation as time_representation
from tudatpy.astro.time_representation import DateTime, TimeScales

POSIX_EPOCH_MINUS_UTC_J2000 = 946728000.0  # POSIX epoch (1970-01-01 00:00:00 UTC) minus UTC J2000 epoch (2000-01-01 12:00:00 UTC)


class TimeFormat(Enum):
    UTC_POSIX = "posix"  # POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
    UTC_ISO_TUDAT = "iso"  # ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
    UTC_J2000_TUDAT = "j2000"  # Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
    TAI_J2000_TUDAT = "tai"  # Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI = 2000-01-01 11:59:28 UTC)
    TT_J2000_TUDAT = "tt"  # Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT = 2000-01-01 11:58:55.816 UTC)
    TDB_J2000_TUDAT = "tdb"  # Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)


SUPPORTED_FORMATS = [c.value for c in TimeFormat]


class TimeData:
    """Container for time format and value."""

    def __init__(self, time_format: TimeFormat, time_string: str):
        self.time_format = time_format
        self.time_string = time_string

    def to_utc_posix(self) -> float:
        raise NotImplementedError

    def to_utc_iso_tudat(self) -> str:
        raise NotImplementedError

    def to_utc_j2000_tudat(self) -> float:
        raise NotImplementedError

    def to_tai_j2000_tudat(self) -> float:
        raise NotImplementedError

    def to_tt_j2000_tudat(self) -> float:
        raise NotImplementedError

    def to_tdb_j2000_tudat(self) -> float:
        raise NotImplementedError


class TudatTimeData(TimeData):

    def __init__(self, time_format: TimeFormat, time_string: str):
        super().__init__(time_format, time_string)

        self.native_time_scale = None
        self.native_tudat_epoch = None

    def to_utc_posix(self) -> float:
        epoch_utc = self.to_utc_j2000_tudat()
        return epoch_utc + POSIX_EPOCH_MINUS_UTC_J2000

    def to_utc_iso_tudat(self) -> str:
        epoch_utc = self.to_utc_j2000_tudat()
        tudat_date_time = DateTime.from_epoch(epoch_utc)

        # Check if this epoch might be leap second
        if (
            (tudat_date_time.month == 7 or tudat_date_time.month == 1)
            and tudat_date_time.day == 1
            and tudat_date_time.hour == 0
            and tudat_date_time.minute == 0
            and tudat_date_time.seconds <= 1.0
        ):
            epoch_utc_plus_1 = (
                time_representation.default_time_scale_converter().convert_time(
                    input_value=self.native_tudat_epoch + 1,
                    input_scale=self.native_time_scale,
                    output_scale=TimeScales.utc_scale,
                )
            )

            # Leap second
            if epoch_utc == epoch_utc_plus_1:
                # It is leap second
                epoch_utc_minus_1 = (
                    time_representation.default_time_scale_converter().convert_time(
                        input_value=self.native_tudat_epoch - 1,
                        input_scale=self.native_time_scale,
                        output_scale=TimeScales.utc_scale,
                    )
                )
                tudat_date_time = DateTime.from_epoch(epoch_utc_minus_1)
                # FIXME  Due to tudat DateTime's bug, this will fail when DateTime.seconds is greater than 60.0
                try:
                    tudat_date_time.seconds += 1.0
                except RuntimeError as e:
                    logging.error(f"Error setting leap second: {e}")
                    return "ERROR"

        return tudat_date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_j2000_tudat(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_tudat_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.utc_scale,
        )

    def to_tai_j2000_tudat(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_tudat_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.tai_scale,
        )

    def to_tt_j2000_tudat(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_tudat_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.tt_scale,
        )

    def to_tdb_j2000_tudat(self) -> float:
        return time_representation.default_time_scale_converter().convert_time(
            input_value=self.native_tudat_epoch,
            input_scale=self.native_time_scale,
            output_scale=TimeScales.tdb_scale,
        )


class UtcTimeData(TudatTimeData):

    def __init__(self, time_format: TimeFormat, time_string: str):
        super().__init__(time_format, time_string)

        self.native_time_scale = TimeScales.utc_scale
        self.tudat_date_time = None
        self.leap_second = 0.0

    def update_utc_epoch(self):
        self.native_tudat_epoch = self.tudat_date_time.to_epoch()

        # If the seconds value is 60 or more, it indicates a leap second.
        if self.tudat_date_time.seconds >= 60.0:
            self.leap_second = 1.0

    def to_utc_iso_tudat(self) -> str:
        return self.tudat_date_time.to_iso_string(number_of_digits_seconds=3)

    def to_utc_j2000_tudat(self) -> float:
        return self.native_tudat_epoch

    def to_tai_j2000_tudat(self) -> float:
        return super().to_tai_j2000_tudat() - self.leap_second

    def to_tt_j2000_tudat(self) -> float:
        return super().to_tt_j2000_tudat() - self.leap_second

    def to_tdb_j2000_tudat(self) -> float:
        return super().to_tdb_j2000_tudat() - self.leap_second


class UtcPosixTimeData(UtcTimeData):
    def __init__(self, time_string: str):
        super().__init__(TimeFormat.UTC_POSIX, time_string)

        self.posix_epoch = float(self.time_string)
        self.native_tudat_epoch = self.posix_epoch - POSIX_EPOCH_MINUS_UTC_J2000
        self.tudat_date_time = DateTime.from_epoch(self.native_tudat_epoch)

    def to_utc_posix(self) -> float:
        return self.posix_epoch

    def to_utc_j2000_tudat(self):
        return self.native_tudat_epoch


class TudatUtcIsoTimeData(UtcTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.UTC_ISO_TUDAT, time_string)

        # FIXME  Due to tudat DateTime's bug, this will fail when DateTime.seconds is greater than 60.0
        try:
            self.tudat_date_time = DateTime.from_iso_string(self.time_string)
            self.update_utc_epoch()
        except RuntimeError as e:
            logging.error(f"Error parsing time string {time_string}: {e}")
            self.native_tudat_epoch = math.nan
            self.tudat_date_time = None


class TudatUtcJ2000TimeData(UtcTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.UTC_J2000_TUDAT, time_string)

        self.tudat_date_time = DateTime.from_epoch(float(self.time_string))
        self.update_utc_epoch()


class TudatTaiJ2000TimeData(TudatTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.TAI_J2000_TUDAT, time_string)

        self.native_time_scale = TimeScales.tai_scale
        self.native_tudat_epoch = float(self.time_string)

    def to_tai_j2000_tudat(self) -> float:
        return self.native_tudat_epoch


class TudatTtJ2000TimeData(TudatTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.TT_J2000_TUDAT, time_string)

        self.native_time_scale = TimeScales.tt_scale
        self.native_tudat_epoch = float(self.time_string)

    def to_tt_j2000_tudat(self) -> float:
        return self.native_tudat_epoch


class TudatTdbJ2000TimeData(TudatTimeData):

    def __init__(self, time_string: str):
        super().__init__(TimeFormat.TDB_J2000_TUDAT, time_string)

        self.native_time_scale = TimeScales.tdb_scale
        self.native_tudat_epoch = float(self.time_string)

    def to_tdb_j2000_tudat(self) -> float:
        return self.native_tudat_epoch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Convert time values between supported TudatPy time formats.",
        epilog="Supported time formats:\n"
        + "  "
        + TimeFormat.UTC_ISO_TUDAT.value
        + ": UTC. ISO 8601 format (e.g., '2024-06-01T12:00:00.000')\n"
        + "  "
        + TimeFormat.UTC_J2000_TUDAT.value
        + ": UTC. Seconds since UTC J2000 epoch (January 1, 2000, 12:00:00 UTC) (e.g., '31557600.000')\n"
        + "  "
        + TimeFormat.TAI_J2000_TUDAT.value
        + ": TAI. "
        + "Seconds since TAI J2000 epoch (January 1, 2000, 12:00:00 TAI = January 1, 2000, 11:59:28 UTC) (e.g., '31557628.000')\n"
        + "  "
        + TimeFormat.TT_J2000_TUDAT.value
        + ": Terrestrial Time. Seconds since TT J2000 epoch (January 1, 2000, 12:00:00 TT = January 1, 2000, 11:58:55.816 UTC) (e.g., '31558127.816')\n"
        + "  "
        + TimeFormat.UTC_POSIX.value
        + ": POSIX timestamp. Seconds since 1970-01-01 00:00:00 UTC (e.g., '1622548800.000')\n",
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
        nargs="+",
        choices=SUPPORTED_FORMATS,
        help=(
            "One or more output time formats. "
            "Provide multiple values to print multiple converted outputs per input time."
        ),
    )
    parser.add_argument(
        "-t",
        "--time",
        nargs="+",
        help="Time values to convert. If omitted, values are read from stdin.",
    )
    return parser.parse_args()


def iter_input_times(args: argparse.Namespace) -> Iterable[str]:
    if args.time:
        yield from args.time
    else:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            for token in line.split():
                yield token


def parse_time_value(value: str, fmt: str) -> TudatTimeData:
    if fmt == TimeFormat.UTC_POSIX.value:
        return UtcPosixTimeData(value)
    if fmt == TimeFormat.UTC_ISO_TUDAT.value:
        return TudatUtcIsoTimeData(value)
    if fmt == TimeFormat.UTC_J2000_TUDAT.value:
        return TudatUtcJ2000TimeData(value)
    if fmt == TimeFormat.TAI_J2000_TUDAT.value:
        return TudatTaiJ2000TimeData(value)
    if fmt == TimeFormat.TT_J2000_TUDAT.value:
        return TudatTtJ2000TimeData(value)
    if fmt == TimeFormat.TDB_J2000_TUDAT.value:
        return TudatTdbJ2000TimeData(value)

    raise ValueError(f"Unsupported input format: {fmt}")


def convert_time_value(time: TudatTimeData, format_name: str):
    if format_name == TimeFormat.UTC_POSIX.value:
        return time.to_utc_posix()
    if format_name == TimeFormat.UTC_ISO_TUDAT.value:
        return time.to_utc_iso_tudat()
    if format_name == TimeFormat.UTC_J2000_TUDAT.value:
        return time.to_utc_j2000_tudat()
    if format_name == TimeFormat.TAI_J2000_TUDAT.value:
        return time.to_tai_j2000_tudat()
    if format_name == TimeFormat.TT_J2000_TUDAT.value:
        return time.to_tt_j2000_tudat()
    if format_name == TimeFormat.TDB_J2000_TUDAT.value:
        return time.to_tdb_j2000_tudat()

    raise ValueError(f"Unsupported output format: {format_name}")


def main() -> None:
    args = parse_args()
    for value in iter_input_times(args):
        time_data = parse_time_value(value, args.input_format)

        outputs = [convert_time_value(time_data, fmt) for fmt in args.output_format]

        print(f"{value}\t", end="")
        formatted_outputs = []
        for output in outputs:
            if isinstance(output, float):
                formatted_outputs.append(f"{output:.3f}")
            else:
                formatted_outputs.append(str(output))

        print("\t".join(formatted_outputs))


if __name__ == "__main__":
    main()
