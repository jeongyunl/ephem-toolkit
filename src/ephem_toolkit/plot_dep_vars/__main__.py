#!/usr/bin/env python3
"""Command-line entry point for dependent-variable plotting."""

from __future__ import annotations

import signal
from types import FrameType
from typing import Any, Sequence

from .plot_dependent_variables_cli import (
    PlotDependentVariablesArgs,
    build_arg_parser,
    parse_arguments,
)


def main(argv=None) -> None:
    """Parse arguments and plot the requested dependent-variable CSV."""
    cli_parser = build_arg_parser()
    cli_args: PlotDependentVariablesArgs = parse_arguments(cli_parser, argv)

    from matplotlib import pyplot as plt
    from .plot_dependent_variables import plot_dependent_variables_from_csv

    def handle_sigint(_signum: int, _frame: FrameType | None) -> None:
        plt.close("all")

    previous_sigint_handler: Any = signal.signal(signal.SIGINT, handle_sigint)

    try:

        def handle_key_press(event: Any) -> None:
            if event.key in {"ctrl+c", "control+c"}:
                plt.close("all")

        # Keep animation objects alive until plt.show() returns.
        animations: list[Any] = []
        if cli_args.dep_vars_csv is not None:
            animation = plot_dependent_variables_from_csv(
                dep_var_csv_path=cli_args.dep_vars_csv,
                satellite_name=cli_args.name,
                show=False,
                duration_s=cli_args.duration,
            )
            if animation is not None:
                animations.append(animation)

        for figure_number in plt.get_fignums():
            figure = plt.figure(figure_number)
            figure.canvas.mpl_connect("key_press_event", handle_key_press)

        plt.show()
    except KeyboardInterrupt:
        plt.close("all")
        return
    finally:
        signal.signal(signal.SIGINT, previous_sigint_handler)


def cli(argv: Sequence[str] | None = None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
