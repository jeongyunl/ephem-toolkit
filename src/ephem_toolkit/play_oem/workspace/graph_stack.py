"""Graph stack and splitter behavior for the playback workspace."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Protocol, cast

import wx

from ..graph_panel import GRAPH_PANEL_MIN_SIZE, GraphPanelHost
from .constants import (
    BOTTOM_HANDLE_HEIGHT,
    GRAPH_REDRAW_INTERVAL_MS,
    MAX_NATURAL_GRAPH_PANEL_HEIGHT,
    MIN_GRAPH_PANEL_HEIGHT,
    MIN_GRAPH_PANE_WIDTH,
    SASH_DRAG_MIN_PANE,
)
from ..tooltips import set_tooltip


class _GraphStackState(Protocol):
    """Workspace-owned graph panes and stack bookkeeping used by this mixin."""

    _add_buttons: dict[str, wx.Button]
    _bottom_drag_start: dict[str, tuple[int, int]]
    _comparison_toggle: wx.ToggleButton | None
    _empty_panels: dict[str, wx.Panel]
    _graph_panel_heights: dict[GraphPanelHost, int]
    _graph_panels: dict[str, list[GraphPanelHost]]
    _graph_redraw_timer: wx.CallLater | None
    _on_add_graph: Callable[[str], None] | None
    _pane_close_buttons: dict[str, wx.Button]
    _pending_graph_redraws: deque[GraphPanelHost]
    _queued_graph_redraws: set[GraphPanelHost]
    _right_pane_visible: bool
    _right_pane_width: int
    _stack_bottom_padding_active: dict[str, bool]
    _stack_handles: dict[str, wx.Panel]
    _stack_overflowing: dict[str, bool]
    _stack_roots: dict[str, wx.Window | None]
    _stack_sizers: dict[str, wx.BoxSizer]
    _stack_windows: dict[str, wx.ScrolledWindow]
    _stacks_fitting: set[str]
    comparison_pane: wx.Panel
    graph_panes_splitter: wx.SplitterWindow
    main_analysis_pane: wx.Panel

    def _apply_graph_sash_heights(self, window: wx.Window | None) -> None: ...

    def _bottom_graph_panel(self, stack: str) -> GraphPanelHost | None: ...

    def _detach_stack_bottom_padding(self, stack: str) -> None: ...

    def _draw_next_graph_panel(self) -> None: ...

    def _layout_graph_stack(self, stack: str) -> None: ...

    def _make_graph_stack(self, parent: wx.Window, stack: str) -> wx.ScrolledWindow: ...

    def _on_bottom_handle_down(self, stack: str, event: wx.MouseEvent) -> None: ...

    def _on_bottom_handle_motion(self, stack: str, event: wx.MouseEvent) -> None: ...

    def _on_bottom_handle_up(self, stack: str, event: wx.MouseEvent) -> None: ...

    def _on_graph_sash_changing(
        self, stack: str, splitter: wx.SplitterWindow, event: wx.SplitterEvent
    ) -> None: ...

    def _on_stack_scroll(self, event: wx.ScrollWinEvent) -> None: ...

    def _on_stack_size(self, stack: str, event: wx.SizeEvent) -> None: ...

    def _remove_panel_from_splitter(
        self, stack: str, splitter: wx.SplitterWindow, panel: GraphPanelHost
    ) -> bool: ...

    def _remove_panel_from_stack_tree(
        self, stack: str, panel: GraphPanelHost
    ) -> None: ...

    def _request_add_graph(self, stack: str) -> None: ...

    def _request_stack_redraws(self, stack: str) -> None: ...

    def request_visible_graph_redraws(self) -> None: ...

    def _resize_graph_panel(
        self, stack: str, panel: GraphPanelHost, height: int
    ) -> None: ...

    def show_right_pane(self, visible: bool) -> None: ...

    def add_graph_panel(self, panel: GraphPanelHost, stack: str = "middle") -> None: ...

    def remove_graph_panel(
        self, panel: GraphPanelHost, stack: str = "middle"
    ) -> None: ...

    def _stack_subtree_height(self, window: wx.Window) -> int: ...

    def _sync_graph_panel_heights(self, stack: str) -> None: ...

    def _update_stack_scrollbar_visibility(self, stack: str) -> None: ...

    def _update_stack_virtual_size(self, stack: str) -> None: ...

    def is_graph_panel_visible(self, panel: GraphPanelHost) -> bool: ...


class GraphStackMixin:
    """Implement graph panel stacks, splitters, scrolling and redraw scheduling."""

    def show_right_pane(self: _GraphStackState, visible: bool) -> None:
        """Show or hide the optional graph stack while retaining its contents."""
        if visible == self._right_pane_visible:
            return
        if visible:
            client_width = self.graph_panes_splitter.GetClientSize().width
            sash_size = self.graph_panes_splitter.GetSashSize()
            if client_width > 0:
                max_right_width = max(
                    MIN_GRAPH_PANE_WIDTH,
                    client_width - MIN_GRAPH_PANE_WIDTH - sash_size,
                )
                right_width = min(self._right_pane_width, max_right_width)
                sash_position = client_width - right_width - sash_size
            else:
                sash_position = MIN_GRAPH_PANE_WIDTH
            self.graph_panes_splitter.SplitVertically(
                self.main_analysis_pane, self.comparison_pane, sash_position
            )
        else:
            client_width = self.graph_panes_splitter.GetClientSize().width
            if client_width > 0:
                self._right_pane_width = max(
                    MIN_GRAPH_PANE_WIDTH,
                    client_width
                    - self.graph_panes_splitter.GetSashPosition()
                    - self.graph_panes_splitter.GetSashSize(),
                )
            self.graph_panes_splitter.Unsplit(self.comparison_pane)
        self._right_pane_visible = visible
        if self._comparison_toggle is not None:
            self._comparison_toggle.SetValue(visible)
        self.graph_panes_splitter.Layout()
        if visible:
            self._request_stack_redraws("right")

    def add_graph_panel(
        self: _GraphStackState, panel: GraphPanelHost, stack: str = "middle"
    ) -> None:
        """Add a graph host, separating adjacent panels with horizontal splitters."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        if panel in self._graph_panels[stack]:
            raise ValueError("graph panel is already in this stack")

        # The new splitter is appended to the sizer, so remove the tail first.
        self._detach_stack_bottom_padding(stack)
        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        root = self._stack_roots[stack]
        if root is None:
            root = panel
            # A reused panel may be parked outside the scroller after removal.
            root.Reparent(window)
            sizer.Add(root, 1, wx.EXPAND)
        else:
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
                raise RuntimeError(f"could not split graph stack {stack!r}")
            new_splitter.Bind(
                wx.EVT_SPLITTER_SASH_POS_CHANGING,
                lambda event, stack=stack, new_splitter=new_splitter: (
                    self._on_graph_sash_changing(stack, new_splitter, event)
                ),
            )
            root = new_splitter
            sizer.Add(root, 1, wx.EXPAND)

        self._graph_panels[stack].append(panel)
        self._stack_roots[stack] = root
        self._layout_graph_stack(stack)

    def remove_graph_panel(
        self: _GraphStackState, panel: GraphPanelHost, stack: str = "middle"
    ) -> None:
        """Remove a graph host and collapse its splitter without disturbing others."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        if panel not in self._graph_panels[stack]:
            return
        # Removing a panel can replace the root item that follows the tail.
        self._detach_stack_bottom_padding(stack)
        self._remove_panel_from_stack_tree(stack, panel)
        self._graph_panels[stack].remove(panel)
        self._graph_panel_heights.pop(panel, None)
        if panel in self._queued_graph_redraws:
            self._pending_graph_redraws = deque(
                queued for queued in self._pending_graph_redraws if queued is not panel
            )
            self._queued_graph_redraws.remove(panel)
        if not self._pending_graph_redraws and self._graph_redraw_timer is not None:
            if self._graph_redraw_timer.IsRunning():
                self._graph_redraw_timer.Stop()
            self._graph_redraw_timer = None
        self._layout_graph_stack(stack)

    def replace_graph_panel(
        self: _GraphStackState,
        old_panel: GraphPanelHost,
        new_panel: GraphPanelHost,
        stack: str = "middle",
    ) -> None:
        """Replace a graph host, preserving panel height, order and scroll position."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        panels = self._graph_panels[stack]
        if old_panel not in panels:
            raise ValueError("graph panel is not in this stack")
        if new_panel in panels:
            raise ValueError("replacement graph panel is already in this stack")

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
                    f"graph panel {old_panel.panel_id!r} has an invalid parent"
                )
            new_panel.Reparent(parent)
            if not parent.ReplaceWindow(old_panel, new_panel):
                new_panel.Reparent(window)
                raise RuntimeError(
                    f"could not replace graph panel {old_panel.panel_id!r}"
                )
            # ReplaceWindow leaves the old native window alive until Destroy();
            # park it so scrolling/layout cannot allocate the retired panel.
            old_panel.Reparent(window.GetParent())

        panels[panels.index(old_panel)] = new_panel
        self._graph_panel_heights[new_panel] = self._graph_panel_heights.pop(
            old_panel, old_panel.GetSize().height
        )
        self._layout_graph_stack(stack)
        self._apply_graph_sash_heights(self._stack_roots[stack])
        window.Scroll(*view_start)

    def size_graph_panel_to_content(
        self: _GraphStackState, panel: GraphPanelHost, natural_height: int
    ) -> None:
        """Size a newly populated panel to its content, within usable height limits."""
        stack = next(
            (name for name, panels in self._graph_panels.items() if panel in panels),
            None,
        )
        if stack is None:
            raise ValueError("graph panel is not in a stack")
        # Keep small native views usable and cap large figures; the outer stack
        # provides scrolling when the resulting panels do not fit the viewport.
        self._graph_panel_heights[panel] = min(
            max(natural_height, MIN_GRAPH_PANEL_HEIGHT),
            MAX_NATURAL_GRAPH_PANEL_HEIGHT,
        )
        self._layout_graph_stack(stack)
        self._apply_graph_sash_heights(self._stack_roots[stack])

    def refresh_graph_stack_layouts(self: _GraphStackState) -> None:
        """Recalculate stack scroll ranges after the frame reaches its shown size."""
        # Initial panel insertion can happen before GTK assigns final viewport sizes.
        for stack in self._graph_panels:
            self._layout_graph_stack(stack)

    def move_graph_panel(
        self: _GraphStackState, panel: GraphPanelHost, stack: str, offset: int
    ) -> None:
        """Move a live panel within its stack without recreating its view."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        panels = self._graph_panels[stack]
        current_index = panels.index(panel)
        target_index = min(max(current_index + offset, 0), len(panels) - 1)
        if target_index == current_index:
            return

        reordered = list(panels)
        reordered.insert(target_index, reordered.pop(current_index))
        stack_window = self._stack_windows[stack]
        for existing_panel in tuple(panels):
            self.remove_graph_panel(existing_panel, stack)
            existing_panel.Reparent(stack_window)
        for existing_panel in reordered:
            self.add_graph_panel(existing_panel, stack)

    def request_visible_graph_redraws(self: _GraphStackState) -> None:
        """Redraw graph hosts that are visible after a stack scroll."""
        self._request_stack_redraws("middle")
        self._request_stack_redraws("right")

    def queue_graph_redraw(self: _GraphStackState, panel: GraphPanelHost) -> None:
        """Queue one visible panel for the shared redraw budget."""
        if not self.is_graph_panel_visible(panel):
            return
        if panel in self._queued_graph_redraws:
            return
        self._pending_graph_redraws.append(panel)
        self._queued_graph_redraws.add(panel)
        if self._graph_redraw_timer is None:
            self._graph_redraw_timer = wx.CallLater(1, self._draw_next_graph_panel)

    def draw_initial_graphs(self: _GraphStackState) -> None:
        """Draw currently visible plots before the playback timer starts."""
        if self._graph_redraw_timer is not None:
            if self._graph_redraw_timer.IsRunning():
                self._graph_redraw_timer.Stop()
            self._graph_redraw_timer = None
        pending = tuple(self._pending_graph_redraws)
        self._pending_graph_redraws.clear()
        self._queued_graph_redraws.clear()
        for panel in pending:
            if self.is_graph_panel_visible(panel):
                panel.draw_initial()

    def is_graph_panel_visible(self: _GraphStackState, panel: GraphPanelHost) -> bool:
        """Check whether a graph host intersects its scroll stack's viewport."""
        if not panel.IsShownOnScreen():
            return False
        stack_window = next(
            (
                self._stack_windows[stack]
                for stack, panels in self._graph_panels.items()
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
        self: _GraphStackState, stack: str, panel: GraphPanelHost
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
            raise RuntimeError(f"graph stack {stack!r} has an invalid splitter tree")
        if not self._remove_panel_from_splitter(stack, root, panel):
            raise RuntimeError(
                f"graph panel {panel.panel_id!r} is missing from its stack"
            )

    def _remove_panel_from_splitter(
        self: _GraphStackState,
        stack: str,
        splitter: wx.SplitterWindow,
        panel: GraphPanelHost,
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
                        f"graph stack {stack!r} has a broken splitter hierarchy"
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
                    raise RuntimeError(f"could not restore graph stack {stack!r}")
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

    def _stack_subtree_height(self: _GraphStackState, window: wx.Window) -> int:
        """Return the height a stack subtree needs: panel heights plus internal sashes."""
        if not isinstance(window, wx.SplitterWindow):
            # Stack leaves are graph hosts; wx exposes splitter children as Windows.
            return self._graph_panel_heights.get(
                cast(GraphPanelHost, window), MIN_GRAPH_PANEL_HEIGHT
            )
        return (
            self._stack_subtree_height(window.GetWindow1())
            + window.GetSashSize()
            + self._stack_subtree_height(window.GetWindow2())
        )

    def _layout_graph_stack(self: _GraphStackState, stack: str) -> None:
        """Synchronize the empty state, minimum sizes, and scroll layout."""

        def minimum_height(window: wx.Window) -> int:
            if not isinstance(window, wx.SplitterWindow):
                return self._stack_subtree_height(window)
            # wx clamps a sash to the minimum size of the panes on both sides, so
            # panels inside a splitter advertise only a small floor. The real
            # panel floor is enforced through _graph_panel_heights.
            first_pane, second_pane = window.GetWindow1(), window.GetWindow2()
            for child in (first_pane, second_pane):
                if not isinstance(child, wx.SplitterWindow):
                    child.SetMinSize(
                        wx.Size(GRAPH_PANEL_MIN_SIZE[0], SASH_DRAG_MIN_PANE)
                    )
            height = (
                minimum_height(first_pane)
                + window.GetSashSize()
                + minimum_height(second_pane)
            )
            window.SetMinimumPaneSize(SASH_DRAG_MIN_PANE)
            window.SetMinSize((GRAPH_PANEL_MIN_SIZE[0], height))
            return height

        root = self._stack_roots[stack]
        if root is not None:
            if not isinstance(root, wx.SplitterWindow):
                root.SetMinSize(
                    wx.Size(GRAPH_PANEL_MIN_SIZE[0], self._stack_subtree_height(root))
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

    def _detach_stack_bottom_padding(self: _GraphStackState, stack: str) -> None:
        """Remove the trailing sizer spacer before changing stack items."""
        if not self._stack_bottom_padding_active[stack]:
            return
        # Structural edits can reorder sizer items, so remove the known final item
        # while its position is still reliable and let layout add it back afterward.
        sizer = self._stack_sizers[stack]
        sizer.Detach(sizer.GetItemCount() - 1)
        self._stack_bottom_padding_active[stack] = False

    def _update_stack_virtual_size(self: _GraphStackState, stack: str) -> None:
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

    def _update_stack_scrollbar_visibility(self: _GraphStackState, stack: str) -> None:
        window = self._stack_windows[stack]
        has_overflow = window.GetScrollRange(wx.VERTICAL) > window.GetScrollThumb(
            wx.VERTICAL
        )
        # Only touch the scrollbars on change; each call can send another size event.
        if self._stack_overflowing.get(stack) == has_overflow:
            return
        self._stack_overflowing[stack] = has_overflow
        window.AlwaysShowScrollbars(False, has_overflow)

    def _on_stack_size(self: _GraphStackState, stack: str, event: wx.SizeEvent) -> None:
        self._update_stack_virtual_size(stack)
        self._update_stack_scrollbar_visibility(stack)
        event.Skip()

    def _sync_graph_panel_heights(self: _GraphStackState, stack: str) -> None:
        for panel in self._graph_panels[stack]:
            self._graph_panel_heights[panel] = panel.GetSize().height

    def _bottom_graph_panel(
        self: _GraphStackState, stack: str
    ) -> GraphPanelHost | None:
        pane = self._stack_roots[stack]
        while isinstance(pane, wx.SplitterWindow):
            pane = pane.GetWindow2()
        if pane is None:
            return None
        return cast(GraphPanelHost, pane)

    def _on_bottom_handle_down(
        self: _GraphStackState, stack: str, event: wx.MouseEvent
    ) -> None:
        panel = self._bottom_graph_panel(stack)
        if panel is None:
            return
        self._sync_graph_panel_heights(stack)
        self._bottom_drag_start[stack] = (
            wx.GetMousePosition().y,
            self._graph_panel_heights[panel],
        )
        self._stack_handles[stack].CaptureMouse()

    def _on_bottom_handle_motion(
        self: _GraphStackState, stack: str, event: wx.MouseEvent
    ) -> None:
        start = self._bottom_drag_start.get(stack)
        panel = self._bottom_graph_panel(stack)
        if start is None or panel is None or not event.Dragging():
            return
        start_y, start_height = start
        # Use screen coordinates: the handle itself moves as the panel grows.
        self._resize_graph_panel(
            stack, panel, start_height + wx.GetMousePosition().y - start_y
        )

    def _on_bottom_handle_up(
        self: _GraphStackState, stack: str, event: wx.MouseEvent
    ) -> None:
        self._bottom_drag_start.pop(stack, None)
        handle = self._stack_handles[stack]
        if handle.HasCapture():
            handle.ReleaseMouse()

    def _on_graph_sash_changing(
        self: _GraphStackState,
        stack: str,
        splitter: wx.SplitterWindow,
        event: wx.SplitterEvent,
    ) -> None:
        """Resize the panel above the sash; panels below keep their heights and the stack grows."""
        event.Veto()
        delta = event.GetSashPosition() - splitter.GetSashPosition()
        if delta == 0:
            return
        pane = splitter.GetWindow1()
        while isinstance(pane, wx.SplitterWindow):
            pane = pane.GetWindow2()
        panel = cast(GraphPanelHost, pane)
        self._sync_graph_panel_heights(stack)
        self._resize_graph_panel(stack, panel, self._graph_panel_heights[panel] + delta)

    def _resize_graph_panel(
        self: _GraphStackState, stack: str, panel: GraphPanelHost, height: int
    ) -> None:
        self._graph_panel_heights[panel] = max(MIN_GRAPH_PANEL_HEIGHT, height)
        self._layout_graph_stack(stack)
        self._apply_graph_sash_heights(self._stack_roots[stack])

    def _apply_graph_sash_heights(
        self: _GraphStackState, window: wx.Window | None
    ) -> None:
        """Set every sash so each panel keeps its requested height, top-down."""
        if not isinstance(window, wx.SplitterWindow):
            return
        window.SetSashPosition(self._stack_subtree_height(window.GetWindow1()))
        self._apply_graph_sash_heights(window.GetWindow1())
        self._apply_graph_sash_heights(window.GetWindow2())

    def _make_graph_pane(
        self: _GraphStackState, parent: wx.Window, stack: str, title: str
    ) -> tuple[wx.Panel, wx.ScrolledWindow]:
        graph_pane = wx.Panel(parent, wx.ID_ANY)
        graph_pane.SetName(title)
        pane_sizer = wx.BoxSizer(wx.VERTICAL)
        pane_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pane_title_label = wx.StaticText(graph_pane, wx.ID_ANY, title)
        pane_title_label.SetName(title)
        pane_header_sizer.Add(pane_title_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 8)
        add_graph_button = wx.Button(graph_pane, wx.ID_ANY, "Add graph")
        add_graph_button.SetName(f"Add graph to {stack} stack")
        set_tooltip(add_graph_button, f"Add a graph to {title}")
        self._add_buttons[stack] = add_graph_button
        add_graph_button.Bind(
            wx.EVT_BUTTON,
            lambda _event, stack=stack: self._request_add_graph(stack),
        )
        pane_header_sizer.Add(add_graph_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        if stack == "middle":
            comparison_toggle = wx.ToggleButton(graph_pane, wx.ID_ANY, "Comparison")
            self._comparison_toggle = comparison_toggle
            comparison_toggle.SetName("Toggle Comparison pane")
            set_tooltip(comparison_toggle, "Show or hide the Comparison pane")
            comparison_toggle.SetValue(False)
            comparison_toggle.Bind(
                wx.EVT_TOGGLEBUTTON,
                lambda _event: self.show_right_pane(comparison_toggle.GetValue()),
            )
            pane_header_sizer.Add(
                comparison_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4
            )
        else:
            close_pane_button = wx.Button(graph_pane, wx.ID_ANY, "Close pane")
            close_pane_button.SetName("Close Comparison pane")
            set_tooltip(close_pane_button, "Hide the Comparison pane")
            close_pane_button.Bind(
                wx.EVT_BUTTON, lambda _event: self.show_right_pane(False)
            )
            self._pane_close_buttons[stack] = close_pane_button
            pane_header_sizer.Add(
                close_pane_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4
            )
        pane_sizer.Add(pane_header_sizer, 0, wx.EXPAND)
        graph_stack_window = self._make_graph_stack(graph_pane, stack)
        graph_stack_window.SetName(f"{title} graph stack")
        pane_sizer.Add(
            graph_stack_window, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4
        )
        graph_pane.SetSizer(pane_sizer)
        return graph_pane, graph_stack_window

    def _make_graph_stack(
        self: _GraphStackState, parent: wx.Window, stack: str
    ) -> wx.ScrolledWindow:
        stack_scroller = wx.ScrolledWindow(parent, wx.ID_ANY, style=wx.VSCROLL)
        stack_scroller.AlwaysShowScrollbars(False, False)
        stack_scroller.SetScrollRate(0, 20)
        stack_sizer = wx.BoxSizer(wx.VERTICAL)
        empty_state_panel = wx.Panel(stack_scroller, wx.ID_ANY)
        empty_state_sizer = wx.BoxSizer(wx.VERTICAL)
        empty_state_label = wx.StaticText(
            empty_state_panel, wx.ID_ANY, "No graph panels"
        )
        empty_state_label.SetName(f"{stack} stack empty state")
        empty_state_sizer.Add(empty_state_label, 0, wx.ALL, 12)
        add_graph_button = wx.Button(empty_state_panel, wx.ID_ANY, "Add graph")
        add_graph_button.SetName(f"Add graph to empty {stack} stack")
        add_graph_button.Bind(
            wx.EVT_BUTTON,
            lambda _event, stack=stack: self._request_add_graph(stack),
        )
        empty_state_sizer.Add(add_graph_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        empty_state_panel.SetSizer(empty_state_sizer)
        stack_sizer.Add(empty_state_panel, 0, wx.EXPAND)
        bottom_resize_handle = wx.Panel(stack_scroller, wx.ID_ANY)
        bottom_resize_handle.SetMinSize(wx.Size(-1, BOTTOM_HANDLE_HEIGHT))
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
        stack_scroller.Bind(wx.EVT_SCROLLWIN, self._on_stack_scroll)
        stack_scroller.Bind(
            wx.EVT_SIZE,
            lambda event, stack=stack: self._on_stack_size(stack, event),
        )
        self._stack_windows[stack] = stack_scroller
        self._stack_sizers[stack] = stack_sizer
        self._stack_handles[stack] = bottom_resize_handle
        self._empty_panels[stack] = empty_state_panel
        return stack_scroller

    def _request_add_graph(self: _GraphStackState, stack: str) -> None:
        if self._on_add_graph is None:
            raise RuntimeError("graph-panel creation handler is not configured")
        self._on_add_graph(stack)

    def _request_stack_redraws(self: _GraphStackState, stack: str) -> None:
        for panel in self._graph_panels[stack]:
            panel.request_redraw()

    def _draw_next_graph_panel(self: _GraphStackState) -> None:
        self._graph_redraw_timer = None
        while self._pending_graph_redraws:
            panel = self._pending_graph_redraws.popleft()
            self._queued_graph_redraws.remove(panel)
            if self.is_graph_panel_visible(panel):
                panel.draw_if_needed()
                break
        if self._pending_graph_redraws:
            self._graph_redraw_timer = wx.CallLater(
                GRAPH_REDRAW_INTERVAL_MS, self._draw_next_graph_panel
            )

    def _on_stack_scroll(self: _GraphStackState, event: wx.ScrollWinEvent) -> None:
        self.request_visible_graph_redraws()
        event.Skip()
