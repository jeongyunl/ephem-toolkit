"""Verify package-resource behavior for the Poetry distribution."""

from importlib.resources import files


def test_package_root_is_resource_accessible() -> None:
    """The installed package root exposes its module resources."""
    package_root = files("ephem_toolkit")

    assert (package_root / "__init__.py").is_file()
