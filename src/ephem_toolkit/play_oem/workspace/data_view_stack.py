"""Data-data-view stack and splitter behavior for the playback workspace."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Protocol, cast

import wx

from ..data_view_panel import DATA_VIEW_PANEL_MIN_SIZE, DataViewPanelHost
from .constants import (
    DATA_VIEW_REDRAW_INTERVAL_MS,
    DATA_VIEW_SCROLL_SETTLE_MS,
    DEFAULT_DATA_VIEW_PANEL_HEIGHT,
    MAX_NATURAL_DATA_VIEW_PANEL_HEIGHT,
    MIN_DATA_VIEW_PANEL_HEIGHT,
    MIN_DATA_VIEW_PANE_WIDTH,
    SASH_DRAG_MIN_PANE,
)
from ..widgets.tooltips import set_tooltip


class _DataViewStackState(Protocol):
    """Workspace-owned data-view panes and stack bookkeeping used by this mixin."""

    _add_buttons: dict[str, wx.Button]
    _bottom_drag_start: dict[str, tuple[int, int]]
    _additional_pane_toggle: wx.ToggleButton | None
    _follow_selection_toggle: wx.CheckBox | None
    _view_preset_choice: wx.Choice | None
    _empty_panels: dict[str, wx.Panel]
    _data_view_panel_heights: dict[DataViewPanelHost, int]
    _data_view_panels: dict[str, list[DataViewPanelHost]]
    _data_view_redraw_timer: wx.CallLater | None
    _visible_data_view_panels: set[DataViewPanelHost]
    _data_view_scroll_timers: dict[str, wx.CallLater | None]
    _on_add_data_view: Callable[[str], None] | None
    _on_open_preset: Callable[[str], None] | None
    _on_follow_selection: Callable[[bool], None] | None
    _pane_close_buttons: dict[str, wx.Button]
    _pending_data_view_redraws: deque[DataViewPanelHost]
    _queued_data_view_redraws: set[DataViewPanelHost]
    _right_pane_visible: bool
    _right_pane_width: int
    _stack_bottom_padding_active: dict[str, bool]
    _stack_handles: dict[str, wx.Panel]
    _stack_overflowing: dict[str, bool]
    _stack_roots: dict[str, wx.Window | None]
    _stack_sizers: dict[str, wx.BoxSizer]
    _stack_windows: dict[str, wx.ScrolledWindow]
    _stacks_fitting: set[str]
    additional_pane: wx.Panel
    data_view_panes_splitter: wx.SplitterWindow
    main_pane: wx.Panel

    def _apply_data_view_sash_heights(self, window: wx.Window | None) -> None: ...

    def _bottom_data_view_panel(self, stack: str) -> DataViewPanelHost | None: ...

    def _detach_stack_bottom_padding(self, stack: str) -> None: ...

    def _draw_next_data_view_panel(self) -> None: ...

    def _layout_data_view_stack(self, stack: str) -> None: ...

    def _make_data_view_stack(self, parent: wx.Window, stack: str) -> wx.ScrolledWindow: ...

    def _on_bottom_handle_down(self, stack: str, event: wx.MouseEvent) -> None: ...

    def _on_bottom_handle_motion(self, stack: str, event: wx.MouseEvent) -> None: ...

    def _on_bottom_handle_up(self, stack: str, event: wx.MouseEvent) -> None: ...

    def _on_data_view_sash_changing(
        self, stack: str, splitter: wx.SplitterWindow, event: wx.SplitterEvent
    ) -> None: ...

    def _on_stack_scroll(self, stack: str, event: wx.ScrollWinEvent) -> None: ...

    def _flush_visible_data_view_redraws(self, stack: str) -> None: ...

    def _on_stack_size(self, stack: str, event: wx.SizeEvent) -> None: ...

    def _remove_panel_from_splitter(
        self, stack: str, splitter: wx.SplitterWindow, panel: DataViewPanelHost
    ) -> bool: ...

    def _remove_panel_from_stack_tree(
        self, stack: str, panel: DataViewPanelHost
    ) -> None: ...

    def _request_add_data_view(self, stack: str) -> None: ...

    def _request_stack_redraws(self, stack: str) -> None: ...

    def request_visible_data_view_redraws(self) -> None: ...

    def _resize_data_view_panel(
        self, stack: str, panel: DataViewPanelHost, height: int
    ) -> None: ...

    def show_right_pane(self, visible: bool) -> None: ...

    def add_data_view_panel(self, panel: DataViewPanelHost, stack: str = "middle") -> None: ...

    def remove_data_view_panel(
        self, panel: DataViewPanelHost, stack: str = "middle"
    ) -> None: ...

    def _stack_subtree_height(self, window: wx.Window) -> int: ...

    def _sync_data_view_panel_heights(self, stack: str) -> None: ...

    def _update_stack_scrollbar_visibility(self, stack: str) -> None: ...

    def _update_stack_virtual_size(self, stack: str) -> None: ...

    def is_data_view_panel_visible(self, panel: DataViewPanelHost) -> bool: ...


class DataViewStackMixin:
    """Implement data-data-view stacks, splitters, scrolling and redraw scheduling."""


    def show_right_pane(self: _DataViewStackState, visible: bool) -> None:
        """Show or hide the optional data-view stack while retaining its contents."""
        if visible == self._right_pane_visible:
            return
        if visible:
            client_width = self.data_view_panes_splitter.GetClientSize().width
            sash_size = self.data_view_panes_splitter.GetSashSize()
            if client_width > 0:
                max_right_width = max(
                    MIN_DATA_VIEW_PANE_WIDTH,
                    client_width - MIN_DATA_VIEW_PANE_WIDTH - sash_size,
                )
                right_width = min(self._right_pane_width, max_right_width)
                sash_position = client_width - right_width - sash_size
            else:
                sash_position = MIN_DATA_VIEW_PANE_WIDTH
            self.data_view_panes_splitter.SplitVertically(
                self.main_pane, self.additional_pane, sash_position
            )
        else:
            client_width = self.data_view_panes_splitter.GetClientSize().width
            if client_width > 0:
                self._right_pane_width = max(
                    MIN_DATA_VIEW_PANE_WIDTH,
                    client_width
                    - self.data_view_panes_splitter.GetSashPosition()
                    - self.data_view_panes_splitter.GetSashSize(),
                )
            self.data_view_panes_splitter.Unsplit(self.additional_pane)
        self._right_pane_visible = visible
        if self._additional_pane_toggle is not None:
            self._additional_pane_toggle.SetValue(visible)
        if self._follow_selection_toggle is not None:
            self._follow_selection_toggle.Enable(visible)
        self.data_view_panes_splitter.Layout()
        if visible:
            self._request_stack_redraws("right")

    def add_data_view_panel(
        self: _DataViewStackState, panel: DataViewPanelHost, stack: str = "middle"
    ) -> None:
        """Add a data-view panel host, separating adjacent panels with horizontal splitters."""
        if stack not in self._data_view_panels:
            raise ValueError(f"unknown data-view stack {stack!r}")
        if panel in self._data_view_panels[stack]:
            raise ValueError("data-view panel is already in this stack")

        # The new splitter is appended to the sizer, so remove the tail first.
        self._detach_stack_bottom_padding(stack)
        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        root = self._stack_roots[stack]
        adding_to_existing_stack = root is not None
        if root is None:
            root = panel
            # A reused panel may be parked outside the scroller after removal.
            root.Reparent(window)
            sizer.Add(root, 1, wx.EXPAND)
        else:
            for existing_panel in self._data_view_panels[stack]:
                self._data_view_panel_heights.setdefault(
                    existing_panel,
                    max(MIN_DATA_VIEW_PANEL_HEIGHT, existing_panel.GetSize().height),
                )
            root_min_height = root.GetMinSize().height
            new_splitter = wx.SplitterWindow(
                window, wx.ID_ANY, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH
            )
            new_splitter.SetMinimumPaneSize(SASH_DRAG_MIN_PANE)
            new_splitter.SetSashGravity(0.5)
            sizer.Detach(root)
            root.Reparent(new_splitter)
            panel.Reparent(new_splitter)
            if not new_splitter.SplitHorizontally(root, panel, root_min_height):
                root.Reparent(window)
                panel.Reparent(window)
                new_splitter.Destroy()
                sizer.Add(root, 1, wx.EXPAND)
                raise RuntimeError(f"could not split data-view stack {stack!r}")
            new_splitter.Bind(
                wx.EVT_SPLITTER_SASH_POS_CHANGING,
                lambda event, stack=stack, new_splitter=new_splitter: (
                    self._on_data_view_sash_changing(stack, new_splitter, event)
                ),
            )
            root = new_splitter
            sizer.Add(root, 1, wx.EXPAND)

        self._data_view_panels[stack].append(panel)
        if adding_to_existing_stack:
            self._data_view_panel_heights.setdefault(panel, DEFAULT_DATA_VIEW_PANEL_HEIGHT)
        self._stack_roots[stack] = root
        self._layout_data_view_stack(stack)
        self._apply_data_view_sash_heights(root)

    def remove_data_view_panel(
        self: _DataViewStackState, panel: DataViewPanelHost, stack: str = "middle"
    ) -> None:
        """Remove a data-view panel host and collapse its splitter without disturbing others."""
        if stack not in self._data_view_panels:
            raise ValueError(f"unknown data-view stack {stack!r}")
        if panel not in self._data_view_panels[stack]:
            return
        # Removing a panel can replace the root item that follows the tail.
        self._detach_stack_bottom_padding(stack)
        self._remove_panel_from_stack_tree(stack, panel)
        self._data_view_panels[stack].remove(panel)
        self._visible_data_view_panels.discard(panel)
        self._data_view_panel_heights.pop(panel, None)
        if panel in self._queued_data_view_redraws:
            self._pending_data_view_redraws = deque(
                queued for queued in self._pending_data_view_redraws if queued is not panel
            )
            self._queued_data_view_redraws.remove(panel)
        if not self._pending_data_view_redraws and self._data_view_redraw_timer is not None:
            if self._data_view_redraw_timer.IsRunning():
                self._data_view_redraw_timer.Stop()
            self._data_view_redraw_timer = None
        self._layout_data_view_stack(stack)
        self._apply_data_view_sash_heights(self._stack_roots[stack])

    def replace_data_view_panel(
        self: _DataViewStackState,
        old_panel: DataViewPanelHost,
        new_panel: DataViewPanelHost,
        stack: str = "middle",
    ) -> None:
        """Replace a data-view panel host, preserving panel height, order and scroll position."""
        if stack not in self._data_view_panels:
            raise ValueError(f"unknown data-view stack {stack!r}")
        panels = self._data_view_panels[stack]
        if old_panel not in panels:
            raise ValueError("data-view panel is not in this stack")
        if new_panel in panels:
            raise ValueError("replacement data-view panel is already in this stack")

        # ReplaceWindow and root replacement change which item owns the stack slot.
        self._detach_stack_bottom_padding(stack)
        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        root = self._stack_roots[stack]
        view_start = window.GetViewStart()
        if root is old_panel:
            sizer.Detach(old_panel)
            # The replaced panel may await deferred destruction while the
            # new layout scrolls; keep it outside GTK's scrolling children.
            old_panel.Reparent(window.GetParent())
            new_panel.Reparent(window)
            sizer.Add(new_panel, 1, wx.EXPAND)
            self._stack_roots[stack] = new_panel
        else:
            parent = old_panel.GetParent()
            if not isinstance(parent, wx.SplitterWindow):
                raise RuntimeError(
                    f"data-view panel {old_panel.panel_id!r} has an invalid parent"
                )
            new_panel.Reparent(parent)
            if not parent.ReplaceWindow(old_panel, new_panel):
                new_panel.Reparent(window)
                raise RuntimeError(
                    f"could not replace data-view panel {old_panel.panel_id!r}"
                )
            # ReplaceWindow leaves the old native window alive until Destroy();
            # park it so scrolling/layout cannot allocate the retired panel.
            old_panel.Reparent(window.GetParent())

        panels[panels.index(old_panel)] = new_panel
        self._visible_data_view_panels.discard(old_panel)
        self._data_view_panel_heights[new_panel] = self._data_view_panel_heights.pop(
            old_panel, old_panel.GetSize().height
        )
        self._layout_data_view_stack(stack)
        self._apply_data_view_sash_heights(self._stack_roots[stack])
        window.Scroll(*view_start)

    def size_data_view_panel_to_content(
        self: _DataViewStackState, panel: DataViewPanelHost, natural_height: int
    ) -> None:
        """Size a newly populated panel to its content, within usable height limits."""
        stack = next(
            (name for name, panels in self._data_view_panels.items() if panel in panels),
            None,
        )
        if stack is None:
            raise ValueError("data-view panel is not in a stack")
        # Keep small native data views usable and cap large figures; the outer stack
        # provides scrolling when the resulting panels do not fit the viewport.
        self._data_view_panel_heights[panel] = min(
            max(natural_height, MIN_DATA_VIEW_PANEL_HEIGHT),
            MAX_NATURAL_DATA_VIEW_PANEL_HEIGHT,
        )
        self._layout_data_view_stack(stack)
        self._apply_data_view_sash_heights(self._stack_roots[stack])

    def refresh_data_view_stack_layouts(self: _DataViewStackState) -> None:
        """Recalculate stack scroll ranges after the frame reaches its shown size."""
        # Initial panel insertion can happen before GTK assigns final viewport sizes.
        for stack in self._data_view_panels:
            self._layout_data_view_stack(stack)

    def move_data_view_panel(
        self: _DataViewStackState, panel: DataViewPanelHost, stack: str, offset: int
    ) -> None:
        """Move a live panel within its stack without recreating its view."""
        if stack not in self._data_view_panels:
            raise ValueError(f"unknown data-view stack {stack!r}")
        panels = self._data_view_panels[stack]
        current_index = panels.index(panel)
        target_index = min(max(current_index + offset, 0), len(panels) - 1)
        if target_index == current_index:
            return

        reordered = list(panels)
        reordered.insert(target_index, reordered.pop(current_index))
        stack_window = self._stack_windows[stack]
        for existing_panel in tuple(panels):
            self.remove_data_view_panel(existing_panel, stack)
            existing_panel.Reparent(stack_window)
        for existing_panel in reordered:
            self.add_data_view_panel(existing_panel, stack)

    def request_visible_data_view_redraws(self: _DataViewStackState) -> None:
        """Refresh graphs only when they enter a stack's visible viewport."""
        visible_panels = {
            panel
            for panels in self._data_view_panels.values()
            for panel in panels
            if self.is_data_view_panel_visible(panel)
        }
        newly_visible = visible_panels - self._visible_data_view_panels
        self._visible_data_view_panels = visible_panels
        for panel in newly_visible:
            panel.notify_viewport_visible()

    def queue_data_view_redraw(self: _DataViewStackState, panel: DataViewPanelHost) -> None:
        """Queue one visible panel for the shared redraw budget."""
        if not self.is_data_view_panel_visible(panel):
            return
        if panel in self._queued_data_view_redraws:
            return
        self._pending_data_view_redraws.append(panel)
        self._queued_data_view_redraws.add(panel)
        if self._data_view_redraw_timer is None:
            self._data_view_redraw_timer = wx.CallLater(1, self._draw_next_data_view_panel)

    def draw_initial_data_views(self: _DataViewStackState) -> None:
        """Draw currently visible data views before the playback timer starts."""
        if self._data_view_redraw_timer is not None:
            if self._data_view_redraw_timer.IsRunning():
                self._data_view_redraw_timer.Stop()
            self._data_view_redraw_timer = None
        pending = tuple(self._pending_data_view_redraws)
        self._pending_data_view_redraws.clear()
        self._queued_data_view_redraws.clear()
        for panel in pending:
            if self.is_data_view_panel_visible(panel):
                panel.draw_initial()

    def is_data_view_panel_visible(self: _DataViewStackState, panel: DataViewPanelHost) -> bool:
        """Check whether a data-view panel host intersects its scroll stack's viewport."""
        # A queued redraw can outlive the native wx window (for example while
        # deferred destruction is being processed). Check the native window
        # before making further calls on a wrapper that may outlive it.
        try:
            if panel.IsBeingDeleted():
                return False
        except RuntimeError:
            # wxPython keeps the Python wrapper reachable after wxWidgets has
            # deleted its native window; calls through that wrapper then fail.
            return False
        if not any(panel in panels for panels in self._data_view_panels.values()):
            return False
        stack = next(
            stack for stack, panels in self._data_view_panels.items() if panel in panels
        )
        scroll_timer = self._data_view_scroll_timers[stack]
        if scroll_timer is not None and scroll_timer.IsRunning():
            return False
        if not panel.IsShownOnScreen():
            return False
        stack_window = next(
            (
                self._stack_windows[stack]
                for stack, panels in self._data_view_panels.items()
                if panel in panels
            ),
            None,
        )
        if stack_window is None:
            return False
        visible_rect = wx.Rect(
            stack_window.ClientToScreen((0, 0)), stack_window.GetClientSize()
        )
        return panel.GetScreenRect().Intersects(visible_rect)

    def _remove_panel_from_stack_tree(
        self: _DataViewStackState, stack: str, panel: DataViewPanelHost
    ) -> None:
        root = self._stack_roots[stack]
        if root is panel:
            self._stack_sizers[stack].Detach(panel)
            # Removing it from the sizer alone still leaves a native scroll
            # child until the caller destroys or reuses the panel.
            panel.Reparent(self._stack_windows[stack].GetParent())
            self._stack_roots[stack] = None
            return
        if not isinstance(root, wx.SplitterWindow):
            raise RuntimeError(f"data-view stack {stack!r} has an invalid splitter tree")
        if not self._remove_panel_from_splitter(stack, root, panel):
            raise RuntimeError(
                f"data-view panel {panel.panel_id!r} is missing from its stack"
            )

    def _remove_panel_from_splitter(
        self: _DataViewStackState,
        stack: str,
        splitter: wx.SplitterWindow,
        panel: DataViewPanelHost,
    ) -> bool:
        first_pane = splitter.GetWindow1()
        second_pane = splitter.GetWindow2()
        if first_pane is panel or second_pane is panel:
            sibling = second_pane if first_pane is panel else first_pane
            stack_window = self._stack_windows[stack]
            splitter.Unsplit(panel)
            # Unsplit hides the removed pane. Park it outside the scroller
            # so GTK cannot allocate it during the following layout update.
            panel.Reparent(stack_window.GetParent())
            if splitter is self._stack_roots[stack]:
                self._stack_sizers[stack].Detach(splitter)
                sibling.Reparent(stack_window)
                # Destroy() is deferred: keep the retiring splitter out of
                # native scrolling while GTK finishes deleting it.
                splitter.Reparent(stack_window.GetParent())
                splitter.Destroy()
                self._stack_sizers[stack].Add(sibling, 1, wx.EXPAND)
                self._stack_roots[stack] = sibling
            else:
                parent = splitter.GetParent()
                if not isinstance(parent, wx.SplitterWindow):
                    raise RuntimeError(
                        f"data-view stack {stack!r} has a broken splitter hierarchy"
                    )
                parent_first = parent.GetWindow1()
                parent_second = parent.GetWindow2()
                parent_sash_position = parent.GetSashPosition()
                parent.Unsplit(splitter)
                sibling.Reparent(parent)
                # Destroy() is deferred here too; park the now-hidden nested
                # splitter outside the visible tree before the parent relayout.
                splitter.Reparent(stack_window.GetParent())
                splitter.Destroy()
                if parent_first is splitter:
                    split_succeeded = parent.SplitHorizontally(
                        sibling, parent_second, parent_sash_position
                    )
                else:
                    split_succeeded = parent.SplitHorizontally(
                        parent_first, sibling, parent_sash_position
                    )
                if not split_succeeded:
                    raise RuntimeError(f"could not restore data-view stack {stack!r}")
            return True

        if isinstance(first_pane, wx.SplitterWindow) and (
            self._remove_panel_from_splitter(stack, first_pane, panel)
        ):
            return True
        if isinstance(second_pane, wx.SplitterWindow) and (
            self._remove_panel_from_splitter(stack, second_pane, panel)
        ):
            return True
        return False

    def _stack_subtree_height(self: _DataViewStackState, window: wx.Window) -> int:
        """Return the height a stack subtree needs: panel heights plus internal sashes."""
        if not isinstance(window, wx.SplitterWindow):
            # Stack leaves are data-view panel hosts; wx exposes splitter children as Windows.
            return self._data_view_panel_heights.get(
                cast(DataViewPanelHost, window), MIN_DATA_VIEW_PANEL_HEIGHT
            )
        return (
            self._stack_subtree_height(window.GetWindow1())
            + window.GetSashSize()
            + self._stack_subtree_height(window.GetWindow2())
        )

    def _layout_data_view_stack(self: _DataViewStackState, stack: str) -> None:
        """Synchronize the empty state, minimum sizes, and scroll layout."""

        def minimum_height(window: wx.Window) -> int:
            if not isinstance(window, wx.SplitterWindow):
                return self._stack_subtree_height(window)
            # wx clamps a sash to the minimum size of the panes on both sides, so
            # panels inside a splitter advertise only a small floor. The real
            # panel floor is enforced through _data_view_panel_heights.
            first_pane, second_pane = window.GetWindow1(), window.GetWindow2()
            for child in (first_pane, second_pane):
                if not isinstance(child, wx.SplitterWindow):
                    child.SetMinSize(
                        wx.Size(DATA_VIEW_PANEL_MIN_SIZE[0], SASH_DRAG_MIN_PANE)
                    )
            height = (
                minimum_height(first_pane)
                + window.GetSashSize()
                + minimum_height(second_pane)
            )
            window.SetMinimumPaneSize(SASH_DRAG_MIN_PANE)
            window.SetMinSize((DATA_VIEW_PANEL_MIN_SIZE[0], height))
            return height

        root = self._stack_roots[stack]
        if root is not None:
            if not isinstance(root, wx.SplitterWindow):
                root.SetMinSize(
                    wx.Size(DATA_VIEW_PANEL_MIN_SIZE[0], self._stack_subtree_height(root))
                )
            minimum_height(root)

        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        empty_panel = self._empty_panels[stack]
        handle = self._stack_handles[stack]
        if self._stack_bottom_padding_active[stack]:
            # Tree edits can append a new splitter after the spacer. Remove it
            # first so the edit cannot mistake the spacer for the stack root.
            sizer.Detach(sizer.GetItemCount() - 1)
            self._stack_bottom_padding_active[stack] = False
        if root is not None and empty_panel.GetParent() is window:
            # wxGTK allocates even hidden direct children when scrolling.
            # Detach and park the empty state until it is needed again.
            empty_panel.Hide()
            sizer.Detach(empty_panel)
            empty_panel.Reparent(window.GetParent())
        elif root is None and empty_panel.GetParent() is not window:
            # Only return the empty state to the scroller when it is visible.
            empty_panel.Reparent(window)
            sizer.Add(empty_panel, 0, wx.EXPAND)
            empty_panel.Show()

        if root is None:
            sizer.Detach(handle)
            handle.Hide()
            # wxGTK may allocate hidden direct children while the scroller is
            # being laid out during shutdown. Keep the unused handle outside it.
            if handle.GetParent() is window:
                handle.Reparent(window.GetParent())
        else:
            # Keep panels at their requested heights rather than stretching them to
            # the viewport, and keep the resize handle directly below the stack.
            bottom_panel = self._bottom_data_view_panel(stack)
            bottom_parent = (
                bottom_panel.GetParent() if bottom_panel is not None else None
            )
            handle_height = (
                bottom_parent.GetSashSize()
                if isinstance(bottom_parent, wx.SplitterWindow)
                else self.data_view_panes_splitter.GetDefaultSashSize()
            )
            handle.SetMinSize(wx.Size(-1, handle_height))
            sizer.GetItem(root).SetProportion(0)
            sizer.Detach(handle)
            if handle.GetParent() is not window:
                handle.Reparent(window)
            sizer.Add(handle, 0, wx.EXPAND)
            handle.Show()
            # Keep one empty viewport after the stack. This lets the user scroll
            # the last graph fully upward instead of stopping at its bottom edge.
            sizer.Add((0, window.GetClientSize().height), 0)
            self._stack_bottom_padding_active[stack] = True

        window.Layout()
        self._update_stack_virtual_size(stack)
        self._update_stack_scrollbar_visibility(stack)

    def _detach_stack_bottom_padding(self: _DataViewStackState, stack: str) -> None:
        """Remove the trailing sizer spacer before changing stack items."""
        if not self._stack_bottom_padding_active[stack]:
            return
        # Structural edits can reorder sizer items, so remove the known final item
        # while its position is still reliable and let layout add it back afterward.
        sizer = self._stack_sizers[stack]
        sizer.Detach(sizer.GetItemCount() - 1)
        self._stack_bottom_padding_active[stack] = False

    def _update_stack_virtual_size(self: _DataViewStackState, stack: str) -> None:
        """Fit the stack, including trailing space for scrolling the last panel upward."""
        if stack in self._stacks_fitting:
            return
        self._stacks_fitting.add(stack)
        try:
            window = self._stack_windows[stack]
            # FitInside can clamp the current scroll position while ranges change.
            view_start = window.GetViewStart()
            if (
                self._stack_roots[stack] is not None
                and self._stack_bottom_padding_active[stack]
            ):
                # Update the spacer after viewport resizes; FitInside then keeps
                # this extra area in its computed range rather than replacing it.
                padding = window.GetSizer().GetItem(
                    window.GetSizer().GetItemCount() - 1
                )
                padding.SetMinSize(wx.Size(0, window.GetClientSize().height))
                window.Layout()
            window.FitInside()
            window.Scroll(*view_start)
        finally:
            self._stacks_fitting.discard(stack)

    def _update_stack_scrollbar_visibility(self: _DataViewStackState, stack: str) -> None:
        window = self._stack_windows[stack]
        has_overflow = window.GetScrollRange(wx.VERTICAL) > window.GetScrollThumb(
            wx.VERTICAL
        )
        # Only touch the scrollbars on change; each call can send another size event.
        if self._stack_overflowing.get(stack) == has_overflow:
            return
        self._stack_overflowing[stack] = has_overflow
        window.AlwaysShowScrollbars(False, has_overflow)

    def _on_stack_size(self: _DataViewStackState, stack: str, event: wx.SizeEvent) -> None:
        self._update_stack_virtual_size(stack)
        self._update_stack_scrollbar_visibility(stack)
        event.Skip()

    def _sync_data_view_panel_heights(self: _DataViewStackState, stack: str) -> None:
        for panel in self._data_view_panels[stack]:
            self._data_view_panel_heights[panel] = panel.GetSize().height

    def _bottom_data_view_panel(
        self: _DataViewStackState, stack: str
    ) -> DataViewPanelHost | None:
        pane = self._stack_roots[stack]
        while isinstance(pane, wx.SplitterWindow):
            pane = pane.GetWindow2()
        if pane is None:
            return None
        return cast(DataViewPanelHost, pane)

    def _on_bottom_handle_down(
        self: _DataViewStackState, stack: str, event: wx.MouseEvent
    ) -> None:
        panel = self._bottom_data_view_panel(stack)
        if panel is None:
            return
        self._sync_data_view_panel_heights(stack)
        self._bottom_drag_start[stack] = (
            wx.GetMousePosition().y,
            self._data_view_panel_heights[panel],
        )
        self._stack_handles[stack].CaptureMouse()

    def _on_bottom_handle_motion(
        self: _DataViewStackState, stack: str, event: wx.MouseEvent
    ) -> None:
        start = self._bottom_drag_start.get(stack)
        panel = self._bottom_data_view_panel(stack)
        if start is None or panel is None or not event.Dragging():
            return
        start_y, start_height = start
        # Use screen coordinates: the handle itself moves as the panel grows.
        self._resize_data_view_panel(
            stack, panel, start_height + wx.GetMousePosition().y - start_y
        )

    def _on_bottom_handle_up(
        self: _DataViewStackState, stack: str, event: wx.MouseEvent
    ) -> None:
        self._bottom_drag_start.pop(stack, None)
        handle = self._stack_handles[stack]
        if handle.HasCapture():
            handle.ReleaseMouse()

    def _on_data_view_sash_changing(
        self: _DataViewStackState,
        stack: str,
        splitter: wx.SplitterWindow,
        event: wx.SplitterEvent,
    ) -> None:
        """Resize the panel above the sash; panels below keep their heights and the stack grows."""
        event.Veto()
        # With SP_LIVE_UPDATE, wx may already report the proposed sash position
        # from GetSashPosition() while this changing event is being dispatched.
        # Compare against the stored layout instead of that transient position.
        first_pane_height = self._stack_subtree_height(splitter.GetWindow1())
        delta = event.GetSashPosition() - first_pane_height
        if delta == 0:
            return
        pane = splitter.GetWindow1()
        while isinstance(pane, wx.SplitterWindow):
            pane = pane.GetWindow2()
        panel = cast(DataViewPanelHost, pane)
        self._resize_data_view_panel(stack, panel, self._data_view_panel_heights[panel] + delta)

    def _resize_data_view_panel(
        self: _DataViewStackState, stack: str, panel: DataViewPanelHost, height: int
    ) -> None:
        self._data_view_panel_heights[panel] = max(MIN_DATA_VIEW_PANEL_HEIGHT, height)
        self._layout_data_view_stack(stack)
        self._apply_data_view_sash_heights(self._stack_roots[stack])

    def _apply_data_view_sash_heights(
        self: _DataViewStackState, window: wx.Window | None
    ) -> None:
        """Set every sash so each panel keeps its requested height, top-down."""
        if not isinstance(window, wx.SplitterWindow):
            return
        window.SetSashPosition(self._stack_subtree_height(window.GetWindow1()))
        self._apply_data_view_sash_heights(window.GetWindow1())
        self._apply_data_view_sash_heights(window.GetWindow2())

    def _make_data_view_pane(
        self: _DataViewStackState, parent: wx.Window, stack: str, title: str
    ) -> tuple[wx.Panel, wx.ScrolledWindow]:
        data_view_pane = wx.Panel(parent, wx.ID_ANY)
        data_view_pane.SetName(title)
        pane_sizer = wx.BoxSizer(wx.VERTICAL)
        pane_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pane_title_label = wx.StaticText(data_view_pane, wx.ID_ANY, title)
        pane_title_label.SetName(title)
        pane_header_sizer.Add(pane_title_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 8)
        add_view_button = wx.Button(data_view_pane, wx.ID_ANY, "Add data view")
        add_view_button.SetName(f"Add data view to {stack} data-view stack")
        set_tooltip(add_view_button, f"Add a data view to {title}")
        self._add_buttons[stack] = add_view_button
        add_view_button.Bind(
            wx.EVT_BUTTON,
            lambda _event, stack=stack: self._request_add_data_view(stack),
        )
        pane_header_sizer.Add(add_view_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        if stack == "middle":
            preset_choices = (
                "Data-view preset",
                "Access Overview",
                "Pass Study",
            )
            preset_choice = wx.Choice(
                data_view_pane, wx.ID_ANY, choices=list(preset_choices)
            )
            preset_choice.SetName("Open view preset")
            preset_choice.SetSelection(0)
            self._view_preset_choice = preset_choice
            preset_choice.Bind(
                wx.EVT_CHOICE,
                lambda event: self._on_view_preset_selected(event.GetSelection()),
            )
            pane_header_sizer.Add(
                preset_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4
            )
            additional_toggle = wx.ToggleButton(data_view_pane, wx.ID_ANY, "Additional pane")
            self._additional_pane_toggle = additional_toggle
            additional_toggle.SetName("Toggle Additional pane")
            set_tooltip(additional_toggle, "Show or hide the Additional pane")
            additional_toggle.SetValue(False)
            additional_toggle.Bind(
                wx.EVT_TOGGLEBUTTON,
                lambda _event: self.show_right_pane(additional_toggle.GetValue()),
            )
            pane_header_sizer.Add(
                additional_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4
            )
            follow_selection_toggle = wx.CheckBox(
                data_view_pane, wx.ID_ANY, "Follow selection"
            )
            follow_selection_toggle.SetName(
                "Follow Main pane station and pass selection"
            )
            follow_selection_toggle.Enable(False)
            follow_selection_toggle.Bind(
                wx.EVT_CHECKBOX,
                lambda event: (
                    self._on_follow_selection(event.IsChecked())
                    if self._on_follow_selection is not None
                    else None
                ),
            )
            self._follow_selection_toggle = follow_selection_toggle
            pane_header_sizer.Add(
                follow_selection_toggle,
                0,
                wx.ALIGN_CENTER_VERTICAL | wx.ALL,
                4,
            )
        else:
            close_pane_button = wx.Button(data_view_pane, wx.ID_ANY, "Close pane")
            close_pane_button.SetName("Close Additional pane")
            set_tooltip(close_pane_button, "Hide the Additional pane")
            close_pane_button.Bind(
                wx.EVT_BUTTON, lambda _event: self.show_right_pane(False)
            )
            self._pane_close_buttons[stack] = close_pane_button
            pane_header_sizer.Add(
                close_pane_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4
            )
        pane_sizer.Add(pane_header_sizer, 0, wx.EXPAND)
        data_view_stack_window = self._make_data_view_stack(data_view_pane, stack)
        data_view_stack_window.SetName(f"{title} data-view stack")
        pane_sizer.Add(
            data_view_stack_window, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4
        )
        data_view_pane.SetSizer(pane_sizer)
        return data_view_pane, data_view_stack_window

    def _on_view_preset_selected(self: _DataViewStackState, selection: int) -> None:
        if selection == 0:
            return
        preset_names = ("access-overview", "pass-study")
        if selection < 1 or selection > len(preset_names):
            raise ValueError(f"unknown view preset selection: {selection}")
        try:
            if self._on_open_preset is None:
                raise RuntimeError("view preset handler is not configured")
            self._on_open_preset(preset_names[selection - 1])
        finally:
            if self._view_preset_choice is not None:
                self._view_preset_choice.SetSelection(0)

    def _make_data_view_stack(
        self: _DataViewStackState, parent: wx.Window, stack: str
    ) -> wx.ScrolledWindow:
        stack_scroller = wx.ScrolledWindow(parent, wx.ID_ANY, style=wx.VSCROLL)
        stack_scroller.AlwaysShowScrollbars(False, False)
        stack_scroller.SetScrollRate(0, 20)
        stack_sizer = wx.BoxSizer(wx.VERTICAL)
        empty_state_panel = wx.Panel(stack_scroller, wx.ID_ANY)
        empty_state_sizer = wx.BoxSizer(wx.VERTICAL)
        empty_state_label = wx.StaticText(
            empty_state_panel, wx.ID_ANY, "No data-view panels"
        )
        empty_state_label.SetName(f"{stack} stack empty state")
        empty_state_sizer.Add(empty_state_label, 0, wx.ALL, 12)
        add_view_button = wx.Button(empty_state_panel, wx.ID_ANY, "Add data view")
        add_view_button.SetName(f"Add data view to empty {stack} data-view stack")
        add_view_button.Bind(
            wx.EVT_BUTTON,
            lambda _event, stack=stack: self._request_add_data_view(stack),
        )
        empty_state_sizer.Add(add_view_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        empty_state_panel.SetSizer(empty_state_sizer)
        stack_sizer.Add(empty_state_panel, 0, wx.EXPAND)
        bottom_resize_handle = wx.Panel(stack_scroller, wx.ID_ANY)
        bottom_resize_handle.SetMinSize(
            wx.Size(-1, self.data_view_panes_splitter.GetDefaultSashSize())
        )
        bottom_resize_handle.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
        )
        bottom_resize_handle.SetCursor(wx.Cursor(wx.CURSOR_SIZENS))
        bottom_resize_handle.SetName(f"{stack} bottom panel resize handle")
        bottom_resize_handle.Bind(
            wx.EVT_LEFT_DOWN,
            lambda event, stack=stack: self._on_bottom_handle_down(stack, event),
        )
        bottom_resize_handle.Bind(
            wx.EVT_MOTION,
            lambda event, stack=stack: self._on_bottom_handle_motion(stack, event),
        )
        bottom_resize_handle.Bind(
            wx.EVT_LEFT_UP,
            lambda event, stack=stack: self._on_bottom_handle_up(stack, event),
        )
        bottom_resize_handle.Hide()
        stack_scroller.SetSizer(stack_sizer)
        stack_scroller.Bind(
            wx.EVT_SCROLLWIN,
            lambda event, stack=stack: self._on_stack_scroll(stack, event),
        )
        stack_scroller.Bind(
            wx.EVT_SIZE,
            lambda event, stack=stack: self._on_stack_size(stack, event),
        )
        self._stack_windows[stack] = stack_scroller
        self._stack_sizers[stack] = stack_sizer
        self._stack_handles[stack] = bottom_resize_handle
        self._empty_panels[stack] = empty_state_panel
        return stack_scroller

    def _request_add_data_view(self: _DataViewStackState, stack: str) -> None:
        if self._on_add_data_view is None:
            raise RuntimeError("data-data-view panel creation handler is not configured")
        self._on_add_data_view(stack)

    def _request_stack_redraws(self: _DataViewStackState, stack: str) -> None:
        for panel in self._data_view_panels[stack]:
            panel.request_redraw()

    def _draw_next_data_view_panel(self: _DataViewStackState) -> None:
        self._data_view_redraw_timer = None
        while self._pending_data_view_redraws:
            panel = self._pending_data_view_redraws.popleft()
            self._queued_data_view_redraws.remove(panel)
            if self.is_data_view_panel_visible(panel):
                panel.draw_if_needed()
                break
        if self._pending_data_view_redraws:
            self._data_view_redraw_timer = wx.CallLater(
                DATA_VIEW_REDRAW_INTERVAL_MS, self._draw_next_data_view_panel
            )

    def _on_stack_scroll(
        self: _DataViewStackState, stack: str, event: wx.ScrollWinEvent
    ) -> None:
        event.Skip()
        timer = self._data_view_scroll_timers[stack]
        if timer is not None and timer.IsRunning():
            timer.Stop()
        self._visible_data_view_panels.clear()
        self._data_view_scroll_timers[stack] = wx.CallLater(
            DATA_VIEW_SCROLL_SETTLE_MS,
            lambda stack=stack: self._flush_visible_data_view_redraws(stack),
        )

    def _flush_visible_data_view_redraws(self: _DataViewStackState, stack: str) -> None:
        self._data_view_scroll_timers[stack] = None
        self.request_visible_data_view_redraws()
