#!/usr/bin/env python3

"""Command-line adapter for Keplerian propagation."""


def main() -> None:
    from tudatpy_utils.propagate_kepler.propagate_kepler import main as command_main

    command_main()