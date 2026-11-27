"""Layout and timing constants shared by workspace components."""

from ..data_view_panel import DATA_VIEW_PANEL_MIN_SIZE

TIMELINE_SLIDER_MAX: int = 10_000
"""Maximum integer position of the timeline slider."""

DATA_VIEW_REDRAW_INTERVAL_MS: int = 33
"""Minimum spacing between scheduled visible view-panel redraws (milliseconds)."""

DATA_VIEW_SCROLL_SETTLE_MS: int = 120
"""Wait for a stack scroll gesture to pause before refreshing its graphs."""

MIN_DATA_VIEW_PANE_WIDTH: int = 320
"""Minimum width for either side of the view-stack splitter."""

MIN_DATA_VIEW_PANEL_HEIGHT: int = DATA_VIEW_PANEL_MIN_SIZE[1]
"""Minimum height for data-view panels separated by horizontal stack splitters."""

DEFAULT_DATA_VIEW_PANEL_HEIGHT: int = 280
"""Initial height for data-view panels before the user resizes them."""

MAX_NATURAL_DATA_VIEW_PANEL_HEIGHT: int = 900
"""Maximum height assigned when sizing a new data-view panel to its content."""

SASH_DRAG_MIN_PANE: int = 1
"""wx-level pane floor for stack splitters; panel minimums are enforced by the stack layout."""

DEFAULT_RIGHT_PANE_WIDTH: int = 320
"""Initial width of the optional Additional pane."""

CONTROLS_PANE_NAME: str = "Controls & Info"
"""Visible and programmatic name for the left feature pane."""

MAIN_PANE_NAME: str = "Main pane"
"""Visible and programmatic name for the primary data-view pane."""

ADDITIONAL_PANE_NAME: str = "Additional pane"
"""Visible and programmatic name for the optional secondary data-view pane."""
