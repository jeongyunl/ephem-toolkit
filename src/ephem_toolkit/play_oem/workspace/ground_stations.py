"""Inline Ground Stations manager for the Controls & Info feature rail."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import wx

from ..ground_stations import GroundStation, create_ground_station


class GroundStationsManager:
    """Render an expandable, inline editor for persistent station definitions."""

    def __init__(
        self,
        parent: wx.Window,
        stations: Sequence[GroundStation],
        on_change: Callable[[list[GroundStation]], None] | None,
    ) -> None:
        self._parent = parent
        self._stations = list(stations)
        self._on_change = on_change
        self._expanded_id: str | None = None
        self._is_new_draft = False
        self._scroll = wx.ScrolledWindow(
            parent, wx.ID_ANY, style=wx.VSCROLL | wx.TAB_TRAVERSAL
        )
        self._scroll.SetName("Ground Stations manager")
        self._scroll.SetScrollRate(0, 10)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self._scroll.SetSizer(self._sizer)
        self._render()
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page_sizer.Add(self._scroll, 1, wx.EXPAND)
        parent.SetSizer(page_sizer)

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._stations = list(stations)
        if self._expanded_id is not None and not any(
            station.station_id == self._expanded_id for station in self._stations
        ):
            self._expanded_id = None
            self._is_new_draft = False
        self._render()

    def select_station(self, station_id: str | None) -> None:
        """Expand a row, asking before discarding an edited form."""
        if station_id == self._expanded_id and not self._is_new_draft:
            if not self._resolve_dirty_form():
                return
            self._expanded_id = None
            self._render()
            return
        if not self._resolve_dirty_form():
            return
        self._expanded_id = station_id
        self._is_new_draft = False
        self._render()

    def _render(self) -> None:
        self._scroll.Freeze()
        self._scroll.DestroyChildren()
        self._sizer.Clear()
        self._fields = {}
        add = wx.Button(self._scroll, wx.ID_ANY, "Add Ground Station")
        add.SetName("Add ground station")
        add.Bind(wx.EVT_BUTTON, self._on_add)
        self._sizer.Add(add, 0, wx.EXPAND | wx.ALL, 8)

        if not self._stations and not self._is_new_draft:
            empty = wx.StaticText(
                self._scroll,
                wx.ID_ANY,
                "No ground stations yet. Add a station to calculate geometric access.",
            )
            empty.SetName("No ground stations empty state")
            empty.Wrap(220)
            self._sizer.Add(empty, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        for station in self._stations:
            expanded = station.station_id == self._expanded_id
            row = wx.ToggleButton(
                self._scroll,
                wx.ID_ANY,
                (
                    f"{station.name}  ·  {station.latitude_deg:.4f}°, "
                    f"{station.longitude_deg:.4f}°  ·  "
                    f"mask {station.minimum_elevation_deg}°"
                ),
            )
            row.SetName(f"Ground station {station.name}")
            row.SetValue(expanded)
            row.SetToolTip(
                f"{station.name}, latitude {station.latitude_deg}°, "
                f"longitude {station.longitude_deg}°, "
                f"minimum elevation {station.minimum_elevation_deg}°"
            )
            row.Bind(
                wx.EVT_TOGGLEBUTTON,
                lambda _event, selected_id=station.station_id: self.select_station(
                    selected_id
                ),
            )
            self._sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
            if expanded:
                self._add_editor(station)
        if self._is_new_draft:
            self._add_editor(None)
        self._sizer.Add((0, 8), 0)
        self._scroll.FitInside()
        self._scroll.Layout()
        self._scroll.Thaw()

    def _add_editor(self, station: GroundStation | None) -> None:
        editor = wx.Panel(self._scroll, wx.ID_ANY)
        editor.SetName("Ground station inline editor")
        editor_sizer = wx.BoxSizer(wx.VERTICAL)
        self._fields: dict[str, wx.TextCtrl] = {}
        defaults = (
            ("name", "Name", "" if station is None else station.name),
            (
                "latitude_deg",
                "Latitude (degrees)",
                "" if station is None else str(station.latitude_deg),
            ),
            (
                "longitude_deg",
                "Longitude (degrees)",
                "" if station is None else str(station.longitude_deg),
            ),
            (
                "altitude_m",
                "Ellipsoid altitude (meters)",
                "" if station is None else str(station.altitude_m),
            ),
        )
        for key, label, initial in defaults:
            text_label = wx.StaticText(editor, wx.ID_ANY, label)
            text_label.SetName(f"Ground station {label} label")
            field = wx.TextCtrl(editor, wx.ID_ANY, initial)
            field.SetName(f"Ground station {key}")
            self._fields[key] = field
            editor_sizer.Add(text_label, 0, wx.EXPAND | wx.TOP, 5)
            editor_sizer.Add(field, 0, wx.EXPAND | wx.TOP, 2)
        mask_label = wx.StaticText(editor, wx.ID_ANY, "Minimum elevation (degrees)")
        mask_label.SetName("Ground station minimum elevation label")
        self._mask_control = wx.SpinCtrl(
            editor,
            wx.ID_ANY,
            value=str(10 if station is None else station.minimum_elevation_deg),
            min=0,
            max=90,
        )
        self._mask_control.SetName("Ground station minimum elevation")
        editor_sizer.Add(mask_label, 0, wx.EXPAND | wx.TOP, 5)
        editor_sizer.Add(self._mask_control, 0, wx.EXPAND | wx.TOP, 2)

        self._error_label = wx.StaticText(editor, wx.ID_ANY, "")
        self._error_label.SetName("Ground station validation error")
        self._error_label.SetForegroundColour(wx.Colour(190, 35, 35))
        editor_sizer.Add(self._error_label, 0, wx.EXPAND | wx.TOP, 5)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        save = wx.Button(editor, wx.ID_ANY, "Save")
        save.SetName("Save ground station")
        save.Bind(wx.EVT_BUTTON, self._on_save)
        cancel = wx.Button(editor, wx.ID_ANY, "Cancel")
        cancel.SetName("Cancel ground station edits")
        cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
        actions.Add(save, 0, wx.RIGHT, 4)
        actions.Add(cancel, 0, wx.RIGHT, 4)
        if station is not None:
            remove = wx.Button(editor, wx.ID_ANY, "Remove")
            remove.SetName(f"Remove ground station {station.name}")
            remove.Bind(
                wx.EVT_BUTTON,
                lambda _event, target=station: self._on_remove(target),
            )
            actions.Add(remove, 0)
        editor_sizer.Add(actions, 0, wx.EXPAND | wx.TOP, 8)
        editor.SetSizer(editor_sizer)
        self._sizer.Add(editor, 0, wx.EXPAND | wx.ALL, 8)
        self._edit_snapshot = self._form_values()

    def _form_values(self) -> tuple[str, ...]:
        if not getattr(self, "_fields", None):
            return ()
        return (
            self._fields["name"].GetValue(),
            self._fields["latitude_deg"].GetValue(),
            self._fields["longitude_deg"].GetValue(),
            self._fields["altitude_m"].GetValue(),
            str(self._mask_control.GetValue()),
        )

    def _resolve_dirty_form(self) -> bool:
        if not self._fields or self._form_values() == self._edit_snapshot:
            return True
        dialog = wx.MessageDialog(
            self._parent,
            "Save changes to this ground station before switching?",
            "Unsaved Ground Station Changes",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        try:
            result = dialog.ShowModal()
        finally:
            dialog.Destroy()
        if result == wx.ID_YES:
            return self._save_form()
        if result == wx.ID_NO:
            return True
        return False

    def _on_add(self, _event: wx.CommandEvent) -> None:
        if not self._resolve_dirty_form():
            return
        self._expanded_id = None
        self._is_new_draft = True
        self._render()

    def _on_save(self, _event: wx.CommandEvent) -> None:
        self._save_form()

    def _save_form(self) -> bool:
        try:
            values = self._form_values()
            name = values[0].strip()
            latitude = float(values[1])
            longitude = float(values[2])
            altitude = float(values[3])
            mask = self._mask_control.GetValue()
            previous = next(
                (
                    item
                    for item in self._stations
                    if item.station_id == self._expanded_id
                ),
                None,
            )
            updated = GroundStation(
                (
                    previous.station_id
                    if previous is not None
                    else create_ground_station(
                        name, latitude, longitude, altitude, mask
                    ).station_id
                ),
                name,
                latitude,
                longitude,
                altitude,
                mask,
            )
        except (ValueError, OverflowError) as error:
            self._error_label.SetLabel(str(error) or "Enter valid station values.")
            return False
        stations = list(self._stations)
        if previous is None:
            stations.append(updated)
        else:
            stations = [
                updated if item.station_id == previous.station_id else item
                for item in stations
            ]
        self._apply_changes(stations)
        self._expanded_id = updated.station_id
        self._is_new_draft = False
        self._render()
        return True

    def _on_cancel(self, _event: wx.CommandEvent) -> None:
        self._expanded_id = None
        self._is_new_draft = False
        self._render()

    def _on_remove(self, station: GroundStation) -> None:
        result = wx.MessageBox(
            f"Remove ground station {station.name!r}?",
            "Remove Ground Station",
            wx.YES_NO | wx.ICON_QUESTION,
            self._parent,
        )
        if result != wx.YES:
            return
        self._apply_changes(
            [item for item in self._stations if item.station_id != station.station_id]
        )
        self._expanded_id = None
        self._is_new_draft = False
        self._render()

    def _apply_changes(self, stations: list[GroundStation]) -> None:
        self._stations = stations
        if self._on_change is not None:
            self._on_change(list(stations))
