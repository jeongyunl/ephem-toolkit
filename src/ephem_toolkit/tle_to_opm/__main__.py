"""Convert TLE state histories to OPM through numerical arc fitting."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from ephem_toolkit.oem_to_opm import main as oem_to_opm_main
from ephem_toolkit.oem_to_opm.oem_to_opm_cli import build_arg_parser, parse_arguments


def main(argv=None) -> None:
    """Propagate a TLE with SGP4 and fit an OPM numerical initial state."""
    if argv is None:
        argv = list(sys.argv[1:])
    parser = build_arg_parser()
    parser.prog = "tle-to-opm"
    args = parse_arguments(parser, argv)
    if args.fit_model != "numerical":
        parser.error("tle-to-opm requires --fit-model numerical")

    from ephem_toolkit.propagate_omm.propagation import (
        propagate_tle_sgp4,
        read_tle_input,
    )
    import ephem_toolkit.core.tle as tle

    tle_data = read_tle_input(args.input_oem)
    start = tle.tle_epoch_to_datetime(tle_data.epoch_year, tle_data.epoch_day)
    generated = io.StringIO()
    with redirect_stdout(generated):
        propagate_tle_sgp4(
            tle_data, start, start + args.fit_span, 60.0, False, "-"
        )

    forwarded = _forward_arguments(argv, args.input_oem, args.output_opm)
    forwarded.extend(["--source-model", "sgp4"])
    # Feed the generated OEM to the common fitter through stdin.
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(generated.getvalue())
    try:
        oem_to_opm_main(["--fit-model", "numerical", "-", *forwarded])
    finally:
        sys.stdin = original_stdin


def _forward_arguments(argv: list[str], input_path: str, output_path: str) -> list[str]:
    from ephem_toolkit.omm_to_opm.__main__ import _forward_arguments as forward

    return forward(argv, input_path, output_path)


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
