#!/usr/bin/env python3

"""Command-line adapter for TLE downloads."""


def main() -> None:
    from tudatpy_utils.download_tle.download_tle import main as command_main

    command_main()


if __name__ == "__main__":
    main()
