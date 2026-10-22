"""Graph-panel creation, replacement and resource lifecycle for PlayerApp."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import uuid4

import wx
from matplotlib.backend_bases import MouseButton, MouseEvent
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg, NavigationToolbar2WxAgg
from matplotlib.figure import Figure

from .. import clock
from ..graph_panel import GraphPanelHost
from ..views import base
from ..views.trajectory3d import selection as trajectory3d_selection
from .state import PlayerAppState
from .support import EMPTY_GRAPH_LABEL, EMPTY_GRAPH_VIEW, _EmptyGraphView, _OpenView


class PanelManagementMixin:
    """Manage graph panel instances and their associated rendering resources."""

    def open_view(self: PlayerAppState, name: str) -> None:
        self._view_registry.open_view(name)

    def open_panel_view(
        self: PlayerAppState,
        name: str,
        panel_id: str,
        stack: str = "middle",
        *,
        force_replace: bool = False,
    ) -> None:
        """Open a view in the graph-panel instance identified by ``panel_id``."""
        if name == EMPTY_GRAPH_VIEW:
            self._open_view(
                name,
                _EmptyGraphView,
                panel_id=panel_id,
                stack=stack,
                force_replace=force_replace,
            )
            return
        if name not in self._view_registry.registered_views:
            raise ValueError(f"unknown view name: {name!r}")
        openers = {
            "trajectory-3d": self.open_trajectory_view,
            "speed-altitude": self.open_speed_altitude_view,
            "state-components": self.open_state_components_view,
            "rtn": self.open_rtn_view,
            "angular-velocity": self.open_angular_velocity_view,
            "direction-change": self.open_direction_change_view,
            "distance": self.open_distance_view,
            "ground-track": self.open_ground_track_view,
        }
        openers[name](panel_id=panel_id, stack=stack, force_replace=force_replace)

    def _add_graph_panel(self: PlayerAppState, stack: str) -> None:
        try:
            self.open_panel_view(EMPTY_GRAPH_VIEW, uuid4().hex, stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not add a graph panel: {error}",
                "Graph panel error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def _select_panel_view(
        self: PlayerAppState, name: str, panel_id: str, stack: str
    ) -> None:
        try:
            self.open_panel_view(name, panel_id, stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not create {self._panel_view_label(name)}: {error}",
                "Graph view error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def _move_panel(self: PlayerAppState, panel_id: str, offset: int) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is not None:
            self.workspace.move_graph_panel(opened.panel, opened.stack, offset)

    def _duplicate_panel(self: PlayerAppState, panel_id: str) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is None:
            return
        try:
            self.open_panel_view(opened.view_name, uuid4().hex, opened.stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not duplicate graph panel: {error}",
                "Graph panel error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def open_group(self: PlayerAppState, name: str) -> None:
        self._view_registry.open_group(name)

    def open_plots(self: PlayerAppState, selection: Sequence[str]) -> None:
        self._view_registry.open(selection)

    def close_view(self: PlayerAppState, name: str) -> None:
        """Close the default panel instance for a registered view."""
        opened = self._open_views.get(name)
        if opened is not None:
            self.close_panel(opened.panel_id)

    def close_panel(self: PlayerAppState, panel_id: str) -> None:
        """Close one graph-panel instance by its stable identifier."""
        self._dispose_open_view(panel_id)

    def _open_view(
        self: PlayerAppState,
        name: str,
        create_view: Callable[[wx.Window], base.View],
        *,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        if self._closed:
            raise RuntimeError("cannot open a view in a closed PlayerApp")
        if stack == "middle":
            stack_parent = self.workspace.main_analysis_stack
        elif stack == "right":
            stack_parent = self.workspace.comparison_stack
        else:
            raise ValueError(f"unknown graph stack {stack!r}")

        is_default_instance = panel_id is None
        replacing: _OpenView | None = None
        if is_default_instance:
            existing = self._open_views.get(name)
            if existing is not None:
                existing.panel.SetFocus()
                return
            panel_id = uuid4().hex
        elif not panel_id:
            raise ValueError("panel_id cannot be empty")
        else:
            existing = self._open_panels.get(panel_id)
            if existing is not None:
                if existing.view_name == name and not force_replace:
                    existing.panel.SetFocus()
                    return
                replacing = existing
                if force_replace and self._open_views.get(name) is existing:
                    is_default_instance = True

        if panel_id in self._open_panels and replacing is None:
            raise ValueError(f"panel instance already exists: {panel_id!r}")

        panel: GraphPanelHost | None = None
        panel_inserted = False
        view: base.View | None = None
        canvas: FigureCanvasWxAgg | None = None
        toolbar: NavigationToolbar2WxAgg | None = None
        click_callback_id: int | None = None
        unsubscribe: Callable[[], None] | None = None
        try:
            panel = GraphPanelHost(
                stack_parent,
                self._panel_view_label(name),
                lambda: self.close_panel(panel_id),
                is_visible=lambda: panel is not None
                and self.workspace.is_graph_panel_visible(panel),
                on_redraw_request=self.workspace.queue_graph_redraw,
                panel_id=panel_id,
                view_choices=self._panel_view_choices,
                selected_view=name,
                on_view_selected=lambda selected: self._select_panel_view(
                    selected, panel_id, stack
                ),
                on_move_up=lambda: self._move_panel(panel_id, -1),
                on_move_down=lambda: self._move_panel(panel_id, 1),
                on_duplicate=lambda: self._duplicate_panel(panel_id),
            )
            if replacing is None:
                self.workspace.add_graph_panel(panel, stack=stack)
            else:
                self.workspace.replace_graph_panel(replacing.panel, panel, stack=stack)
            panel_inserted = True
            view = create_view(panel.graph_scroller)
            content = view.build(self.series, self.time_unit)
            view.update(self.clock.t_now)
            if isinstance(content, Figure):
                canvas = FigureCanvasWxAgg(panel.graph_scroller, wx.ID_ANY, content)
                plot_toolbar = NavigationToolbar2WxAgg(canvas)
                plot_toolbar.Realize()
                toolbar = plot_toolbar
                panel.set_matplotlib_content(plot_toolbar, canvas)
                click_callback_id = canvas.mpl_connect(
                    "button_press_event",
                    lambda event: self._on_plot_click(event, plot_toolbar),
                )
            elif isinstance(content, wx.Window):
                panel.set_native_content(content)
            else:
                raise TypeError(
                    f"{name!r} view build returned unsupported content "
                    f"{type(content).__name__!r}"
                )

            # Size a new or newly populated panel to its plot once. Replacing one
            # populated graph with another must retain the user's chosen height.
            if name != EMPTY_GRAPH_VIEW and (
                replacing is None or replacing.view_name == EMPTY_GRAPH_VIEW
            ):
                natural_height = getattr(panel, "natural_content_height", None)
                size_to_content = getattr(
                    self.workspace, "size_graph_panel_to_content", None
                )
                if callable(natural_height) and callable(size_to_content):
                    size_to_content(panel, natural_height())

            def update_view(time_s: float) -> None:
                view.update(time_s)
                if panel is not None and canvas is not None:
                    panel.request_redraw()

            unsubscribe = (
                self.clock.subscribe(update_view)
                if name != EMPTY_GRAPH_VIEW
                else lambda: None
            )
            opened_state = _OpenView(
                panel_id,
                name,
                stack,
                panel,
                view,
                unsubscribe,
                canvas,
                toolbar,
                click_callback_id,
            )
            self.frame.Layout()
            panel.Layout()
            if isinstance(content, wx.Window) and name == "trajectory-3d":
                trajectory3d_selection.validate_vtk_render_context(view)
            if canvas is not None:
                panel.request_redraw()
        except Exception:
            if replacing is None:
                self._open_panels.pop(panel_id, None)
            if self._open_views.get(name) is not None:
                if self._open_views[name].panel_id == panel_id:
                    self._open_views.pop(name)
            if canvas is not None and click_callback_id is not None:
                canvas.mpl_disconnect(click_callback_id)
            if unsubscribe is not None:
                unsubscribe()
            if view is not None:
                view.close()
            if panel is not None:
                try:
                    if panel_inserted:
                        if replacing is None:
                            self.workspace.remove_graph_panel(panel, stack=stack)
                        else:
                            self.workspace.replace_graph_panel(
                                panel, replacing.panel, stack=stack
                            )
                finally:
                    panel.Destroy()
            raise
        self._open_panels[panel_id] = opened_state
        if is_default_instance:
            self._open_views[name] = opened_state
        if replacing is not None:
            try:
                self._release_open_view_resources(replacing)
            finally:
                replacing.panel.Destroy()

    def _on_plot_click(
        self: PlayerAppState, event: MouseEvent, toolbar: NavigationToolbar2WxAgg
    ) -> None:
        if (
            getattr(toolbar, "mode", "")
            or event.button != MouseButton.LEFT
            or event.inaxes is None
            or event.xdata is None
            or event.inaxes.name == "3d"
        ):
            return

        target_time_s = (
            self.clock.t_start + event.xdata * self.time_unit.get_divisor_s()
        )
        self.clock.seek(target_time_s)
        self._update_time_display()

    def _panel_view_label(self: PlayerAppState, name: str) -> str:
        if name == EMPTY_GRAPH_VIEW:
            return EMPTY_GRAPH_LABEL
        return self._view_registry.label_for(name)

    def _dispose_open_view(self: PlayerAppState, panel_id: str) -> None:
        opened = self._open_panels.pop(panel_id, None)
        if opened is None:
            return
        try:
            self._release_open_view_resources(opened)
        finally:
            try:
                self.workspace.remove_graph_panel(opened.panel, stack=opened.stack)
            finally:
                opened.panel.Destroy()

    def _release_open_view_resources(self: PlayerAppState, opened: _OpenView) -> None:
        if self._open_views.get(opened.view_name) is opened:
            self._open_views.pop(opened.view_name)
        if opened.canvas is not None and opened.click_callback_id is not None:
            opened.canvas.mpl_disconnect(opened.click_callback_id)
        opened.unsubscribe()
        opened.view.close()
