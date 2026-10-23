"""Layout and timing constants shared by workspace components."""

from ..graph_panel import GRAPH_PANEL_MIN_SIZE

TIMELINE_SLIDER_MAX: int = 10_000
"""Maximum integer position of the timeline slider."""

GRAPH_REDRAW_INTERVAL_MS: int = 33
"""Minimum spacing between scheduled visible graph-panel redraws (milliseconds)."""

MIN_GRAPH_PANE_WIDTH: int = 320
"""Minimum width for either side of the graph-stack splitter."""

MIN_GRAPH_PANEL_HEIGHT: int = GRAPH_PANEL_MIN_SIZE[1]
"""Minimum height for graph panels separated by horizontal stack splitters."""

MAX_NATURAL_GRAPH_PANEL_HEIGHT: int = 900
"""Maximum height assigned when sizing a new graph panel to its content."""

SASH_DRAG_MIN_PANE: int = 1
"""wx-level pane floor for stack splitters; panel minimums are enforced by the stack layout."""

DEFAULT_RIGHT_PANE_WIDTH: int = 320
"""Initial width of the optional right graph pane."""

CONTROLS_PANE_NAME: str = "Controls & Info"
"""Visible and programmatic name for the left feature pane."""

MAIN_ANALYSIS_PANE_NAME: str = "Main Analysis"
"""Visible and programmatic name for the middle graph pane."""

COMPARISON_PANE_NAME: str = "Comparison"
"""Visible and programmatic name for the optional right graph pane."""
