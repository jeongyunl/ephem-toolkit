"""Fit a TLE reference arc to an OPM numerical initial state."""


def main(argv=None):
    from .__main__ import main as implementation

    return implementation(argv)


def cli(argv=None) -> int:
    from .__main__ import cli as implementation

    return implementation(argv)


__all__ = ["cli", "main"]
