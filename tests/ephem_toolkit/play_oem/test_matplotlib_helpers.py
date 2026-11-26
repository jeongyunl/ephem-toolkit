"""Tests for shared Play-OEM Matplotlib construction and styling."""

from __future__ import annotations

import math

import pytest
from matplotlib import rcParams
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.layout_engine import PlaceHolderLayoutEngine
from matplotlib.lines import Line2D

from ephem_toolkit.play_oem.matplotlib_helpers import (
    AXIS_LABEL_SIZE_PT,
    AXIS_TITLE_SIZE_PT,
    FIGURE_LAYOUT_PADS,
    GRID_ALPHA,
    GRID_LINEWIDTH_PT,
    LEGEND_LABEL_SIZE_PT,
    TICK_LABEL_SIZE_PT,
    _configure_figure_layout,
    create_figure,
    create_figure_legend,
    legend_canvas_size_px,
    style_axes,
)


def test_create_figure_uses_configured_dpi_and_layout_pads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(rcParams, "figure.dpi", 144.0)
    figure = create_figure((8.0, 6.0))

    assert figure.dpi == 144.0
    assert figure.get_size_inches().tolist() == [8.0, 6.0]
    layout_engine = figure.get_layout_engine()
    assert layout_engine is not None
    assert layout_engine.get() == {
        **FIGURE_LAYOUT_PADS,
        "rect": (0, 0, 1, 1),
    }


def test_create_figure_can_disable_constrained_layout() -> None:
    figure = create_figure((5.0, 4.5), constrained_layout=False)

    assert figure.get_layout_engine() is None


def test_create_figure_accepts_explicit_dpi_override() -> None:
    figure = create_figure((5.0, 4.5), dpi=72.0)

    assert figure.dpi == 72.0


def test_nonconstrained_layout_uses_tight_layout_for_default_subplot_bounds() -> None:
    figure = Figure(figsize=(8.0, 4.5), constrained_layout=False)
    figure.add_subplot(111)

    _configure_figure_layout(figure)

    assert isinstance(figure.get_layout_engine(), PlaceHolderLayoutEngine)
    assert figure.subplotpars.left < 0.125


def test_nonconstrained_layout_does_not_override_custom_subplot_bounds() -> None:
    figure = create_figure((8.0, 4.5), constrained_layout=False)
    axes = figure.add_subplot(111)
    figure.subplots_adjust(left=0.3)
    original_bounds = (
        figure.subplotpars.left,
        figure.subplotpars.right,
        figure.subplotpars.bottom,
        figure.subplotpars.top,
    )

    _configure_figure_layout(figure)

    assert (
        figure.subplotpars.left,
        figure.subplotpars.right,
        figure.subplotpars.bottom,
        figure.subplotpars.top,
    ) == original_bounds
    assert axes in figure.axes


def test_style_axes_applies_defaults_without_changing_labels_or_aspect() -> None:
    figure = create_figure((8.0, 4.5))
    axes = figure.subplots()
    axes.set_title("Elevation")
    axes.set_xlabel("Elapsed time")
    axes.set_ylabel("Degrees")
    axes.set_aspect("auto")
    (line,) = axes.plot([0, 1], [1, 0], color="#e74d69", label="Station")
    axes.legend()

    style_axes(axes)
    FigureCanvasAgg(figure).draw()

    assert axes.get_title() == "Elevation"
    assert axes.get_xlabel() == "Elapsed time"
    assert axes.get_ylabel() == "Degrees"
    assert axes.get_aspect() == "auto"
    assert line.get_color() == "#e74d69"
    assert axes.title.get_fontsize() == AXIS_TITLE_SIZE_PT
    assert axes.xaxis.label.get_fontsize() == AXIS_LABEL_SIZE_PT
    assert axes.yaxis.label.get_fontsize() == AXIS_LABEL_SIZE_PT
    assert axes.get_xticklabels()[0].get_fontsize() == TICK_LABEL_SIZE_PT
    assert axes.get_legend() is not None
    assert (
        axes.get_legend().get_texts()[0].get_fontsize()
        == LEGEND_LABEL_SIZE_PT
    )
    assert axes.xaxis.get_gridlines()[0].get_alpha() == GRID_ALPHA
    assert axes.xaxis.get_gridlines()[0].get_linewidth() == GRID_LINEWIDTH_PT
    assert axes.get_axisbelow()


def test_style_axes_applies_axis_label_size_to_3d_z_axis() -> None:
    figure = create_figure((8.0, 6.0))
    axes = figure.add_subplot(111, projection="3d")
    axes.set_zlabel("Z (km)")

    style_axes(axes)

    assert axes.zaxis.label.get_fontsize() == AXIS_LABEL_SIZE_PT


def test_create_figure_legend_applies_standard_typography() -> None:
    figure = Figure(figsize=(4.0, 2.0), dpi=100)
    handle = Line2D([], [], label="Ground track")

    legend = create_figure_legend(figure, [handle])

    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["Ground track"]
    assert legend.get_texts()[0].get_fontsize() == LEGEND_LABEL_SIZE_PT


def test_figure_legend_helpers_cover_empty_entries_and_renderer_padding() -> None:
    figure = Figure(figsize=(4.0, 2.0), dpi=100)
    canvas = FigureCanvasAgg(figure)
    assert create_figure_legend(figure, []) is None

    handle = Line2D([], [], label="Ground track")
    legend = create_figure_legend(figure, [handle])
    assert legend is not None
    canvas.draw()
    bounds = legend.get_window_extent(canvas.get_renderer())

    assert legend_canvas_size_px(None, canvas.get_renderer()) == (1, 1)
    assert legend_canvas_size_px(
        legend,
        canvas.get_renderer(),
        padding_px=2,
    ) == (math.ceil(bounds.width + 4), math.ceil(bounds.height + 4))


def test_constrained_layout_keeps_axes_text_inside_at_multiple_dpi() -> None:
    for dpi in (72, 144):
        figure = create_figure((8.0, 4.5), dpi=dpi)
        axes = figure.subplots()
        axes.set_title("Long plot title")
        axes.set_xlabel("Elapsed time (hours)")
        axes.set_ylabel("Position (kilometers)")
        style_axes(axes)
        canvas = FigureCanvasAgg(figure)
        canvas.draw()

        figure_bounds = figure.bbox
        axes_bounds = axes.get_tightbbox(canvas.get_renderer())
        assert axes_bounds.x0 >= figure_bounds.x0 - 2
        assert axes_bounds.y0 >= figure_bounds.y0 - 2
        assert axes_bounds.x1 <= figure_bounds.x1 + 2
        assert axes_bounds.y1 <= figure_bounds.y1 + 2
