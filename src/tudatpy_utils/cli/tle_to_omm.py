#!/usr/bin/env python3

"""Command-line adapter for TLE to OMM conversion."""


def main() -> None:
    from tudatpy_utils.tle_to_omm.tle_to_omm import main as command_main

    command_main()


if __name__ == "__main__":
    main()
