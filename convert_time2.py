#!/usr/bin/env python3

import argparse
import math
import sys
from typing import Iterable
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.WARNING)

import tudatpy.astro.time_representation as time_representation
from tudatpy.astro.time_representation import DateTime, TimeScales

from enum import Enum

POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH = 946728000.0  # POSIX epoch (1970-01-01 00:00:00 UTC) minus TUDAT UTC J2000 epoch (2000-01-01 12:00:00 UTC)
TT_EPOCH_MINUS_TAI_EPOCH = 32.184  # TT epoch (2000-01-01 12:00:00 TT) minus TAI epoch (2000-01-01 12:00:00 TAI)

tudat_time_scale_converter = time_representation.default_time_scale_converter()


class TimeFormat(Enum):
    UTC_POSIX = "posix"  # POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
    UTC_ISO_TUDAT = "iso"  # ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
    UTC_TUDAT = "utc"  # Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
    TAI_TUDAT = "tai"  # Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI = 2000-01-01 11:59:28 UTC)
    TT_TUDAT = "tt"  # Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT = 2000-01-01 11:58:55.816 UTC)
    TDB_TUDAT = "tdb"  # Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)
    TDB_APX_TUDAT = "tdb_apx"  # Approximate Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)


SUPPORTED_FORMATS = [c.value for c in TimeFormat]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Convert time values between supported TudatPy time formats.",
        epilog="Supported time formats:\n"
        + "  "
        + TimeFormat.UTC_ISO_TUDAT.value
        + ": UTC. ISO 8601 format (e.g., '2024-06-01T12:00:00.000')\n"
        + "  "
        + TimeFormat.UTC_TUDAT.value
        + ": UTC. Seconds since UTC J2000 epoch (January 1, 2000, 12:00:00 UTC) (e.g., '31557600.000')\n"
        + "  "
        + TimeFormat.TAI_TUDAT.value
        + ": TAI. "
        + "Seconds since TAI J2000 epoch (January 1, 2000, 12:00:00 TAI = January 1, 2000, 11:59:28 UTC) (e.g., '31557628.000')\n"
        + "  "
        + TimeFormat.TT_TUDAT.value
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
        help=(
            "One or more output time formats. "
            "Provide multiple values to print multiple converted outputs per input time."
        ),
    )
    parser.add_argument(
        "time",
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
    def utc_iso_tudat_to_utc_posix(iso_time: str) -> float:

        return TimeConverter.utc_tudat_to_utc_posix(
            TimeConverter.utc_iso_tudat_to_utc_tudat(iso_time)
        )

    @staticmethod
    def utc_iso_tudat_to_utc_tudat(iso_time: str) -> float:
        # Convert ISO time to UTC J2000 seconds
        tudat_date_time = DateTime.from_iso_string(iso_time)
        return tudat_date_time.to_epoch()

    @staticmethod
    def utc_iso_tudat_to_tai_tudat(iso_time: str) -> float:
        # Convert ISO time to TAI J2000 seconds
        tudat_date_time = DateTime.from_iso_string(iso_time)

        if tudat_date_time.seconds >= 60.0:
            leap_second = 1.0
        else:
            leap_second = 0.0

        return (
            TimeConverter.utc_tudat_to_tai_tudat(tudat_date_time.to_epoch())
            - leap_second
        )

    @staticmethod
    def utc_iso_tudat_to_tt_tudat(iso_time: str) -> float:
        # Convert ISO time to TT J2000 seconds
        tudat_date_time = DateTime.from_iso_string(iso_time)

        if tudat_date_time.seconds >= 60.0:
            leap_second = 1.0
        else:
            leap_second = 0.0

        return (
            TimeConverter.utc_tudat_to_tt_tudat(tudat_date_time.to_epoch())
            - leap_second
        )

    @staticmethod
    def utc_iso_tudat_to_tdb_tudat(iso_time: str) -> float:
        # Convert ISO time to TDB J2000 secondsF
        tudat_date_time = DateTime.from_iso_string(iso_time)

        if tudat_date_time.seconds >= 60.0:
            leap_second = 1.0
        else:
            leap_second = 0.0

        return (
            TimeConverter.utc_tudat_to_tdb_tudat(tudat_date_time.to_epoch())
            - leap_second
        )

    @staticmethod
    def utc_iso_tudat_to_tdb_apx_tudat(iso_time: str) -> float:
        return TimeConverter.utc_iso_tudat_to_tt_tudat(iso_time)

    #
    # Conversion functions for POSIX epoch
    #

    @staticmethod
    def utc_posix_to_utc_iso_tudat(utc_posix_epoch: float) -> str:
        # Convert POSIX timestamp to ISO format
        tudat_date_time = DateTime.from_epoch(
            utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH
        )
        return tudat_date_time.to_iso_string(number_of_digits_seconds=3)

    @staticmethod
    def utc_posix_to_utc_tudat(utc_posix_epoch: float) -> float:
        # Convert POSIX timestamp to UTC J2000 seconds
        return utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH

    @staticmethod
    def utc_posix_to_tai_tudat(utc_posix_epoch: float) -> float:
        # Convert POSIX timestamp to TAI J2000 seconds
        utc_tudat_epoch = TimeConverter.utc_posix_to_utc_tudat(utc_posix_epoch)
        return TimeConverter.utc_tudat_to_tai_tudat(utc_tudat_epoch)

    @staticmethod
    def utc_posix_to_tt_tudat(utc_posix_epoch: float) -> float:
        # Convert POSIX timestamp to TT J2000 seconds
        utc_tudat_epoch = TimeConverter.utc_posix_to_utc_tudat(utc_posix_epoch)
        return TimeConverter.utc_tudat_to_tt_tudat(utc_tudat_epoch)

    @staticmethod
    def utc_posix_to_tdb_tudat(utc_posix_epoch: float) -> float:
        # Convert POSIX timestamp to TDB J2000 seconds
        utc_tudat_epoch = TimeConverter.utc_posix_to_utc_tudat(utc_posix_epoch)
        return TimeConverter.utc_tudat_to_tdb_tudat(utc_tudat_epoch)

    @staticmethod
    def utc_posix_to_tdb_apx_tudat(utc_posix_epoch: float) -> float:
        # Convert POSIX timestamp to approximate TDB J2000 seconds
        return TimeConverter.utc_posix_to_tt_tudat(utc_posix_epoch)

    #
    # Conversion functions for UTC J2000 epoch
    #

    @staticmethod
    def utc_tudat_to_utc_iso_tudat(utc_tudat_epoch: float) -> str:
        # Convert UTC J2000 seconds to ISO format
        tudat_date_time = DateTime.from_epoch(utc_tudat_epoch)
        return tudat_date_time.to_iso_string(number_of_digits_seconds=3)

    @staticmethod
    def utc_tudat_to_utc_posix(utc_tudat_epoch: float) -> float:
        # Convert UTC J2000 seconds to POSIX timestamp
        return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH

    @staticmethod
    def utc_tudat_to_tai_tudat(utc_tudat_epoch: float) -> float:
        # Convert UTC J2000 seconds to TAI J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=utc_tudat_epoch,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tai_scale,
        )

    @staticmethod
    def utc_tudat_to_tt_tudat(utc_tudat_epoch: float) -> float:
        # Convert UTC J2000 seconds to TT J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=utc_tudat_epoch,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tt_scale,
        )

    @staticmethod
    def utc_tudat_to_tdb_tudat(utc_tudat_epoch: float) -> float:
        # Convert UTC J2000 seconds to TDB J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=utc_tudat_epoch,
            input_scale=TimeScales.utc_scale,
            output_scale=TimeScales.tdb_scale,
        )

    @staticmethod
    def utc_tudat_to_tdb_apx_tudat(utc_tudat_epoch: float) -> float:
        # Convert UTC J2000 seconds to approximate TDB J2000 seconds
        return TimeConverter.utc_tudat_to_tt_tudat(utc_tudat_epoch)

    #
    # Conversion functions for TAI J2000 epoch
    #

    @staticmethod
    def tai_tudat_to_utc_iso_tudat(tai_tudat_epoch: float) -> str:
        # Convert TAI J2000 seconds to ISO format
        utc_tudat_epoch = TimeConverter.tai_tudat_to_utc_tudat(tai_tudat_epoch)
        return TimeConverter.utc_tudat_to_utc_iso_tudat(utc_tudat_epoch)

    @staticmethod
    def tai_tudat_to_utc_posix(tai_tudat_epoch: float) -> float:
        # Convert TAI J2000 seconds to POSIX timestamp
        utc_tudat_epoch = TimeConverter.tai_tudat_to_utc_tudat(tai_tudat_epoch)
        return TimeConverter.utc_tudat_to_utc_posix(utc_tudat_epoch)

    @staticmethod
    def tai_tudat_to_utc_tudat(tai_tudat_epoch: float) -> float:
        # Convert TAI J2000 seconds to UTC J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tai_tudat_epoch,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.utc_scale,
        )

    @staticmethod
    def tai_tudat_to_tt_tudat(tai_tudat_epoch: float) -> float:
        # Convert TAI J2000 seconds to TT J2000 seconds
        return tai_tudat_epoch + TT_EPOCH_MINUS_TAI_EPOCH

    @staticmethod
    def tai_tudat_to_tdb_tudat(tai_tudat_epoch: float) -> float:
        # Convert TAI J2000 seconds to TDB J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tai_tudat_epoch,
            input_scale=TimeScales.tai_scale,
            output_scale=TimeScales.tdb_scale,
        )

    @staticmethod
    def tai_tudat_to_tdb_apx_tudat(tai_tudat_epoch: float) -> float:
        # Convert TAI J2000 seconds to approximate TDB J2000 seconds
        return TimeConverter.tai_tudat_to_tt_tudat(tai_tudat_epoch)

    #
    # Conversion functions for TT J2000 epoch
    #

    @staticmethod
    def tt_tudat_to_utc_iso_tudat(tt_tudat_epoch: float) -> str:
        # Convert TT J2000 seconds to ISO format
        utc_tudat_epoch = TimeConverter.tt_tudat_to_utc_tudat(tt_tudat_epoch)
        return TimeConverter.utc_tudat_to_utc_iso_tudat(utc_tudat_epoch)

    @staticmethod
    def tt_tudat_to_utc_posix(tt_tudat_epoch: float) -> float:
        # Convert TT J2000 seconds to POSIX timestamp
        utc_tudat_epoch = TimeConverter.tt_tudat_to_utc_tudat(tt_tudat_epoch)
        return TimeConverter.utc_tudat_to_utc_posix(utc_tudat_epoch)

    @staticmethod
    def tt_tudat_to_utc_tudat(tt_tudat_epoch: float) -> float:
        # Convert TT J2000 seconds to UTC J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tt_tudat_epoch,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.utc_scale,
        )

    @staticmethod
    def tt_tudat_to_tai_tudat(tt_tudat_epoch: float) -> float:
        # Convert TT J2000 seconds to TAI J2000 seconds
        return tt_tudat_epoch - TT_EPOCH_MINUS_TAI_EPOCH

    @staticmethod
    def tt_tudat_to_tdb_tudat(tt_tudat_epoch: float) -> float:
        # Convert TT J2000 seconds to TDB J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tt_tudat_epoch,
            input_scale=TimeScales.tt_scale,
            output_scale=TimeScales.tdb_scale,
        )

    @staticmethod
    def tt_tudat_to_tdb_apx_tudat(tt_tudat_epoch: float) -> float:
        # Convert TT J2000 seconds to approximate TDB J2000 seconds
        return tt_tudat_epoch

    #
    # Conversion functions for TDB J2000 epoch
    #

    @staticmethod
    def tdb_tudat_to_utc_iso_tudat(tdb_tudat_epoch: float) -> str:
        # Convert TDB J2000 seconds to ISO format (via UTC)
        utc_tudat_epoch = TimeConverter.tdb_tudat_to_utc_tudat(tdb_tudat_epoch)
        return TimeConverter.utc_tudat_to_utc_iso_tudat(utc_tudat_epoch)

    @staticmethod
    def tdb_tudat_to_utc_posix(tdb_tudat_epoch: float) -> float:
        # Convert TDB J2000 seconds to POSIX timestamp
        utc_tudat_epoch = TimeConverter.tdb_tudat_to_utc_tudat(tdb_tudat_epoch)
        return TimeConverter.utc_tudat_to_utc_posix(utc_tudat_epoch)

    @staticmethod
    def tdb_tudat_to_utc_tudat(tdb_tudat_epoch: float) -> float:
        # Convert TDB J2000 seconds to UTC J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tdb_tudat_epoch,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.utc_scale,
        )

    @staticmethod
    def tdb_tudat_to_tai_tudat(tdb_tudat_epoch: float) -> float:
        # Convert TDB J2000 seconds to TAI J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tdb_tudat_epoch,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.tai_scale,
        )

    @staticmethod
    def tdb_tudat_to_tt_tudat(tdb_tudat_epoch: float) -> float:
        # Convert TDB J2000 seconds to TT J2000 seconds
        return tudat_time_scale_converter.convert_time(
            input_value=tdb_tudat_epoch,
            input_scale=TimeScales.tdb_scale,
            output_scale=TimeScales.tt_scale,
        )

    @staticmethod
    def tdb_tudat_to_tdb_apx_tudat(tdb_tudat_epoch: float) -> float:
        # Convert TDB J2000 seconds to approximate TDB J2000 seconds
        return tdb_tudat_epoch

    #
    # Conversion functions for Approximate TDB J2000 epoch
    #

    @staticmethod
    def tdb_apx_tudat_to_utc_iso_tudat(tdb_tudat_epoch: float) -> str:
        # Convert approximate TDB J2000 seconds to ISO format (via UTC)
        return TimeConverter.tt_tudat_to_utc_iso_tudat(tdb_tudat_epoch)

    @staticmethod
    def tdb_apx_tudat_to_utc_posix(tdb_tudat_epoch: float) -> float:
        # Convert approximate TDB J2000 seconds to POSIX timestamp
        return TimeConverter.tt_tudat_to_utc_posix(tdb_tudat_epoch)

    @staticmethod
    def tdb_apx_tudat_to_utc_tudat(tdb_tudat_epoch: float) -> float:
        # Convert approximate TDB J2000 seconds to UTC J2000 seconds
        return TimeConverter.tt_tudat_to_utc_tudat(tdb_tudat_epoch)

    @staticmethod
    def tdb_apx_tudat_to_tai_tudat(tdb_tudat_epoch: float) -> float:
        # Convert approximate TDB J2000 seconds to TAI J2000 seconds
        return TimeConverter.tt_tudat_to_tai_tudat(tdb_tudat_epoch)

    @staticmethod
    def tdb_apx_tudat_to_tt_tudat(tdb_tudat_epoch: float) -> float:
        # Convert approximate TDB J2000 seconds to TT J2000 seconds
        return tdb_tudat_epoch

    @staticmethod
    def tdb_apx_tudat_to_tdb_tudat(tdb_tudat_epoch: float) -> float:
        # Convert approximate TDB J2000 seconds to TDB J2000 seconds
        return tdb_tudat_epoch

    conversion_table = {
        TimeFormat.UTC_POSIX.value: {
            TimeFormat.UTC_ISO_TUDAT.value: utc_posix_to_utc_iso_tudat.__func__,
            TimeFormat.UTC_TUDAT.value: utc_posix_to_utc_tudat.__func__,
            TimeFormat.TAI_TUDAT.value: utc_posix_to_tai_tudat.__func__,
            TimeFormat.TT_TUDAT.value: utc_posix_to_tt_tudat.__func__,
            TimeFormat.TDB_TUDAT.value: utc_posix_to_tdb_tudat.__func__,
            TimeFormat.TDB_APX_TUDAT.value: utc_posix_to_tdb_apx_tudat.__func__,
        },
        TimeFormat.UTC_ISO_TUDAT.value: {
            TimeFormat.UTC_POSIX.value: utc_iso_tudat_to_utc_posix.__func__,
            TimeFormat.UTC_TUDAT.value: utc_iso_tudat_to_utc_tudat.__func__,
            TimeFormat.TAI_TUDAT.value: utc_iso_tudat_to_tai_tudat.__func__,
            TimeFormat.TT_TUDAT.value: utc_iso_tudat_to_tt_tudat.__func__,
            TimeFormat.TDB_TUDAT.value: utc_iso_tudat_to_tdb_tudat.__func__,
            TimeFormat.TDB_APX_TUDAT.value: utc_iso_tudat_to_tdb_apx_tudat.__func__,
        },
        TimeFormat.UTC_TUDAT.value: {
            TimeFormat.UTC_ISO_TUDAT.value: utc_tudat_to_utc_iso_tudat.__func__,
            TimeFormat.UTC_POSIX.value: utc_tudat_to_utc_posix.__func__,
            TimeFormat.TAI_TUDAT.value: utc_tudat_to_tai_tudat.__func__,
            TimeFormat.TT_TUDAT.value: utc_tudat_to_tt_tudat.__func__,
            TimeFormat.TDB_TUDAT.value: utc_tudat_to_tdb_tudat.__func__,
            TimeFormat.TDB_APX_TUDAT.value: utc_tudat_to_tdb_apx_tudat.__func__,
        },
        TimeFormat.TAI_TUDAT.value: {
            TimeFormat.UTC_ISO_TUDAT.value: tai_tudat_to_utc_iso_tudat.__func__,
            TimeFormat.UTC_POSIX.value: tai_tudat_to_utc_posix.__func__,
            TimeFormat.UTC_TUDAT.value: tai_tudat_to_utc_tudat.__func__,
            TimeFormat.TT_TUDAT.value: tai_tudat_to_tt_tudat.__func__,
            TimeFormat.TDB_TUDAT.value: tai_tudat_to_tdb_tudat.__func__,
            TimeFormat.TDB_APX_TUDAT.value: tai_tudat_to_tdb_apx_tudat.__func__,
        },
        TimeFormat.TT_TUDAT.value: {
            TimeFormat.UTC_ISO_TUDAT.value: tt_tudat_to_utc_iso_tudat.__func__,
            TimeFormat.UTC_POSIX.value: tt_tudat_to_utc_posix.__func__,
            TimeFormat.UTC_TUDAT.value: tt_tudat_to_utc_tudat.__func__,
            TimeFormat.TAI_TUDAT.value: tt_tudat_to_tai_tudat.__func__,
            TimeFormat.TDB_TUDAT.value: tt_tudat_to_tdb_tudat.__func__,
            TimeFormat.TDB_APX_TUDAT.value: tt_tudat_to_tdb_apx_tudat.__func__,
        },
        TimeFormat.TDB_TUDAT.value: {
            TimeFormat.UTC_ISO_TUDAT.value: tdb_tudat_to_utc_iso_tudat.__func__,
            TimeFormat.UTC_POSIX.value: tdb_tudat_to_utc_posix.__func__,
            TimeFormat.UTC_TUDAT.value: tdb_tudat_to_utc_tudat.__func__,
            TimeFormat.TAI_TUDAT.value: tdb_tudat_to_tai_tudat.__func__,
            TimeFormat.TT_TUDAT.value: tdb_tudat_to_tt_tudat.__func__,
            TimeFormat.TDB_APX_TUDAT.value: tdb_tudat_to_tdb_apx_tudat.__func__,
        },
        TimeFormat.TDB_APX_TUDAT.value: {
            TimeFormat.UTC_ISO_TUDAT.value: tdb_apx_tudat_to_utc_iso_tudat.__func__,
            TimeFormat.UTC_POSIX.value: tdb_apx_tudat_to_utc_posix.__func__,
            TimeFormat.UTC_TUDAT.value: tdb_apx_tudat_to_utc_tudat.__func__,
            TimeFormat.TAI_TUDAT.value: tdb_apx_tudat_to_tai_tudat.__func__,
            TimeFormat.TT_TUDAT.value: tdb_apx_tudat_to_tt_tudat.__func__,
            TimeFormat.TDB_TUDAT.value: tdb_apx_tudat_to_tdb_tudat.__func__,
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

        if args.input_format == TimeFormat.UTC_ISO_TUDAT.value:
            time_value = value
        else:
            time_value = float(value)

        for output_format in args.output_format.split(","):
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
