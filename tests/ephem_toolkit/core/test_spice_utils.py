"""Tests for core/spice_utils.py — SPICE kernel path and loading helpers."""

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


def test_get_spice_kernel_path_uses_valid_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    kernel_path = tmp_path / "kernels"
    kernel_path.mkdir()
    cache_file = tmp_path / "cache" / "spice_kernel_path"
    cache_file.parent.mkdir()
    cache_file.write_text(str(kernel_path), encoding="utf-8")
    monkeypatch.setattr(spice_utils, "_SPICE_CACHE_FILE", cache_file)

    assert spice_utils.get_spice_kernel_path() == str(kernel_path)


def test_get_spice_kernel_path_resolves_and_caches_missing_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    kernel_path = tmp_path / "resolved-kernels"
    kernel_path.mkdir()
    cache_file = tmp_path / "cache" / "spice_kernel_path"
    monkeypatch.setattr(spice_utils, "_SPICE_CACHE_FILE", cache_file)
    monkeypatch.setattr("tudatpy.data.get_spice_kernel_path", lambda: str(kernel_path))

    assert spice_utils.get_spice_kernel_path() == str(kernel_path)
    assert cache_file.read_text(encoding="utf-8") == str(kernel_path)


def test_get_spice_kernel_path_tolerates_cache_io_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_directory = tmp_path / "cache-is-directory"
    cache_directory.mkdir()
    resolved_path = tmp_path / "resolved-kernels"
    resolved_path.mkdir()
    monkeypatch.setattr(spice_utils, "_SPICE_CACHE_FILE", cache_directory)
    monkeypatch.setattr(
        "tudatpy.data.get_spice_kernel_path", lambda: str(resolved_path)
    )

    assert spice_utils.get_spice_kernel_path() == str(resolved_path)


def test_load_kernel_uses_resolved_default_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    load_kernel_mock = Mock()
    monkeypatch.setattr(spice_utils, "_loaded_kernels", set())
    monkeypatch.setattr(spice_utils, "get_spice_kernel_path", lambda: str(tmp_path))
    monkeypatch.setattr(spice_utils.spice, "load_kernel", load_kernel_mock)

    spice_utils.load_kernel("naif0012.tls")

    load_kernel_mock.assert_called_once_with(str(tmp_path / "naif0012.tls"))
