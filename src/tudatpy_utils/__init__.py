"""Python utilities for TudatPy astrodynamics workflows."""

import importlib
import sys

__version__ = "0.1.0"

from . import core as _core
from .core import ccsds as _ccsds
from .core import interpolator as _interpolator

for _package_name in (
    "diff_oem",
    "download_tle",
    "oem_to_omm",
    "omm_to_tle",
    "plot_dep_vars",
    "plot_orbit",
    "plot_orbit_deltas",
    "propagate_kepler",
    "propagate_orbit",
    "propagate_tle",
    "slice_oem",
    "tle_info",
    "tle_to_omm",
    "xform_oem",
):
    _module = importlib.import_module(f".{_package_name}", __name__)
    sys.modules[_package_name] = _module
