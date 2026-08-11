#!/usr/bin/env python3

"""Command-line adapter for OEM comparison."""


def main() -> None:
    from tudatpy_utils.diff_oem.diff_oem import main as command_main

    command_main()