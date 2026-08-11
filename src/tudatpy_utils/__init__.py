"""Python utilities for TudatPy astrodynamics workflows."""

import importlib
import sys

__version__ = "0.1.0"

for _package_name in ("common", "diff_oem", "oem_to_omm", "propagation", "plotting"):
	_package = importlib.import_module(_package_name)
	sys.modules[f"{__name__}.{_package_name}"] = _package
