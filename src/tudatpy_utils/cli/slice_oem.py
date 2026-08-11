#!/usr/bin/env python3

"""Command-line adapter for OEM slicing."""


def main() -> None:
    from tudatpy_utils.slice_oem.slice_oem import main as command_main

    command_main()


if __name__ == "__main__":
    main()
