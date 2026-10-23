"""Compact native GTK controls without clipping their themed contents."""

from __future__ import annotations

import ctypes
from functools import lru_cache

import wx


@lru_cache(maxsize=1)
def _gtk_style() -> tuple[ctypes.CDLL, int]:
    gtk = ctypes.CDLL("libgtk-3.so.0")
    pointer = ctypes.c_void_p
    signatures = (
        ("gtk_css_provider_new", [], pointer),
        (
            "gtk_css_provider_load_from_data",
            [pointer, ctypes.c_char_p, ctypes.c_ssize_t, pointer],
            ctypes.c_int,
        ),
        ("gtk_widget_get_screen", [pointer], pointer),
        ("gtk_widget_get_style_context", [pointer], pointer),
        (
            "gtk_style_context_add_provider_for_screen",
            [pointer, pointer, ctypes.c_uint],
            None,
        ),
        ("gtk_style_context_add_class", [pointer, ctypes.c_char_p], None),
    )
    for name, arguments, result in signatures:
        function = getattr(gtk, name)
        function.argtypes = arguments
        function.restype = result
    provider = gtk.gtk_css_provider_new()
    gtk.gtk_css_provider_load_from_data(
        provider,
        b".ephem-ground-track-compact, .ephem-ground-track-compact * "
        b"{ min-height: 20px; min-width: 0; padding: 0 4px; }",
        -1,
        None,
    )
    # Keep the provider alive with the cached library for all Ground Track views.
    return gtk, provider


def compact_controls(controls: tuple[wx.Window, ...]) -> None:
    """Reduce GTK padding only for these controls, leaving other views alone."""
    if "gtk3" not in wx.PlatformInfo or not controls:
        return
    gtk, provider = _gtk_style()
    screen = gtk.gtk_widget_get_screen(int(controls[0].GetGtkWidget()))
    gtk.gtk_style_context_add_provider_for_screen(screen, provider, 600)
    for control in controls:
        context = gtk.gtk_widget_get_style_context(int(control.GetGtkWidget()))
        gtk.gtk_style_context_add_class(context, b"ephem-ground-track-compact")
        control.InvalidateBestSize()
        if isinstance(control, wx.Choice):
            # wx caches the default combo height despite the smaller GTK padding.
            control.SetMinSize(wx.Size(-1, control.FromDIP(24)))
