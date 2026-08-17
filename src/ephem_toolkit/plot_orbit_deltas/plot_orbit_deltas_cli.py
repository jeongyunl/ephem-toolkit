"""CLI argument parsing for orbit-delta plotting."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for plotting multiple orbit trajectories."""
    parser = argparse.ArgumentParser(
        description="Plot multiple orbit trajectories with various views and RTN coordinates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot single orbit
  python3 plot_orbits.py reference.oem

  # Plot reference orbit with comparison orbits
  python3 plot_orbits.py reference.oem comparison1.oem comparison2.oem

  # Save output to file
  python3 plot_orbits.py reference.oem comparison.oem -o orbits.png
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="OEM or raw-state files. First file is the reference orbit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path for saving the figure (e.g., orbits.png)",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        default=None,
        help="Duration of data to analyze from start (e.g., 1h, 30m, 3600s)",
    )
    parser.add_argument(
        "--time-unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help="Time unit for time series plots: m/minute/minutes or h/hour/hours (default: hours)",
    )

    return parser.parse_args()
