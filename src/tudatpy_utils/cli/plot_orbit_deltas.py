#!/usr/bin/env python3

"""Command-line adapter for orbit-delta plotting."""


def main() -> None:
    from tudatpy_utils.plot_orbit_deltas.plot_orbit_deltas import main as command_main

    command_main()