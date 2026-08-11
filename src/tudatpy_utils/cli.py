"""Adapters for command-line entry points."""

import runpy


def propagate_orbit_main() -> None:
    """Run the legacy orbit propagation script as a console command."""
    runpy.run_module("propagation.propagate_orbit", run_name="__main__")
