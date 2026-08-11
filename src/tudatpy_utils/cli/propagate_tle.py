#!/usr/bin/env python3

"""Command-line adapter for TLE propagation."""


def main() -> None:
    from tudatpy_utils.propagate_tle.propagate_tle import main as command_main

    command_main()


if __name__ == "__main__":
    main()
