"""Adapters for command-line entry points."""


def propagate_orbit_main() -> None:
    """Run the orbit propagation script as a console command."""
    from propagate_orbit.propagate_orbit import main

    main()
