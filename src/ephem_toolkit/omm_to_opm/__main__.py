"""Convert OMM state histories to OPM through numerical arc fitting."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from ephem_toolkit.oem_to_opm import main as oem_to_opm_main
from ephem_toolkit.oem_to_opm.oem_to_opm_cli import (
    build_arg_parser,
    parse_arguments,
)


def main(argv=None) -> None:
    """Propagate an OMM using its declared model and fit an OPM state."""
    if argv is None:
        argv = list(sys.argv[1:])
    parser = build_arg_parser()
    parser.prog = "omm-to-opm"
    args = parse_arguments(parser, argv)

    if args.fit_model != "numerical":
        parser.error("omm-to-opm requires --fit-model numerical")

    import ephem_toolkit.core.time_utils as time_utils
    from ephem_toolkit.propagate_omm.propagation import (
        propagate_omm_dsst,
        propagate_omm_kepler,
        propagate_omm_sgp4,
    )
    from ephem_toolkit.propagate_omm.propagation import read_omm_input

    omm_data = read_omm_input(args.input_oem)
    start = time_utils.iso8601_to_datetime(omm_data.epoch)
    stop = start + args.fit_span
    generated = io.StringIO()
    with redirect_stdout(generated):
        if omm_data.tle_parameters is not None:
            propagate_omm_sgp4(omm_data, start, stop, 60.0, False, "-")
        elif omm_data.mean_element_theory.upper() == "DSST":
            propagate_omm_dsst(omm_data, start, stop, 60.0, False, "-")
        else:
            propagate_omm_kepler(omm_data, start, stop, 60.0, False, "-")

    # Reuse the complete OEM-to-OPM numerical CLI and its shared fitter.
    forwarded = _forward_arguments(argv, args.input_oem, args.output_opm)
    forwarded.extend(["--source-model", omm_data.mean_element_theory])
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(generated.getvalue())
    try:
        oem_to_opm_main(["--fit-model", "numerical", "-", *forwarded])
    finally:
        sys.stdin = original_stdin


def _forward_arguments(argv: list[str], input_path: str, output_path: str) -> list[str]:
    """Remove wrapper-owned positional/output/model arguments for delegation."""
    forwarded: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == input_path:
            index += 1
            continue
        if argument in {"-o", "--output", "--fit-model"}:
            index += 2
            continue
        if argument.startswith("--output=") or argument.startswith("--fit-model="):
            index += 1
            continue
        forwarded.append(argument)
        index += 1
    forwarded.extend(["--output", output_path])
    return forwarded


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
