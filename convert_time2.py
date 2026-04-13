#!/usr/bin/env python3

import argparse
import math
import sys
from typing import Iterable
import logging

logging.basicConfig(level=logging.WARNING)

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


class TimeConverter:
    """Utility conversion helpers.

    Note: this class is currently not used by the CLI flow below (which uses the
    TimeData classes + `convert_time_value`). It exists as an alternative
    conversion API for direct ISO/J2000 conversions.
    """

    #
    # Conversion functions for UTC ISO-8601 format
    #

    @staticmethod
    def utc_iso_to_utc_ymdhms(iso_time: str) -> str:
        # Convert ISO time to YMDHMS format
        date_time = DateTime.from_iso_string(iso_time)
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    @staticmethod
    def utc_iso_to_utc_j2000(iso_time: str) -> float:
        # Convert ISO time to UTC J2000 seconds
        date_time = DateTime.from_iso_string(iso_time)
        return date_time.to_epoch()

    @staticmethod
    def utc_iso_to_tai_j2000(iso_time: str) -> float:
        # Convert ISO time to TAI J2000 seconds
        date_time = DateTime.from_iso_string(iso_time)
        return TimeConverter.utc_j2000_to_tai_j2000(date_time.to_epoch())

    @staticmethod
    def utc_iso_to_tt_j2000(iso_time: str) -> float:
        # Convert ISO time to TT J2000 seconds
        date_time = DateTime.from_iso_string(iso_time)
        return TimeConverter.utc_j2000_to_tt_j2000(date_time.to_epoch())

    @staticmethod
    def utc_iso_to_tdb_j2000(iso_time: str) -> float:
        # Convert ISO time to TDB J2000 seconds
        date_time = DateTime.from_iso_string(iso_time)
        return TimeConverter.utc_j2000_to_tdb_j2000(date_time.to_epoch())

    #
    # Conversion functions for UTC J2000 epoch
    #

    @staticmethod
    def utc_j2000_to_iso(utc_j2000_epoch: float) -> str:
        # Convert UTC J2000 seconds to ISO format
        date_time = DateTime.from_epoch(utc_j2000_epoch)
        return date_time.to_iso_string(number_of_digits_seconds=3)

    @staticmethod
    def utc_j2000_to_utc_ymdhms(utc_j2000_epoch: float) -> str:
        # Convert UTC J2000 seconds to YMDHMS format
        date_time = DateTime.from_epoch(utc_j2000_epoch)
        return f"{date_time.year},{date_time.month},{date_time.day},{date_time.hour},{date_time.minute},{date_time.seconds}"

    @staticmethod
    def utc_j2000_to_tai_j2000(utc_j2000_epoch: float) -> float:
        # Convert UTC J2000 seconds to TAI J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=utc_j2000_epoch,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tai_scale,
        )

    @staticmethod
    def utc_j2000_to_tt_j2000(utc_j2000_epoch: float) -> float:
        # Convert UTC J2000 seconds to TT J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=utc_j2000_epoch,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tt_scale,
        )

    @staticmethod
    def utc_j2000_to_tdb_j2000(utc_j2000_epoch: float) -> float:
        # Convert UTC J2000 seconds to TDB J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=utc_j2000_epoch,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tdb_scale,
        )

    #
    # Conversion functions for TAI J2000 epoch
    #

    @staticmethod
    def tai_j2000_to_iso(tai_j2000_epoch: float) -> str:
        # Convert TAI J2000 seconds to ISO format
        utc_j2000_epoch = TimeConverter.tai_j2000_to_utc_j2000(tai_j2000_epoch)
        return TimeConverter.utc_j2000_to_iso(utc_j2000_epoch)

    @staticmethod
    def tai_j2000_to_utc_ymdhms(tai_j2000_epoch: float) -> str:
        # Convert TAI J2000 seconds to YMDHMS format
        utc_j2000_epoch = TimeConverter.tai_j2000_to_utc_j2000(tai_j2000_epoch)
        return TimeConverter.utc_j2000_to_utc_ymdhms(utc_j2000_epoch)

    @staticmethod
    def tai_j2000_to_utc_j2000(tai_j2000_epoch: float) -> float:
        # Convert TAI J2000 seconds to UTC J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tai_j2000_epoch,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.utc_scale,
        )

    @staticmethod
    def tai_j2000_to_tt_j2000(tai_j2000_epoch: float) -> float:
        # Convert TAI J2000 seconds to TT J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tai_j2000_epoch,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.tt_scale,
        )

    @staticmethod
    def tai_j2000_to_tdb_j2000(tai_j2000_epoch: float) -> float:
        # Convert TAI J2000 seconds to TDB J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tai_j2000_epoch,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.tdb_scale,
        )

    #
    # Conversion functions for TT J2000 epoch
    #

    @staticmethod
    def tt_j2000_to_iso(tt_j2000_epoch: float) -> str:
        # Convert TT J2000 seconds to ISO format
        utc_j2000_epoch = TimeConverter.tt_j2000_to_utc_j2000(tt_j2000_epoch)
        return TimeConverter.utc_j2000_to_iso(utc_j2000_epoch)

    @staticmethod
    def tt_j2000_to_utc_ymdhms(tt_j2000_epoch: float) -> str:
        # Convert TT J2000 seconds to YMDHMS format
        utc_j2000_epoch = TimeConverter.tt_j2000_to_utc_j2000(tt_j2000_epoch)
        return TimeConverter.utc_j2000_to_utc_ymdhms(utc_j2000_epoch)

    @staticmethod
    def tt_j2000_to_utc_j2000(tt_j2000_epoch: float) -> float:
        # Convert TT J2000 seconds to UTC J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tt_j2000_epoch,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.utc_scale,
        )

    @staticmethod
    def tt_j2000_to_tai_j2000(tt_j2000_epoch: float) -> float:
        # Convert TT J2000 seconds to TAI J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tt_j2000_epoch,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.tai_scale,
        )

    @staticmethod
    def tt_j2000_to_tdb_j2000(tt_j2000_epoch: float) -> float:
        # Convert TT J2000 seconds to TDB J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tt_j2000_epoch,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.tdb_scale,
        )

    #
    # Conversion functions for TDB J2000 epoch
    #

    @staticmethod
    def tdb_j2000_to_iso(tdb_j2000_epoch: float) -> str:
        # Convert TDB J2000 seconds to ISO format (via UTC)
        utc_j2000_epoch = TimeConverter.tdb_j2000_to_utc_j2000(tdb_j2000_epoch)
        return TimeConverter.utc_j2000_to_iso(utc_j2000_epoch)

    @staticmethod
    def tdb_j2000_to_utc_ymdhms(tdb_j2000_epoch: float) -> str:
        # Convert TDB J2000 seconds to YMDHMS format (via UTC)
        utc_j2000_epoch = TimeConverter.tdb_j2000_to_utc_j2000(tdb_j2000_epoch)
        return TimeConverter.utc_j2000_to_utc_ymdhms(utc_j2000_epoch)

    @staticmethod
    def tdb_j2000_to_utc_j2000(tdb_j2000_epoch: float) -> float:
        # Convert TDB J2000 seconds to UTC J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tdb_j2000_epoch,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.utc_scale,
        )

    @staticmethod
    def tdb_j2000_to_tai_j2000(tdb_j2000_epoch: float) -> float:
        # Convert TDB J2000 seconds to TAI J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tdb_j2000_epoch,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.tai_scale,
        )

    @staticmethod
    def tdb_j2000_to_tt_j2000(tdb_j2000_epoch: float) -> float:
        # Convert TDB J2000 seconds to TT J2000 seconds
        return time_representation.default_time_scale_converter().convert_time(
            input_value=tdb_j2000_epoch,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.tt_scale,
        )

    conversion_table = {
        TimeFormat.UTC_ISO.value: {
            TimeFormat.UTC_YMDHMS.value: utc_iso_to_utc_ymdhms,
            TimeFormat.UTC_J2000.value: utc_iso_to_utc_j2000,
            TimeFormat.TAI_J2000.value: utc_iso_to_tai_j2000,
            TimeFormat.TT_J2000.value: utc_iso_to_tt_j2000,
            TimeFormat.TDB_J2000.value: utc_iso_to_tdb_j2000,
        },
        TimeFormat.UTC_J2000.value: {
            TimeFormat.UTC_ISO.value: utc_j2000_to_iso,
            TimeFormat.UTC_YMDHMS.value: utc_j2000_to_utc_ymdhms,
            TimeFormat.TAI_J2000.value: utc_j2000_to_tai_j2000,
            TimeFormat.TT_J2000.value: utc_j2000_to_tt_j2000,
            TimeFormat.TDB_J2000.value: utc_j2000_to_tdb_j2000,
        },
        TimeFormat.TAI_J2000.value: {
            TimeFormat.UTC_ISO.value: tai_j2000_to_iso,
            TimeFormat.UTC_YMDHMS.value: tai_j2000_to_utc_ymdhms,
            TimeFormat.UTC_J2000.value: tai_j2000_to_utc_j2000,
            TimeFormat.TT_J2000.value: tai_j2000_to_tt_j2000,
            TimeFormat.TDB_J2000.value: tai_j2000_to_tdb_j2000,
        },
        TimeFormat.TT_J2000.value: {
            TimeFormat.UTC_ISO.value: tt_j2000_to_iso,
            TimeFormat.UTC_YMDHMS.value: tt_j2000_to_utc_ymdhms,
            TimeFormat.UTC_J2000.value: tt_j2000_to_utc_j2000,
            TimeFormat.TAI_J2000.value: tt_j2000_to_tai_j2000,
            TimeFormat.TDB_J2000.value: tt_j2000_to_tdb_j2000,
        },
        TimeFormat.TDB_J2000.value: {
            TimeFormat.UTC_ISO.value: tdb_j2000_to_iso,
            TimeFormat.UTC_YMDHMS.value: tdb_j2000_to_utc_ymdhms,
            TimeFormat.UTC_J2000.value: tdb_j2000_to_utc_j2000,
            TimeFormat.TAI_J2000.value: tdb_j2000_to_tai_j2000,
            TimeFormat.TT_J2000.value: tdb_j2000_to_tt_j2000,
        },
    }

    @staticmethod
    def convert(input_value, input_format: str, output_format: str):
        if output_format == input_format:
            return input_value
        else:
            return TimeConverter.conversion_table[input_format][output_format](
                input_value
            )


def main() -> None:
    args = parse_args()
    for value in iter_input_times(args):
        print(value, end="")

        if (
            args.input_format == TimeFormat.UTC_ISO.value
            or args.input_format == TimeFormat.UTC_YMDHMS.value
        ):
            time_value = value
        else:
            time_value = float(value)

        for output_format in args.output_format:
            if output_format == args.input_format:
                print(f"\t{value}", end="")
            else:
                output = TimeConverter.convert(
                    time_value, args.input_format, output_format
                )

                if isinstance(output, float):
                    print(f"\t{output:.3f}", end="")
                else:
                    print(f"\t{output}", end="")

        print()


if __name__ == "__main__":
    main()
