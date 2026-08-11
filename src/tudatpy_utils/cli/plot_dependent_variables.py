#!/usr/bin/env python3

"""Command-line adapter for dependent-variable plotting."""


def main() -> None:
    from tudatpy_utils.plot_dep_vars.plot_dependent_variables import main as command_main

    command_main()