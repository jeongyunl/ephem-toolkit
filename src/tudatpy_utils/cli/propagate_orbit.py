#!/usr/bin/env python3

"""Command-line adapter for orbit propagation."""


def main() -> None:
    from tudatpy_utils.propagate_orbit.propagate_orbit import main as command_main

    command_main()


if __name__ == "__main__":
    main()
