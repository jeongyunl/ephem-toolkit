"""Output formatting for OEM comparison results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

import ephem_toolkit.core.interpolator as interpolator
import ephem_toolkit.core.time_utils as time_utils

from .data_structures import ComparisonResult
from .debug import debug_print, debug_print_time_range


@dataclass
class ComparisonOutput:
    """Comparison rows and options used to render a report with statistics."""

    comparison_results: list[tuple[float, ComparisonResult | None]]
    """Comparison results keyed by their query epochs."""

    reference_interpolator: interpolator.Interpolator
    """Interpolator used for reference states."""

    comparison_interpolator: interpolator.Interpolator
    """Interpolator used for comparison states."""

    verbose: bool
    """Whether to include component-wise differences."""

    rtn: bool
    """Whether to include reference-frame RTN differences."""

    title: str | None = None
    """Optional report title."""

    fit_description: str | None = None
    """Optional description of the applied transformation fit."""

    @staticmethod
    def _get_output_columns(
        include_time_difference: bool,
        verbose: bool,
        rtn: bool,
        include_comparison_epoch: bool,
    ) -> list[str]:
        """Return output column names for the selected comparison details."""
        columns: list[str] = ["index", "reference\nepoch"]
        if include_comparison_epoch:
            columns.append("comparison\nepoch")
        if include_time_difference:
            columns.append("time\ndifference\n(s)")
        columns.extend(["position\ndifference\n(km)", "velocity\ndifference\n(km/s)"])
        if verbose:
            columns.extend(
                [
                    "dX\n(km)",
                    "dY\n(km)",
                    "dZ\n(km)",
                    "dVX\n(km/s)",
                    "dVY\n(km/s)",
                    "dVZ\n(km/s)",
                ]
            )
        if rtn:
            columns.extend(
                [
                    "RTN r\n(km)",
                    "RTN t\n(km)",
                    "RTN n\n(km)",
                    "RTN vr\n(km/s)",
                    "RTN vt\n(km/s)",
                    "RTN vn\n(km/s)",
                ]
            )
        return columns

    @staticmethod
    def _get_output_column_widths(columns: list[str]) -> list[int]:
        """Return shared display widths for header and data columns."""
        widths: list[int] = []
        for column in columns:
            label_width: int = max(map(len, column.split("\n")))
            if column == "index":
                data_width: int = 5
            elif "epoch" in column:
                data_width = 24
            else:
                data_width = 10
            widths.append(max(label_width, data_width))
        return widths

    @classmethod
    def _format_output_row(cls, values: list[str], columns: list[str]) -> str:
        """Format output values in consistently spaced columns."""
        column_widths = cls._get_output_column_widths(columns)
        aligned_values = [
            f"{value:>{width}}" for value, width in zip(values, column_widths)
        ]
        return "  ".join(aligned_values).rstrip()

    @classmethod
    def _format_output_header(cls, columns: list[str]) -> str:
        """Format a multi-line header with aligned column labels."""
        header_lines = [column.split("\n") for column in columns]
        column_widths = cls._get_output_column_widths(columns)
        lines: list[str] = []
        for line_index in range(max(map(len, header_lines))):
            line_values = [
                (
                    lines_for_column[line_index]
                    if line_index < len(lines_for_column)
                    else ""
                )
                for lines_for_column in header_lines
            ]
            lines.append(
                "  ".join(
                    f"{value:<{width}}"
                    for value, width in zip(line_values, column_widths)
                ).rstrip()
            )
        return "\n".join(lines)

    def print_header(
        self,
        include_time_difference: bool,
        include_comparison_epoch: bool,
    ) -> None:
        """Print this report's aligned column header.

        Parameters
        ----------
        include_time_difference : bool
            Whether to include the time-difference column.
        include_comparison_epoch : bool
            Whether to include the comparison epoch column.
        """
        columns = self._get_output_columns(
            include_time_difference,
            self.verbose,
            self.rtn,
            include_comparison_epoch,
        )
        print(self._format_output_header(columns))

    def print_result(
        self,
        index: int,
        comparison_result: ComparisonResult | None,
        include_comparison_epoch: bool,
        query_epoch: datetime | None,
    ) -> None:
        """Print one result row using this report's formatting options.

        Parameters
        ----------
        index : int
            One-based row index.
        comparison_result : ComparisonResult or None
            Result to render, or ``None`` for an invalid boundary sample.
        include_comparison_epoch : bool
            Whether to include the comparison epoch column.
        query_epoch : datetime or None
            Query epoch used when ``comparison_result`` is ``None``.
        """
        if comparison_result is None:
            if query_epoch is None:
                raise ValueError("query_epoch is required for an empty comparison row")
            values = [str(index), time_utils.datetime_to_iso8601(query_epoch)]
            if include_comparison_epoch:
                values.append("")
            columns = self._get_output_columns(
                include_time_difference=False,
                verbose=self.verbose,
                rtn=self.rtn,
                include_comparison_epoch=include_comparison_epoch,
            )
            values.extend([""] * (len(columns) - len(values)))
            print(self._format_output_row(values, columns))
            return

        values: list[str] = [
            str(index),
            time_utils.datetime_to_iso8601(comparison_result.reference_epoch),
        ]
        if include_comparison_epoch:
            values.append(
                time_utils.datetime_to_iso8601(comparison_result.comparison_epoch)
            )
        if comparison_result.time_diff_s is not None:
            values.append(f"{comparison_result.time_diff_s:.6f}")
        values.extend(
            [
                f"{comparison_result.position_diff_magnitude_km:.3f}",
                f"{comparison_result.velocity_diff_magnitude_km_s:.6f}",
            ]
        )
        if self.verbose:
            values.extend(
                [f"{comparison_result.position_diff_km[i]:+.3f}" for i in range(3)]
                + [f"{comparison_result.velocity_diff_km_s[i]:+.6f}" for i in range(3)]
            )
        if self.rtn:
            values.extend(
                [f"{comparison_result.rtn_position_km[i]:+.3f}" for i in range(3)]
                + [f"{comparison_result.rtn_velocity_km_s[i]:+.6f}" for i in range(3)]
            )
        columns = self._get_output_columns(
            comparison_result.time_diff_s is not None,
            self.verbose,
            self.rtn,
            include_comparison_epoch,
        )
        print(self._format_output_row(values, columns))

    def print_statistics(self, include_time_difference: bool) -> None:
        """Print summary statistics for this report's comparison results.

        Parameters
        ----------
        include_time_difference : bool
            Whether to include time-difference statistics.
        """
        comparison_results = [
            result for _, result in self.comparison_results if result is not None
        ]
        if not comparison_results:
            print("\nStatistics: no valid comparison results")
            return

        criteria: list[tuple[str, np.ndarray]] = [
            (
                "position difference (km)",
                np.array(
                    [result.position_diff_magnitude_km for result in comparison_results]
                ),
            ),
            (
                "velocity difference (km/s)",
                np.array(
                    [
                        result.velocity_diff_magnitude_km_s
                        for result in comparison_results
                    ]
                ),
            ),
        ]
        if include_time_difference:
            criteria.insert(
                0,
                (
                    "time difference (s)",
                    np.array(
                        [
                            result.time_diff_s
                            for result in comparison_results
                            if result.time_diff_s is not None
                        ]
                    ),
                ),
            )
        if self.verbose:
            criteria.extend(
                [
                    (
                        f"d{axis} (km)",
                        np.array(
                            [
                                result.position_diff_km[index]
                                for result in comparison_results
                            ]
                        ),
                    )
                    for index, axis in enumerate(("X", "Y", "Z"))
                ]
            )
            criteria.extend(
                [
                    (
                        f"dV{axis} (km/s)",
                        np.array(
                            [
                                result.velocity_diff_km_s[index]
                                for result in comparison_results
                            ]
                        ),
                    )
                    for index, axis in enumerate(("X", "Y", "Z"))
                ]
            )
        if self.rtn:
            criteria.extend(
                [
                    (
                        f"RTN {axis} (km)",
                        np.array(
                            [
                                result.rtn_position_km[index]
                                for result in comparison_results
                            ]
                        ),
                    )
                    for index, axis in enumerate(("r", "t", "n"))
                ]
            )
        print("\nStatistics (mean, std, min, max)")
        rtn_statistics_started = False
        for label, values in criteria:
            if label.startswith("RTN ") and not rtn_statistics_started:
                print("\nStatistics (std, min, max)")
                rtn_statistics_started = True
            if label.endswith("(km)"):
                value_format = "+.3f"
            elif label.endswith("(km/s)"):
                value_format = "+.6f"
            else:
                value_format = "+.9g"
            if label.startswith("RTN "):
                print(
                    f"{label}: {format(np.std(values), value_format)}, "
                    f"{format(np.min(values), value_format)}, "
                    f"{format(np.max(values), value_format)}"
                )
            else:
                print(
                    f"{label}: {format(np.mean(values), value_format)}, "
                    f"{format(np.std(values), value_format)}, "
                    f"{format(np.min(values), value_format)}, "
                    f"{format(np.max(values), value_format)}"
                )

    def print(self) -> None:
        """Print comparison rows followed by their summary statistics."""
        valid_results = [r for _, r in self.comparison_results if r is not None]
        debug_print(
            f"print: title='{self.title}', "
            f"total_results={len(self.comparison_results)}, "
            f"valid_results={len(valid_results)}",
            "output",
        )
        if self.comparison_results:
            first_epoch_s = self.comparison_results[0][0]
            last_epoch_s = self.comparison_results[-1][0]
            debug_print_time_range(
                "print: query epoch range",
                first_epoch_s,
                last_epoch_s,
            )
        if valid_results:
            first_ref = valid_results[0].reference_epoch
            last_ref = valid_results[-1].reference_epoch
            first_cmp = valid_results[0].comparison_epoch
            last_cmp = valid_results[-1].comparison_epoch
            debug_print_time_range("print: ref data time range", first_ref, last_ref)
            debug_print_time_range("print: cmp data time range", first_cmp, last_cmp)
        if self.title is not None:
            print(f"\n{self.title}")
        self.print_header(
            include_time_difference=False,
            include_comparison_epoch=False,
        )
        for index, (query_epoch_s, comparison_result) in enumerate(
            self.comparison_results, start=1
        ):
            self.print_result(
                index,
                comparison_result,
                include_comparison_epoch=False,
                query_epoch=time_utils.tt_s_to_datetime(query_epoch_s),
            )
        if self.fit_description is not None:
            print("\n" + self.fit_description)
        self.print_statistics(include_time_difference=False)
