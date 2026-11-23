"""Mapped derived-buffer allocation and memory advice helpers."""

from __future__ import annotations

import mmap

import numpy as np

import ephem_toolkit.play_oem.oem_data_store as public_store


def _mapped_float_array(shape: tuple[int, int]) -> np.ndarray:
    rows, columns = shape
    if rows < 1:
        return np.empty(shape, dtype=np.float64)
    flags = getattr(mmap, "MAP_PRIVATE", None)
    anonymous_flag = getattr(
        mmap,
        "MAP_ANONYMOUS",
        getattr(mmap, "MAP_ANON", None),
    )
    if flags is None or anonymous_flag is None:
        mapping = mmap.mmap(
            -1,
            rows * columns * np.dtype(np.float64).itemsize,
        )
    else:
        mapping = mmap.mmap(
            -1,
            rows * columns * np.dtype(np.float64).itemsize,
            flags=flags | anonymous_flag,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
        )
    return np.ndarray(shape, dtype=np.float64, buffer=mapping)


def _mapping_for_buffer(buffer: np.ndarray) -> mmap.mmap | None:
    owner: object = buffer
    while isinstance(owner, np.ndarray):
        owner = owner.base
    return owner if isinstance(owner, mmap.mmap) else None


def _mapped_buffer_id(buffer: np.ndarray) -> int:
    mapping = _mapping_for_buffer(buffer)
    return id(mapping) if mapping is not None else id(buffer)


def _madvise_chunk(
    buffer: np.ndarray,
    chunk_index: int,
    row_count: int,
    columns: int,
    advice: int,
) -> None:
    mapping = _mapping_for_buffer(buffer)
    if mapping is None:
        raise RuntimeError("derived buffer is not backed by an mmap")
    bytes_per_row = columns * np.dtype(np.float64).itemsize
    chunk_size = public_store.DERIVED_CHUNK_SIZE
    start = chunk_index * chunk_size * bytes_per_row
    rows = min(chunk_size, row_count - chunk_index * chunk_size)
    length = rows * bytes_per_row
    if length:
        mapping.madvise(advice, start, length)
