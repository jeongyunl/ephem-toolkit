#!/usr/bin/env python3

"""Command-line adapter for OEM transformation."""


def main() -> None:
    from tudatpy_utils.xform_oem.xform_oem import main as command_main

    command_main()