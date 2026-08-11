#!/usr/bin/env python3

"""Command-line adapter for TLE fit evaluation."""


def main() -> None:
    from tudatpy_utils.oem_to_omm.evaluate_fit_tle import main as command_main

    command_main()