"""Formatting helpers for read-only timestamp labels."""

from __future__ import annotations

import re

import wx

_FRACTION_SUFFIX = re.compile(r"\.(\d+)(Z|[+-]\d{2}:\d{2}|\s+s)?$")


def small_fraction_markup(text: str) -> str:
    """Wrap trailing fractional seconds in wx small-text markup."""
    match = _FRACTION_SUFFIX.search(text)
    if match is None:
        return text
    return (
        f"{text[:match.start()]}.<small>{match.group(1)}</small>"
        f"{match.group(2) or ''}"
    )


def set_small_fraction_label(control: wx.StaticText, text: str) -> None:
    """Set a read-only label with smaller fractional seconds when supported."""
    set_markup = getattr(control, "SetLabelMarkup", None)
    if set_markup is None or not set_markup(small_fraction_markup(text)):
        control.SetLabel(text)


def set_timestamp_label(control: wx.StaticText, text: str) -> None:
    """Set a read-only timestamp label with smaller fractional seconds."""
    set_small_fraction_label(control, text)
