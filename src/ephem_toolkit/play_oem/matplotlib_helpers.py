"""Shared Matplotlib figure construction and axes styling for Play-OEM."""

from __future__ import annotations

import math
from collections.abc import Sequence

from matplotlib import rcParams
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.backend_bases import RendererBase
from matplotlib.figure import Figure
from matplotlib.layout_engine import ConstrainedLayoutEngine, PlaceHolderLayoutEngine
from matplotlib.legend import Legend

FIGURE_LAYOUT_PADS: dict[str, float] = {
    "w_pad": 0.08,
    "h_pad": 0.08,
    "wspace": 0.04,
    "hspace": 0.08,
}
"""Default constrained-layout spacing for Play-OEM figures."""

CANVAS_INSET_DIP: int = 8
"""Inset around embedded Matplotlib canvases in device-independent pixels."""

AXIS_TITLE_SIZE_PT: float = 11.0
"""Default axes title size."""

AXIS_LABEL_SIZE_PT: float = 10.0
"""Default axes label size."""

TICK_LABEL_SIZE_PT: float = 9.0
"""Default axes tick-label size."""

LEGEND_LABEL_SIZE_PT: float = 9.0
"""Default legend-label size."""

GRID_ALPHA: float = 0.25
"""Default major-grid transparency."""

GRID_LINEWIDTH_PT: float = 0.6
"""Default major-grid line width."""


def create_figure(
    figsize: tuple[float, float],
    *,
    dpi: float | None = None,
    constrained_layout: bool = True,
) -> Figure:
    """Create a Play-OEM figure using Matplotlib's configured DPI by default."""
    figure = Figure(
        figsize=figsize,
        dpi=dpi,
        constrained_layout=constrained_layout,
    )
    _configure_figure_layout(figure)
    return figure


def style_axes(*axes: Axes) -> None:
    """Apply shared typography and major-grid styling without changing plot data."""
    for axis in axes:
        axis.title.set_fontsize(AXIS_TITLE_SIZE_PT)
        axis.xaxis.label.set_fontsize(AXIS_LABEL_SIZE_PT)
        axis.yaxis.label.set_fontsize(AXIS_LABEL_SIZE_PT)
        zaxis = getattr(axis, "zaxis", None)
        if zaxis is not None:
            zaxis.label.set_fontsize(AXIS_LABEL_SIZE_PT)
        axis.tick_params(axis="both", which="major", labelsize=TICK_LABEL_SIZE_PT)
        axis.set_axisbelow(True)
        axis.grid(
            True,
            which="major",
            alpha=GRID_ALPHA,
            linewidth=GRID_LINEWIDTH_PT,
        )
        legend = axis.get_legend()
        if legend is not None:
            style_legend(legend)


def style_legend(legend: Legend) -> None:
    """Apply the shared typography to a Matplotlib legend."""
    for label in legend.get_texts():
        label.set_fontsize(LEGEND_LABEL_SIZE_PT)


def create_figure_legend(
    figure: Figure,
    handles: Sequence[Artist],
    *,
    loc: str = "center",
    ncol: int = 1,
    frameon: bool = False,
    borderpad: float = 0.1,
    labelspacing: float = 0.2,
    handletextpad: float = 0.4,
) -> Legend | None:
    """Create a consistently styled figure-level legend when handles exist."""
    if not handles:
        return None
    legend = figure.legend(
        handles=handles,
        loc=loc,
        ncol=ncol,
        frameon=frameon,
        borderpad=borderpad,
        labelspacing=labelspacing,
        handletextpad=handletextpad,
    )
    style_legend(legend)
    return legend


def legend_canvas_size_px(
    legend: Legend | None,
    renderer: RendererBase,
    *,
    padding_px: int = 2,
) -> tuple[int, int]:
    """Return a legend's fitted canvas dimensions in physical renderer pixels."""
    if padding_px < 0:
        raise ValueError("padding_px must be non-negative")
    if legend is None:
        return 1, 1
    bounds = legend.get_window_extent(renderer)
    return (
        math.ceil(bounds.width + 2 * padding_px),
        math.ceil(bounds.height + 2 * padding_px),
    )


def _configure_figure_layout(figure: Figure) -> None:
    """Apply shared spacing without overriding caller-customized subplot bounds."""
    layout_engine = figure.get_layout_engine()
    if isinstance(layout_engine, ConstrainedLayoutEngine):
        layout_engine.set(**FIGURE_LAYOUT_PADS)
        return
    if layout_engine is not None and not isinstance(
        layout_engine, PlaceHolderLayoutEngine
    ):
        return
    if not figure.axes:
        return

    subplot_params = figure.subplotpars
    default_params = (
        rcParams["figure.subplot.left"],
        rcParams["figure.subplot.right"],
        rcParams["figure.subplot.bottom"],
        rcParams["figure.subplot.top"],
        rcParams["figure.subplot.wspace"],
        rcParams["figure.subplot.hspace"],
    )
    current_params = (
        subplot_params.left,
        subplot_params.right,
        subplot_params.bottom,
        subplot_params.top,
        subplot_params.wspace,
        subplot_params.hspace,
    )
    if current_params == default_params:
        figure.tight_layout(pad=0.2)
