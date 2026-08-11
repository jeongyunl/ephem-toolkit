#!/usr/bin/env python3

"""Command-line adapter for TLE information."""


def main() -> None:
    from tudatpy_utils.tle_info.tle_info import main as command_main

    command_main()


if __name__ == "__main__":
    main()
