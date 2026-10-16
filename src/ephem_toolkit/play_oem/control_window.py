"""Initial Tk control window for OEM playback."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

# Classic buttons keep the readout visible with legacy Tk builds such as macOS Tk 8.5.
BACKGROUND_COLOR = "#f0f0f0"
FOREGROUND_COLOR = "#000000"
MINIMUM_WIDTH_PX = 320
TIMELINE_WIDTH_PX = 480
TIMELINE_HEIGHT_PX = 32
TIMELINE_LEFT_PX = 12
TIMELINE_RIGHT_PX = 468
TIMELINE_CENTER_Y = 16


class ControlWindow:
    """Display the current playback time and handle window-close requests."""

    def __init__(
        self,
        root: tk.Tk,
        on_close: Callable[[], None],
        on_open_overview: Callable[[], None],
        on_toggle_play: Callable[[], None],
        on_seek: Callable[[float], None],
        on_set_speed: Callable[[float], None],
        *,
        timeline_enabled: bool,
    ) -> None:
        self.root = root
        self._on_seek = on_seek
        self._on_toggle_play = on_toggle_play
        self._space_pressed = False
        self._timeline_enabled = timeline_enabled
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
        playback_controls = tk.Frame(root, background=BACKGROUND_COLOR)
        playback_controls.pack(fill="x")
        self._play_pause_button = tk.Button(
            playback_controls,
            text="Play",
            command=on_toggle_play,
            highlightbackground=BACKGROUND_COLOR,
        )
        self._play_pause_button.pack(side="left", padx=(16, 8), pady=(0, 8))
        self._speed_label = tk.Button(
            playback_controls,
            text="Speed: 1x",
            state="normal",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground=FOREGROUND_COLOR,
        )
        self._speed_label.pack(side="left", padx=(0, 8), pady=(0, 8))
        self._speed_1_button = tk.Button(
            playback_controls,
            text="1x",
            command=lambda: on_set_speed(1.0),
            highlightbackground=BACKGROUND_COLOR,
        )
        self._speed_1_button.pack(side="left", padx=(0, 4), pady=(0, 8))
        self._speed_10_button = tk.Button(
            playback_controls,
            text="10x",
            command=lambda: on_set_speed(10.0),
            highlightbackground=BACKGROUND_COLOR,
        )
        self._speed_10_button.pack(side="left", padx=(0, 16), pady=(0, 8))
        self._timeline_base_image = tk.PhotoImage(
            master=root,
            width=TIMELINE_WIDTH_PX,
            height=TIMELINE_HEIGHT_PX,
        )
        self._timeline_base_image.put(
            BACKGROUND_COLOR,
            to=(0, 0, TIMELINE_WIDTH_PX, TIMELINE_HEIGHT_PX),
        )
        self._timeline_base_image.put(
            "#8b8b8b",
            to=(
                TIMELINE_LEFT_PX,
                TIMELINE_CENTER_Y - 2,
                TIMELINE_RIGHT_PX + 1,
                TIMELINE_CENTER_Y + 2,
            ),
        )
        self._timeline_image = tk.PhotoImage(
            master=root,
            width=TIMELINE_WIDTH_PX,
            height=TIMELINE_HEIGHT_PX,
        )
        self._timeline_button = tk.Button(
            root,
            image=self._timeline_image,
            anchor="w",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            state="normal" if timeline_enabled else "disabled",
        )
        self._timeline_button.pack(fill="x", padx=16, pady=(0, 8))
        self._timeline_button.bind("<Button-1>", self._on_timeline_seek)
        self._timeline_button.bind("<B1-Motion>", self._on_timeline_seek)
        self._open_overview_button = tk.Button(
            root,
            text="Open Overview",
            command=on_open_overview,
            highlightbackground=BACKGROUND_COLOR,
        )
        self._open_overview_button.pack(fill="x", padx=16, pady=(0, 16))
        for button in (
            self._elapsed_label,
            self._utc_label,
            self._play_pause_button,
            self._speed_label,
            self._speed_1_button,
            self._speed_10_button,
            self._timeline_button,
            self._open_overview_button,
        ):
            button.bind("<space>", self._on_space)
            button.bind("<KeyRelease-space>", self._on_space_release)
        self._render_timeline(0.0)
        self.root.protocol("WM_DELETE_WINDOW", on_close)

    def update_time(self, text: str) -> None:
        """Update the visible elapsed-time and UTC readout."""
        elapsed_text, separator, utc_text = text.partition("\n")
        self._elapsed_label.configure(text=elapsed_text)
        self._utc_label.configure(text=utc_text if separator else "")

    def update_playback_state(
        self, text: str, progress: float, playing: bool, rate: float
    ) -> None:
        """Refresh readouts and controls without seeking from the programmatic slider update."""
        self.update_time(text)
        self._play_pause_button.configure(text="Pause" if playing else "Play")
        self._speed_label.configure(text=f"Speed: {abs(rate):g}x")
        self._speed_1_button.configure(
            relief="sunken" if abs(rate) == 1.0 else "raised"
        )
        self._speed_10_button.configure(
            relief="sunken" if abs(rate) == 10.0 else "raised"
        )
        self._render_timeline(progress)

    def _render_timeline(self, progress: float) -> None:
        progress = min(max(progress, 0.0), 1.0)
        cursor_x = round(
            TIMELINE_LEFT_PX + progress * (TIMELINE_RIGHT_PX - TIMELINE_LEFT_PX)
        )
        self._timeline_image.tk.call(
            str(self._timeline_image), "copy", str(self._timeline_base_image)
        )
        self._timeline_image.put(
            "#2878c8",
            to=(
                TIMELINE_LEFT_PX,
                TIMELINE_CENTER_Y - 1,
                cursor_x + 1,
                TIMELINE_CENTER_Y + 1,
            ),
        )
        self._timeline_image.put(
            "#303030",
            to=(
                cursor_x - 6,
                TIMELINE_CENTER_Y - 9,
                cursor_x + 7,
                TIMELINE_CENTER_Y + 10,
            ),
        )
        self._timeline_image.put(
            "#f8f8f8",
            to=(
                cursor_x - 4,
                TIMELINE_CENTER_Y - 7,
                cursor_x + 5,
                TIMELINE_CENTER_Y + 8,
            ),
        )
        self._timeline_image.put(
            "#4b4b4b",
            to=(
                cursor_x - 1,
                TIMELINE_CENTER_Y - 6,
                cursor_x + 2,
                TIMELINE_CENTER_Y + 7,
            ),
        )

    def _on_timeline_seek(self, event: tk.Event) -> None:
        if not self._timeline_enabled:
            return
        progress = min(
            max(
                (event.x - TIMELINE_LEFT_PX) / (TIMELINE_RIGHT_PX - TIMELINE_LEFT_PX),
                0.0,
            ),
            1.0,
        )
        self._on_seek(progress)

    def _on_space(self, _event: tk.Event) -> str:
        if not self._space_pressed:
            self._space_pressed = True
            self._on_toggle_play()
        return "break"

    def _on_space_release(self, _event: tk.Event) -> str:
        self._space_pressed = False
        return "break"

    def _on_timeline_click(self, event: tk.Event) -> str | None:
        if self._timeline.identify(event.x, event.y) == "slider":
            return None
        first_x = self._timeline.coords(0.0)[0]
        last_x = self._timeline.coords(1.0)[0]
        if first_x == last_x:
            return "break"
        progress = min(max((event.x - first_x) / (last_x - first_x), 0.0), 1.0)
        self._on_seek(progress)
        return "break"
