"""Compact controls for playback limits and the shared plot interval."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import wx

from ephem_toolkit.core import time_utils

from .. import time_range


def _timestamp(value_s: float) -> str:
    return time_utils.datetime_to_iso8601(
        time_utils.tt_s_to_datetime(value_s), fractional_second_places=3
    )


def _parse_endpoint(text: str, fixed: bool) -> time_range.TimeRangeEndpoint:
    parsed = time_utils.parse_time_or_duration(text.strip())
    if fixed:
        if isinstance(parsed, timedelta):
            raise ValueError("Fixed time requires a UTC timestamp")
        return time_range.TimeRangeEndpoint(
            "fixed", time_utils.datetime_to_tt_s(parsed)
        )
    if not isinstance(parsed, timedelta):
        raise ValueError("Playback offset requires a duration such as -1h or +3h")
    return time_range.TimeRangeEndpoint("offset", parsed.total_seconds())


class TimeRangeEditor(wx.Panel):
    """Compact plot endpoint controls with inline validation."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        playback: tuple[float, float],
        plot_rule: time_range.PlotTimeRange,
        now: Callable[[], float],
        on_plot: Callable[[time_range.PlotTimeRange], None],
        on_begin_edit: Callable[[], None],
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        self.playback, self.plot_rule = playback, plot_rule
        self._now, self._on_plot = now, on_plot
        self._on_begin_edit = on_begin_edit
        self._syncing = False
        outer = wx.BoxSizer(wx.VERTICAL)

        plot_row = wx.BoxSizer(wx.HORIZONTAL)
        self.plot_enabled = wx.CheckBox(self, label="Plot range")
        self.plot_enabled.SetName("Enable shared plot time range")
        self.plot_enabled.Bind(wx.EVT_CHECKBOX, self._toggle_plot)
        plot_row.Add(self.plot_enabled, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.endpoint_fields: dict[str, wx.TextCtrl] = {}
        self.endpoint_fixed: dict[str, wx.CheckBox] = {}
        self.endpoint_labels: dict[str, wx.StaticText] = {}
        for name, label in (("start", "From"), ("end", "To")):
            endpoint_label = wx.StaticText(self, label=label)
            plot_row.Add(
                endpoint_label,
                0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                4,
            )
            field = self._field(f"Plot {label.lower()} time or playback offset")
            field.SetMinSize(wx.Size(150, -1))
            fixed = wx.CheckBox(self, label="Fixed time")
            fixed.SetName(f"Plot {label.lower()} is fixed UTC time")
            fixed.SetToolTip(
                "Checked: fixed UTC timestamp. Unchecked: offset from current playback time."
            )
            field.Bind(
                wx.EVT_TEXT_ENTER,
                lambda event, endpoint=name: self._submit_plot(event, endpoint),
            )
            field.Bind(
                wx.EVT_KILL_FOCUS,
                lambda event, endpoint=name: self._submit_plot(
                    event, endpoint, focus_loss=True
                ),
            )
            field.Bind(
                wx.EVT_CHAR,
                lambda event, endpoint=name: self._escape_field(event, endpoint),
            )
            fixed.Bind(
                wx.EVT_CHECKBOX,
                lambda event, endpoint=name: self._toggle_mode(event, endpoint),
            )
            plot_row.Add(field, 1, wx.RIGHT, 3)
            plot_row.Add(fixed, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            self.endpoint_fields[name], self.endpoint_fixed[name] = field, fixed
            self.endpoint_labels[name] = endpoint_label
        self.all_oem = wx.Button(self, label="All OEM data")
        self.all_oem.SetName("Show all OEM data in plots")
        self.all_oem.Bind(wx.EVT_BUTTON, self._reset_plot)
        plot_row.Add(self.all_oem, 0)
        outer.Add(plot_row, 0, wx.EXPAND | wx.ALL, 3)

        self.message = wx.StaticText(self, label="")
        self.message.SetForegroundColour(wx.Colour(190, 35, 35))
        outer.Add(self.message, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        self.SetSizer(outer)
        self._sync()

    def _field(self, name: str) -> wx.TextCtrl:
        field = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        field.SetName(name)
        field.SetMinSize(wx.Size(205, -1))
        return field

    def set_state(
        self, playback: tuple[float, float], plot_rule: time_range.PlotTimeRange
    ) -> None:
        self.playback, self.plot_rule = playback, plot_rule
        self._sync()

    def _sync(self) -> None:
        self._syncing = True
        try:
            self.plot_enabled.SetValue(self.plot_rule.enabled)
            for name in ("start", "end"):
                endpoint = getattr(self.plot_rule, name)
                self.endpoint_fixed[name].SetValue(endpoint.mode == "fixed")
                value = (
                    _timestamp(endpoint.value_s)
                    if endpoint.mode == "fixed"
                    else f"{endpoint.value_s:+g}s"
                )
                if not self.endpoint_fields[name].HasFocus():
                    self.endpoint_fields[name].ChangeValue(value)
                self.endpoint_fields[name].Show(self.plot_rule.enabled)
                self.endpoint_fixed[name].Show(self.plot_rule.enabled)
                self.endpoint_labels[name].Show(self.plot_rule.enabled)
            self.Layout()
        finally:
            self._syncing = False

    def _submit_plot(
        self, event: wx.Event, name: str, focus_loss: bool = False
    ) -> None:
        if not self._syncing:
            try:
                endpoints = {
                    key: _parse_endpoint(
                        self.endpoint_fields[key].GetValue(),
                        self.endpoint_fixed[key].GetValue(),
                    )
                    for key in ("start", "end")
                }
                candidate = time_range.PlotTimeRange(
                    self.plot_enabled.GetValue(), endpoints["start"], endpoints["end"]
                )
                time_range.validate_plot_range(candidate)
                self._on_begin_edit()
                self._on_plot(candidate)
                self.message.SetLabel("")
            except (OverflowError, ValueError) as error:
                self.message.SetLabel(str(error))
        event.Skip()

    def _escape_field(self, event: wx.KeyEvent, name: str) -> None:
        if event.GetKeyCode() != wx.WXK_ESCAPE:
            event.Skip()
            return
        endpoint = getattr(self.plot_rule, name)
        field = self.endpoint_fields[name]
        field.ChangeValue(
            _timestamp(endpoint.value_s)
            if endpoint.mode == "fixed"
            else f"{endpoint.value_s:+g}s"
        )
        self.message.SetLabel("")

    def _toggle_mode(self, event: wx.CommandEvent, name: str) -> None:
        if self._syncing:
            return
        endpoint = getattr(self.plot_rule, name)
        absolute = endpoint.value_s + (
            self._now() if endpoint.mode == "offset" else 0.0
        )
        fixed = self.endpoint_fixed[name].GetValue()
        converted = (
            time_range.TimeRangeEndpoint("fixed", absolute)
            if fixed
            else time_range.TimeRangeEndpoint("offset", absolute - self._now())
        )
        candidate = time_range.PlotTimeRange(
            self.plot_enabled.GetValue(),
            converted if name == "start" else self.plot_rule.start,
            converted if name == "end" else self.plot_rule.end,
        )
        self.endpoint_fields[name].ChangeValue(
            _timestamp(absolute) if fixed else f"{converted.value_s:+g}s"
        )
        self._submit_plot(event, name)

    def _toggle_plot(self, event: wx.CommandEvent) -> None:
        enabled = self.plot_enabled.GetValue()
        if enabled:
            start, end = self.playback
            candidate = time_range.PlotTimeRange(
                True,
                time_range.TimeRangeEndpoint("fixed", start),
                time_range.TimeRangeEndpoint("fixed", end),
            )
        else:
            candidate = time_range.PlotTimeRange(
                False, self.plot_rule.start, self.plot_rule.end
            )
        try:
            self._on_begin_edit()
            self._on_plot(candidate)
            self.message.SetLabel("")
        except ValueError as error:
            self.message.SetLabel(str(error))
            self._sync()

    def _reset_plot(self, _event: wx.CommandEvent) -> None:
        self._on_begin_edit()
        self._on_plot(
            time_range.PlotTimeRange(False, self.plot_rule.start, self.plot_rule.end)
        )
