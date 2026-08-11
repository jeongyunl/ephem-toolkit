#!/usr/bin/env python3

"""Command-line adapter for orbit plotting."""


def main() -> None:
    from tudatpy_utils.plot_orbit.plot_orbit import main as command_main

    command_main()