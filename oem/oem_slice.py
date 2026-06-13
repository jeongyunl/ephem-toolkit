#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path to import common utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.oem import CcsdsOem, write_states


def parse_slice(slice_str: str) -> slice | int:
    """Parse a Python-style slice string (e.g., '0:10', '::2', '5', '-5:').

    Returns either a slice object or an int for single indices.
    """
    # Handle single index
    if ":" not in slice_str:
        try:
            return int(slice_str)
        except ValueError:
            raise ValueError(f"Invalid index: {slice_str}")

    # Handle slice notation
    parts = slice_str.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid slice: {slice_str}")

    start = int(parts[0]) if parts[0] else None
    stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
    step = int(parts[2]) if len(parts) > 2 and parts[2] else None

    return slice(start, stop, step)


def main() -> None:
    """Read OEM file name from CLI argument and load it."""
    parser = argparse.ArgumentParser(description="Load and slice CCSDS OEM file states")
    parser.add_argument("oem_file", help="Path to OEM file")
    parser.add_argument(
        "-s",
        "--slice",
        help="Python-style slice index (e.g., '0:10', '::2', '5', '-5:')",
        default=None,
    )
    parser.add_argument(
        "--oem",
        action="store_true",
        help="Output in OEM file format",
    )

    args = parser.parse_args()

    oem_file = Path(args.oem_file)
    oem = CcsdsOem.from_source(oem_file)

    if args.slice:
        slice_obj = parse_slice(args.slice)
        sliced_states = oem.states[slice_obj]

        # Handle both single index (returns tuple) and slice (returns list)
        if isinstance(slice_obj, int):
            # Single index returns a tuple (epoch, state)
            epoch, state = sliced_states
            sliced_states_list = [(epoch, state)]
        else:
            # Slice returns a list of tuples
            sliced_states_list = sliced_states

        # Update time fields based on selected slice
        if sliced_states_list:
            first_epoch = sliced_states_list[0][0]
            last_epoch = sliced_states_list[-1][0]

            oem.meta.start_time = first_epoch.isoformat()
            oem.meta.stop_time = last_epoch.isoformat()
            oem.meta.useable_start_time = ""
            oem.meta.useable_stop_time = ""

        if args.oem:
            # Output in OEM file format
            oem.states = sliced_states_list
            oem.to_file(sys.stdout)
        else:
            # Output raw states
            states_dict = {epoch: state for epoch, state in sliced_states_list}
            write_states(sys.stdout, states_dict)


if __name__ == "__main__":
    main()
