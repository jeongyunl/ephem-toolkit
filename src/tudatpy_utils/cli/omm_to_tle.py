#!/usr/bin/env python3

"""Command-line adapter for OMM to TLE conversion."""


def main() -> None:
    from tudatpy_utils.omm_to_tle.omm_to_tle import main as command_main

    command_main()