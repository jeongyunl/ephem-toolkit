"""Initial Tk control window for OEM playback."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

# Classic buttons keep the readout visible with legacy Tk builds such as macOS Tk 8.5.
BACKGROUND_COLOR = "#f0f0f0"
FOREGROUND_COLOR = "#000000"
MINIMUM_WIDTH_PX = 320


class ControlWindow:
    """Display the current playback time and handle window-close requests."""

    def __init__(
        self,
        root: tk.Tk,
        on_close: Callable[[], None],
        on_open_speed_altitude: Callable[[], None],
    ) -> None:
        self.root = root
        self.root.title("play-oem")
        self.root.configure(background=BACKGROUND_COLOR)
        self.root.minsize(MINIMUM_WIDTH_PX, 1)
        self._elapsed_label = tk.Button(
            root,
            text="",
            justify="left",
            anchor="w",
            width=38,
            height=1,
            state="normal",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground=FOREGROUND_COLOR,
        )
        self._elapsed_label.pack(fill="x", padx=16, pady=(12, 0))
        self._utc_label = tk.Button(
            root,
            text="",
            justify="left",
            anchor="w",
            width=38,
            height=1,
            state="normal",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground=FOREGROUND_COLOR,
        )
        self._utc_label.pack(fill="x", padx=16, pady=(0, 8))
        self._open_speed_altitude_button = tk.Button(
            root,
            text="Open Speed / Altitude",
            command=on_open_speed_altitude,
            highlightbackground=BACKGROUND_COLOR,
        )
        self._open_speed_altitude_button.pack(fill="x", padx=16, pady=(0, 16))
        self.root.protocol("WM_DELETE_WINDOW", on_close)

    def update_time(self, text: str) -> None:
        """Update the visible elapsed-time and UTC readout."""
        elapsed_text, separator, utc_text = text.partition("\n")
        self._elapsed_label.configure(text=elapsed_text)
        self._utc_label.configure(text=utc_text if separator else "")
