"""Tests for common/spice_utils.py — SPICE kernel path and loading helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, call

import pytest

import core.spice_utils as spice_utils


def test_load_kernel_loads_each_kernel_path_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Load a kernel once while allowing distinct kernel paths."""
    kernel_path = tmp_path / "spice-kernels"
    load_kernel_mock = Mock()

    monkeypatch.setattr(spice_utils, "_loaded_kernels", set())
    monkeypatch.setattr(
        spice_utils.spice,
        "load_kernel",
        load_kernel_mock,
    )

    spice_utils.load_kernel("naif0012.tls", kernel_path)
    spice_utils.load_kernel("naif0012.tls", kernel_path)
    spice_utils.load_kernel("pck00011.tpc", kernel_path)

    assert load_kernel_mock.call_count == 2
    assert load_kernel_mock.call_args_list == [
        call(str(kernel_path / "naif0012.tls")),
        call(str(kernel_path / "pck00011.tpc")),
    ]
