"""Headless tests for plot artists backed by column-group views."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch
from matplotlib.path import Path

from ephem_toolkit.play_oem.oem_data_store import ColumnGroupView, RowSpan


def test_path_patch_and_line_collection_keep_column_pair_through_draw() -> None:
    source = np.arange(70_000, dtype=np.float64).reshape((10_000, 7))
    group = ColumnGroupView(
        source,
        ("t", "x", "y", "z", "vx", "vy", "vz"),
        (RowSpan(0, len(source)),),
    )
    pair = group.pair("t", "z")
    path = Path(pair)
    line_collection = LineCollection([pair])
    figure = Figure()
    axes = figure.add_subplot(111)
    axes.add_patch(PathPatch(path, fill=False))
    axes.add_collection(line_collection)

    FigureCanvasAgg(figure).draw()

    patch_vertices = path.vertices
    collection_vertices = line_collection.get_paths()[0].vertices
    assert np.shares_memory(patch_vertices, source)
    assert np.shares_memory(collection_vertices, source)
    source[0, 0] = -1.0
    assert patch_vertices[0, 0] == -1.0
    assert collection_vertices[0, 0] == -1.0
