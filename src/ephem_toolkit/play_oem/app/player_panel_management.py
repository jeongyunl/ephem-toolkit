"""Data-data-view panel creation, replacement and resource lifecycle for PlayerApp."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import uuid4

import wx
from matplotlib.backend_bases import MouseButton, MouseEvent
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg, NavigationToolbar2WxAgg
from matplotlib.figure import Figure

from .. import time_range
from ..data_view_panel import DataViewPanelHost
from ..matplotlib_helpers import create_figure
from ..views import data_view_base as base
from ..views.trajectory3d import selection as trajectory3d_selection
from ..widgets.matplotlib_panel import MatplotlibPanel
from .player_app_state import PlayerAppState
from .player_app_support import (
    EMPTY_DATA_VIEW,
    EMPTY_DATA_VIEW_LABEL,
    PanelBuildResources,
    _EmptyDataView,
    _OpenDataView,
    _PendingDataView,
)


def _release_view_resources(
    data_view: base.DataView | None,
    canvas: FigureCanvasWxAgg | None,
    click_callback_id: int | None,
    unsubscribe: Callable[[], None] | None,
) -> None:
    if canvas is not None and click_callback_id is not None:
        canvas.mpl_disconnect(click_callback_id)
    if unsubscribe is not None:
        unsubscribe()
    if data_view is not None:
        data_view.close()


class PanelManagementMixin:
    """Manage data-view panel instances and their associated rendering resources."""

    def _rollback_open_data_view(
        self: PlayerAppState,
        *,
        name: str,
        panel_id: str,
        stack: str,
        replacing: _OpenDataView | None,
        panel: DataViewPanelHost | None,
        panel_inserted: bool,
        data_view: base.DataView | None,
        canvas: FigureCanvasWxAgg | None,
        click_callback_id: int | None,
        unsubscribe: Callable[[], None] | None,
    ) -> None:
        if replacing is None:
            self._open_panels.pop(panel_id, None)
            default = self._open_data_views.get(name)
            if default is not None and default.panel_id == panel_id:
                self._open_data_views.pop(name)
        _release_view_resources(data_view, canvas, click_callback_id, unsubscribe)
        if panel is not None:
            try:
                if panel_inserted:
                    if replacing is None:
                        self.workspace.remove_data_view_panel(panel, stack=stack)
                    else:
                        self.workspace.replace_data_view_panel(
                            panel, replacing.panel, stack=stack
                        )
            finally:
                panel.Destroy()

    def _create_data_view_panel(
        self: PlayerAppState,
        name: str,
        panel_id: str,
        stack: str,
        stack_parent: wx.Window,
        panel_ref: list[DataViewPanelHost | None],
    ) -> DataViewPanelHost:
        return DataViewPanelHost(
            stack_parent,
            self._panel_data_view_label(name),
            lambda: self.close_panel(panel_id),
            is_visible=lambda: self._panel_is_visible(panel_ref[0]),
            on_redraw_request=self.workspace.queue_data_view_redraw,
            on_show=lambda: self._sync_open_panel(panel_id),
            panel_id=panel_id,
            data_view_choices=self._panel_data_view_choices,
            selected_view=name,
            on_view_selected=lambda selected: self._select_panel_view(
                selected, panel_id, stack
            ),
            on_move_up=lambda: self._move_panel(panel_id, -1),
            on_move_down=lambda: self._move_panel(panel_id, 1),
            on_duplicate=lambda: self._duplicate_panel(panel_id),
        )

    def _panel_is_visible(
        self: PlayerAppState, panel: DataViewPanelHost | None
    ) -> bool:
        return panel is not None and self.workspace.is_data_view_panel_visible(panel)

    def _build_view_content(
        self: PlayerAppState,
        data_view: base.DataView,
    ) -> tuple[object, bool]:
        resolved_range = time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            self.clock.t_now,
        )
        coverage = (self.clock.t_start, self.clock.t_end)
        store_context = self._store_state.view_context
        placeholder_builder = getattr(data_view, "build_placeholder", None)
        if store_context is None:
            if not callable(placeholder_builder):
                figure = create_figure((8.0, 4.5))
                axes = figure.add_subplot(111)
                axes.set_axis_off()
                label = getattr(data_view, "label", getattr(data_view, "name", "Data View"))
                axes.text(0.5, 0.55, label, ha="center", va="center", fontsize=12)
                axes.text(0.5, 0.45, "Waiting for OEM data…", ha="center", va="center", color="0.45")
                content = figure
            else:
                content = placeholder_builder()
            return content, True
        store_context = store_context.with_range(resolved_range, coverage)
        self._store_state.view_context = store_context
        content = data_view.build_from_store(store_context)
        data_view.update(self.clock.t_now)
        return content, False

    def _attach_view_content(
        self: PlayerAppState,
        name: str,
        panel: DataViewPanelHost,
        content: object,
        *,
        data_view: base.DataView | None = None,
        preserve_aspect_ratio: bool = False,
    ) -> tuple[FigureCanvasWxAgg | None, NavigationToolbar2WxAgg | None, int | None]:
        if isinstance(content, Figure):
            plot_panel = MatplotlibPanel(
                panel.data_view_scroller,
                content,
                toolbar_factory=NavigationToolbar2WxAgg,
                preserve_aspect_ratio=preserve_aspect_ratio,
            )
            canvas = plot_panel.canvas
            toolbar_window = plot_panel.toolbar
            if not isinstance(toolbar_window, NavigationToolbar2WxAgg):
                raise RuntimeError(
                    "graph Matplotlib panel requires a navigation toolbar"
                )
            toolbar = toolbar_window
            panel.set_matplotlib_content(plot_panel)
            click_callback_id = canvas.mpl_connect(
                "button_press_event",
                lambda event: self._on_plot_click(event, toolbar, data_view),
            )
            return canvas, toolbar, click_callback_id
        if isinstance(content, wx.Window):
            panel.set_native_content(content)
            return None, None, None
        raise TypeError(
            f"{name!r} view build returned unsupported content "
            f"{type(content).__name__!r}"
        )

    def _insert_data_view_panel(
        self: PlayerAppState,
        panel: DataViewPanelHost,
        stack: str,
        replacing: _OpenDataView | None,
    ) -> None:
        if replacing is None:
            self.workspace.add_data_view_panel(panel, stack=stack)
        else:
            self.workspace.replace_data_view_panel(replacing.panel, panel, stack=stack)

    def _size_opened_panel(
        self: PlayerAppState,
        name: str,
        panel: DataViewPanelHost,
        replacing: _OpenDataView | None,
    ) -> None:
        if name == EMPTY_DATA_VIEW:
            return
        if replacing is not None and replacing.data_view_name != EMPTY_DATA_VIEW:
            return
        natural_height = getattr(panel, "natural_content_height", None)
        size_to_content = getattr(self.workspace, "size_data_view_panel_to_content", None)
        if callable(natural_height) and callable(size_to_content):
            size_to_content(panel, natural_height())

    def _register_opened_view(
        self: PlayerAppState,
        *,
        panel_id: str,
        name: str,
        stack: str,
        panel: DataViewPanelHost,
        resources: PanelBuildResources,
        requires_store_rebuild: bool,
    ) -> _OpenDataView:
        if resources.data_view is None or resources.unsubscribe is None:
            raise RuntimeError("panel resources are incomplete")
        opened_state = _OpenDataView(
            panel_id,
            name,
            stack,
            panel,
            resources.data_view,
            resources.unsubscribe,
            resources.canvas,
            resources.toolbar,
            resources.click_callback_id,
            requires_store_rebuild=requires_store_rebuild,
        )
        return opened_state

    def _resolve_panel_target(
        self: PlayerAppState,
        name: str,
        panel_id: str | None,
        force_replace: bool,
    ) -> tuple[str, str | None, _OpenDataView | None, bool, bool]:
        """Resolve default-instance, explicit-instance, and replacement state."""
        is_default_instance = panel_id is None
        replacing: _OpenDataView | None = None
        if is_default_instance:
            existing = self._open_data_views.get(name)
            if existing is not None:
                existing.panel.SetFocus()
                return name, None, None, True, True
            panel_id = uuid4().hex
        elif not panel_id:
            raise ValueError("panel_id cannot be empty")
        else:
            existing = self._open_panels.get(panel_id)
            if existing is not None:
                if existing.data_view_name == name and not force_replace:
                    existing.panel.SetFocus()
                    return name, panel_id, None, False, True
                replacing = existing
                if force_replace and self._open_data_views.get(name) is existing:
                    is_default_instance = True
        if panel_id in self._open_panels and replacing is None:
            raise ValueError(f"panel instance already exists: {panel_id!r}")
        return name, panel_id, replacing, is_default_instance, False

    def open_data_view(self: PlayerAppState, name: str) -> None:
        self._data_view_registry.open_data_view(name)

    def open_panel_data_view(
        self: PlayerAppState,
        name: str,
        *,
        panel_id: str,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open a view in the data-data-view panel instance identified by ``panel_id``."""
        if name == EMPTY_DATA_VIEW:
            self._open_data_view(
                name,
                _EmptyDataView,
                panel_id=panel_id,
                stack=stack,
                force_replace=force_replace,
            )
            return
        if name not in self._data_view_registry.registered_data_views:
            print(f"Error: unknown data-view name {name!r}")
            self._open_data_view(
                EMPTY_DATA_VIEW,
                _EmptyDataView,
                panel_id=panel_id,
                stack=stack,
                force_replace=force_replace,
            )
            return
        if not self._oem_loaded:
            self._open_pending_data_view(
                name,
                panel_id=panel_id,
                stack=stack,
                force_replace=force_replace,
            )
            return
        openers = {
            "trajectory-3d": self.open_trajectory_view,
            "speed-altitude": self.open_speed_altitude_view,
            "state-components": self.open_state_components_view,
            "rtn": self.open_rtn_view,
            "angular-velocity": self.open_angular_velocity_view,
            "direction-change": self.open_direction_change_view,
            "distance": self.open_distance_view,
            "ground-track": self.open_ground_track_view,
            "elevation-profile": self.open_elevation_profile_view,
            "azimuth-profile": self.open_azimuth_profile_view,
            "range-profile": self.open_range_profile_view,
            "pass-list": self.open_pass_list_view,
            "sky-view": self.open_sky_view,
        }
        openers[name](panel_id=panel_id, stack=stack, force_replace=force_replace)

    def _add_data_view_panel(self: PlayerAppState, stack: str) -> None:
        try:
            self.open_panel_data_view(EMPTY_DATA_VIEW, panel_id=uuid4().hex, stack=stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not add a data-view panel: {error}",
                "DataData-view panel error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def _select_panel_view(
        self: PlayerAppState, name: str, panel_id: str, stack: str
    ) -> None:
        try:
            self.open_panel_data_view(name, panel_id=panel_id, stack=stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not create {self._panel_data_view_label(name)}: {error}",
                "Data view error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def _move_panel(self: PlayerAppState, panel_id: str, offset: int) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is not None:
            self.workspace.move_data_view_panel(opened.panel, opened.stack, offset)

    def _duplicate_panel(self: PlayerAppState, panel_id: str) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is None:
            return
        try:
            self.open_panel_data_view(
                opened.data_view_name,
                panel_id=uuid4().hex,
                stack=opened.stack,
            )
        except Exception as error:
            wx.MessageBox(
                f"Could not duplicate data-view panel: {error}",
                "DataData-view panel error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def open_preset(self: PlayerAppState, name: str) -> None:
        self._data_view_registry.open_preset(name)

    def open_data_views(self: PlayerAppState, selection: Sequence[str]) -> None:
        self._data_view_registry.open(selection)

    def open_pending_data_views(self: PlayerAppState, selection: Sequence[str]) -> None:
        """Show selected data-view panels before the first OEM batch is ready."""
        for name in selection:
            self._open_pending_data_view(name)

    def _open_pending_data_view(
        self: PlayerAppState,
        name: str,
        *,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        self._open_data_view(
            name,
            lambda panel: _PendingDataView(panel, self._panel_data_view_label(name)),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def close_view(self: PlayerAppState, name: str) -> None:
        """Close the default panel instance for a registered view."""
        opened = self._open_data_views.get(name)
        if opened is not None:
            self.close_panel(opened.panel_id)

    def close_panel(self: PlayerAppState, panel_id: str) -> None:
        """Close one data-data-view panel instance by its stable identifier."""
        self._dispose_open_data_view(panel_id)

    def _open_data_view(
        self: PlayerAppState,
        name: str,
        create_data_view: Callable[[wx.Window], base.DataView],
        *,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        if self._closed:
            raise RuntimeError("cannot open a view in a closed PlayerApp")
        self._publish_range_hint()
        if stack == "middle":
            stack_parent = self.workspace.main_stack
        elif stack == "right":
            stack_parent = self.workspace.additional_stack
        else:
            raise ValueError(f"unknown data-view stack {stack!r}")

        _, resolved_panel_id, replacing, is_default_instance, stopped = (
            self._resolve_panel_target(name, panel_id, force_replace)
        )
        if stopped:
            return
        panel_id = resolved_panel_id
        assert panel_id is not None

        resources = PanelBuildResources()
        try:
            panel_ref: list[DataViewPanelHost | None] = [None]
            panel = self._create_data_view_panel(
                name, panel_id, stack, stack_parent, panel_ref
            )
            resources.panel = panel
            panel_ref[0] = panel
            self._insert_data_view_panel(panel, stack, replacing)
            resources.panel_inserted = True
            view = create_data_view(panel.data_view_scroller)
            resources.data_view = view
            content, requires_store_rebuild = self._build_view_content(view)
            resources.canvas, resources.toolbar, resources.click_callback_id = (
                self._attach_view_content(
                    name,
                    panel,
                    content,
                    data_view=view,
                    preserve_aspect_ratio=bool(
                        getattr(
                            view,
                            "preserve_canvas_aspect_ratio",
                            False,
                        )
                    ),
                )
            )

            # Size a new or newly populated panel to its plot once. Replacing one
            # populated graph with another must retain the user's chosen height.
            self._size_opened_panel(name, panel, replacing)

            # Clock updates use one controller-owned dispatch across all data views.
            resources.unsubscribe = lambda: None
            opened_state = self._register_opened_view(
                panel_id=panel_id,
                name=name,
                stack=stack,
                panel=panel,
                resources=resources,
                requires_store_rebuild=requires_store_rebuild,
            )
            self.frame.Layout()
            panel.Layout()
            if isinstance(content, wx.Window) and name == "trajectory-3d":
                trajectory3d_selection.validate_vtk_render_context(view)
            if resources.canvas is not None:
                panel.request_redraw()
        except Exception:
            failed_data_view = resources.data_view
            if failed_data_view is not None:
                close = getattr(failed_data_view, "close", None)
                if callable(close):
                    close()
                resources.data_view = None
            self._rollback_open_data_view(
                name=name,
                panel_id=panel_id,
                stack=stack,
                replacing=replacing,
                panel=resources.panel,
                panel_inserted=resources.panel_inserted,
                data_view=resources.data_view,
                canvas=resources.canvas,
                click_callback_id=resources.click_callback_id,
                unsubscribe=resources.unsubscribe,
            )
            raise
        self._open_panels[panel_id] = opened_state
        if is_default_instance:
            self._open_data_views[name] = opened_state
        if replacing is not None:
            try:
                self._release_open_data_view_resources(replacing)
            finally:
                replacing.panel.Destroy()
        self._publish_range_hint()

    def _on_plot_click(
        self: PlayerAppState,
        event: MouseEvent,
        toolbar: NavigationToolbar2WxAgg,
        data_view: base.DataView | None = None,
    ) -> None:
        if (
            getattr(toolbar, "mode", "")
            or event.button != MouseButton.LEFT
            or event.inaxes is None
            or event.xdata is None
            or (
                data_view is not None
                and getattr(data_view, "seek_on_click", True) is False
            )
        ):
            return
        origin_s = getattr(event.inaxes, "_play_oem_time_origin_s", None)
        divisor_s = getattr(event.inaxes, "_play_oem_time_divisor_s", None)
        seek_enabled = getattr(event.inaxes, "_play_oem_seek_enabled", None)
        if seek_enabled is not True or origin_s is None or divisor_s is None:
            return
        target_time_s = (
            origin_s + event.xdata * divisor_s
        )
        self.clock.seek(target_time_s)
        self._update_time_display()

    def _panel_data_view_label(self: PlayerAppState, name: str) -> str:
        if name == EMPTY_DATA_VIEW:
            return EMPTY_DATA_VIEW_LABEL
        return self._data_view_registry.label_for(name)

    def _dispose_open_data_view(self: PlayerAppState, panel_id: str) -> None:
        opened = self._open_panels.pop(panel_id, None)
        if opened is None:
            return
        try:
            self._release_open_data_view_resources(opened)
        finally:
            try:
                self.workspace.remove_data_view_panel(opened.panel, stack=opened.stack)
            finally:
                opened.panel.Destroy()
        self._publish_range_hint()

    def _release_open_data_view_resources(self: PlayerAppState, opened: _OpenDataView) -> None:
        if self._open_data_views.get(opened.data_view_name) is opened:
            self._open_data_views.pop(opened.data_view_name)
        _release_view_resources(
            opened.data_view,
            opened.canvas,
            opened.click_callback_id,
            opened.unsubscribe,
        )
