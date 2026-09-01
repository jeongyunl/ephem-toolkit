#!/usr/bin/env python3
"""OEM-to-TLE wrapper around the OEM-to-OMM conversion command."""

from __future__ import annotations

import sys

from ephem_toolkit.oem_to_omm import __main__ as oem_to_omm


def main(argv=None) -> None:
    """Invoke the OEM-to-OMM workflow in TLE conversion mode."""
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    filtered_arguments: list[str] = []
    skip_next = False
    for argument in argv:
        if skip_next:
            skip_next = False
            continue
        if argument == "--mode":
            skip_next = True
            continue
        if argument.startswith("--mode="):
            continue
        filtered_arguments.append(argument)

    oem_to_omm.main(["--mode", "tle", *filtered_arguments])


if __name__ == "__main__":
    main()
