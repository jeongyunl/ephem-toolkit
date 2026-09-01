#!/usr/bin/env python3
"""TLE propagation wrapper around the OMM propagation command.

This utility is a thin compatibility layer around the canonical OMM propagator.
It reuses the same CLI and propagation logic, but always appends the
``--tle`` flag so the input is interpreted as raw TLE text.
"""

from __future__ import annotations

import sys

from ephem_toolkit.propagate_omm import propagate_omm


def main(argv=None) -> int:
    """Invoke the OMM propagation workflow in TLE mode."""
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)
    if "--tle" not in argv:
        argv.insert(0, "--tle")
    return propagate_omm.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
