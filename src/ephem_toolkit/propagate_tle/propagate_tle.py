#!/usr/bin/env python3
"""TLE propagation wrapper around the OMM propagation command.

This utility is a thin compatibility layer around the canonical OMM propagator.
It reuses the same CLI and propagation logic, but always appends the
``--tle`` flag so the input is interpreted as raw TLE text.
"""

from __future__ import annotations

import sys

from ephem_toolkit.propagate_omm import propagate_omm
from ephem_toolkit.propagate_omm.propagate_omm import resolve_time_bounds
from ephem_toolkit.propagate_omm.propagate_omm_cli import PropagateOmmArgs


def parse_arguments() -> PropagateOmmArgs:
    """Parse CLI arguments for the TLE wrapper.

    The wrapper delegates to the OMM parser but forces the TLE mode flag so the
    same propagation logic handles TLE input correctly.
    """
    argv = list(sys.argv[1:])
    if "--tle" not in argv:
        argv.insert(0, "--tle")
    sys.argv = [sys.argv[0], *argv]
    args = propagate_omm.parse_arguments()
    args.tle_file = args.input_file
    return args


def main() -> int:
    """Invoke the OMM propagation workflow in TLE mode."""
    argv = list(sys.argv[1:])
    if "--tle" not in argv:
        argv.insert(0, "--tle")
    sys.argv = [sys.argv[0], *argv]
    return propagate_omm.main()


if __name__ == "__main__":
    raise SystemExit(main())
