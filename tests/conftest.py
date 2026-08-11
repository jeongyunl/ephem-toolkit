"""Shared pytest setup for the source-layout package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tudatpy_utils
