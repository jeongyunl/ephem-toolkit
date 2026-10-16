"""Initial Tk control window for OEM playback."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk


class ControlWindow:
    """Display the current playback time and handle window-close requests."""

    def __init__(self, root: tk.Tk, on_close: Callable[[], None]) -> None:
        self.root = root
        self.root.title("play-oem")
        self._time_label = ttk.Label(root, text="", justify="left", anchor="w")
        self._time_label.pack(fill="x", padx=16, pady=16)
        self.root.protocol("WM_DELETE_WINDOW", on_close)

    def update_time(self, text: str) -> None:
        """Update the visible elapsed-time and UTC readout."""
        self._time_label.configure(text=text)
