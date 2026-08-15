"""Type definitions for OEM comparison operations."""

from __future__ import annotations

import numpy as np

State = tuple[float, np.ndarray]
"""Single OEM-like state as ``(timestamp, state_m)``."""

StatePair = tuple[State, State]
"""Reference/comparison state pair used by comparisons and fitting."""
