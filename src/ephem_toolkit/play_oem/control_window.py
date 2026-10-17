"""Initial Tk control window for OEM playback."""

from __future__ import annotations

from collections.abc import Callable
import math
import tkinter as tk

from .views.registry import GROUP_LABELS, ViewRegistry

# Classic buttons keep the readout visible with legacy Tk builds such as macOS Tk 8.5.
BACKGROUND_COLOR = "#f0f0f0"
FOREGROUND_COLOR = "#000000"
MINIMUM_WIDTH_PX = 320
TIMELINE_WIDTH_PX = 480
TIMELINE_HEIGHT_PX = 32
TIMELINE_LEFT_PX = 12
TIMELINE_RIGHT_PX = 468
TIMELINE_CENTER_Y = 16
SPEED_SCALE_WIDTH_PX = 320
SPEED_SCALE_HEIGHT_PX = 28
SPEED_SCALE_LEFT_PX = 12
SPEED_SCALE_RIGHT_PX = 308
SPEED_SCALE_CENTER_Y = 14
TIME_ENTRY_FIELD_HEIGHT_PX = 38
SPEED_PRESETS = (1.0, 10.0, 100.0, 1000.0)


class ControlWindow:
    """Display the current playback time and handle window-close requests."""

    def __init__(
        self,
        root: tk.Tk,
        on_close: Callable[[], None],
        on_open_view: Callable[[str], None],
        on_open_group: Callable[[str], None],
        view_registry: ViewRegistry,
        on_toggle_play: Callable[[], None],
        on_seek: Callable[[float], None],
        on_set_speed: Callable[[float], None],
        on_reverse: Callable[[], None],
        *,
        on_seek_to_time: Callable[[str], None],
        on_step_samples: Callable[[int], None],
        on_step_seconds: Callable[[float], None],
        on_jump_to_start: Callable[[], None],
        on_jump_to_end: Callable[[], None],
        timeline_enabled: bool,
    ) -> None:
        self.root = root
        self._on_seek = on_seek
        self._on_toggle_play = on_toggle_play
        self._on_set_speed = on_set_speed
        self._on_reverse = on_reverse
        self._on_seek_to_time = on_seek_to_time
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
            text="Speed: +1x",
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
        self._speed_10_button.pack(side="left", padx=(0, 4), pady=(0, 8))
        self._speed_100_button = tk.Button(
            playback_controls,
            text="100x",
            command=lambda: on_set_speed(100.0),
            highlightbackground=BACKGROUND_COLOR,
        )
        self._speed_100_button.pack(side="left", padx=(0, 4), pady=(0, 8))
        self._speed_1000_button = tk.Button(
            playback_controls,
            text="1000x",
            command=lambda: on_set_speed(1000.0),
            highlightbackground=BACKGROUND_COLOR,
        )
        self._speed_1000_button.pack(side="left", padx=(0, 4), pady=(0, 8))
        self._reverse_button = tk.Button(
            playback_controls,
            text="Reverse",
            command=on_reverse,
            highlightbackground=BACKGROUND_COLOR,
        )
        self._reverse_button.pack(side="left", padx=(0, 16), pady=(0, 8))
        time_entry_controls = tk.Frame(root, background=BACKGROUND_COLOR)
        time_entry_controls.pack(fill="x", padx=16, pady=(0, 4))
        self._time_entry_prompt = tk.Button(
            time_entry_controls,
            text="Seek to elapsed time or UTC:",
            anchor="w",
            height=1,
            state="normal",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground=FOREGROUND_COLOR,
        )
        self._time_entry_prompt.pack(fill="x", pady=(0, 4))
        time_entry_row = tk.Frame(time_entry_controls, background=BACKGROUND_COLOR)
        time_entry_row.pack(fill="x")
        # Aqua Tk 8.5.9 maps Entry but blends it into dark mode; mirror its text visibly.
        self._time_entry_editing = False
        self.time_entry = tk.Entry(time_entry_row, width=28, takefocus=False)
        self.time_entry.place(x=0, y=0, width=1, height=1)
        self.time_entry.bind("<Return>", self._submit_time_entry)
        self.time_entry.bind("<KeyRelease>", self._refresh_time_entry_display)
        self.time_entry.bind("<FocusOut>", self._on_time_entry_focus_out)
        self._time_entry_image = self._create_time_entry_image(SPEED_SCALE_WIDTH_PX)
        time_entry_row.configure(height=TIME_ENTRY_FIELD_HEIGHT_PX)
        time_entry_row.grid_propagate(False)
        self._time_entry_display_button = tk.Button(
            time_entry_row,
            text="Click to enter elapsed time or UTC",
            image=self._time_entry_image,
            compound="center",
            anchor="w",
            justify="left",
            padx=10,
            pady=0,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground="#ffffff",
            command=self._focus_time_entry,
        )
        time_entry_row.grid_columnconfigure(0, weight=1)
        self._time_entry_display_button.grid(row=0, column=0, sticky="ew")
        self._time_entry_display_button.bind(
            "<Configure>", self._resize_time_entry_display
        )
        self._seek_time_button = tk.Button(
            time_entry_row,
            text="Seek",
            command=self._submit_time_entry,
            highlightbackground=BACKGROUND_COLOR,
        )
        self._seek_time_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self._time_error_label = tk.Button(
            root,
            text="",
            anchor="w",
            height=1,
            state="normal",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground="#a00000",
        )
        self._time_error_label.pack(fill="x", padx=16, pady=(0, 4))
        navigation_controls = tk.Frame(root, background=BACKGROUND_COLOR)
        navigation_controls.pack(fill="x", padx=16, pady=(0, 8))
        self._navigation_buttons = (
            tk.Button(
                navigation_controls,
                text="Start",
                command=on_jump_to_start,
                highlightbackground=BACKGROUND_COLOR,
            ),
            tk.Button(
                navigation_controls,
                text="Previous sample",
                command=lambda: on_step_samples(-1),
                highlightbackground=BACKGROUND_COLOR,
            ),
            tk.Button(
                navigation_controls,
                text="-1 min",
                command=lambda: on_step_seconds(-60.0),
                highlightbackground=BACKGROUND_COLOR,
            ),
            tk.Button(
                navigation_controls,
                text="+1 min",
                command=lambda: on_step_seconds(60.0),
                highlightbackground=BACKGROUND_COLOR,
            ),
            tk.Button(
                navigation_controls,
                text="Next sample",
                command=lambda: on_step_samples(1),
                highlightbackground=BACKGROUND_COLOR,
            ),
            tk.Button(
                navigation_controls,
                text="End",
                command=on_jump_to_end,
                highlightbackground=BACKGROUND_COLOR,
            ),
        )
        for button in self._navigation_buttons:
            button.pack(side="left", padx=(0, 4))
        self._speed_scale_caption = tk.Button(
            root,
            text="Playback speed (log scale, 1x to 1000x)",
            anchor="w",
            height=1,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
            foreground=FOREGROUND_COLOR,
        )
        self._speed_scale_caption.pack(fill="x", padx=16, pady=(0, 0))
        self._speed_scale_base_image = tk.PhotoImage(
            master=root,
            width=SPEED_SCALE_WIDTH_PX,
            height=SPEED_SCALE_HEIGHT_PX,
        )
        self._speed_scale_base_image.put(
            BACKGROUND_COLOR,
            to=(0, 0, SPEED_SCALE_WIDTH_PX, SPEED_SCALE_HEIGHT_PX),
        )
        self._speed_scale_base_image.put(
            "#8b8b8b",
            to=(
                SPEED_SCALE_LEFT_PX,
                SPEED_SCALE_CENTER_Y - 2,
                SPEED_SCALE_RIGHT_PX + 1,
                SPEED_SCALE_CENTER_Y + 2,
            ),
        )
        for preset in SPEED_PRESETS:
            progress = math.log10(preset) / 3.0
            tick_x = round(
                SPEED_SCALE_LEFT_PX
                + progress * (SPEED_SCALE_RIGHT_PX - SPEED_SCALE_LEFT_PX)
            )
            self._speed_scale_base_image.put(
                "#4b4b4b",
                to=(
                    tick_x - 1,
                    SPEED_SCALE_CENTER_Y - 5,
                    tick_x + 2,
                    SPEED_SCALE_CENTER_Y + 6,
                ),
            )
        self._speed_scale_image = tk.PhotoImage(
            master=root,
            width=SPEED_SCALE_WIDTH_PX,
            height=SPEED_SCALE_HEIGHT_PX,
        )
        self._speed_scale_button = tk.Button(
            root,
            image=self._speed_scale_image,
            anchor="w",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            takefocus=False,
            background=BACKGROUND_COLOR,
        )
        self._speed_scale_button.pack(fill="x", padx=16, pady=(0, 8))
        self._speed_scale_button.bind("<Button-1>", self._on_speed_scale)
        self._speed_scale_button.bind("<B1-Motion>", self._on_speed_scale)
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
        group_toolbar = tk.Frame(root, background=BACKGROUND_COLOR)
        group_toolbar.pack(fill="x", padx=16, pady=(0, 4))
        self._view_group_buttons: dict[str, tk.Button] = {}
        for name, label in GROUP_LABELS:
            button = tk.Button(
                group_toolbar,
                text=label,
                command=lambda group=name: on_open_group(group),
                state="normal" if view_registry.can_open(name) else "disabled",
                highlightbackground=BACKGROUND_COLOR,
            )
            button.pack(side="left", padx=(0, 4))
            self._view_group_buttons[name] = button
        self._open_overview_button = self._view_group_buttons["overview"]

        view_toolbar = tk.Frame(root, background=BACKGROUND_COLOR)
        view_toolbar.pack(fill="x", padx=16, pady=(0, 16))
        self._view_buttons: dict[str, tk.Button] = {}
        for name in view_registry.registered_views:
            button = tk.Button(
                view_toolbar,
                text=view_registry.label_for(name),
                command=lambda view=name: on_open_view(view),
                highlightbackground=BACKGROUND_COLOR,
            )
            button.pack(side="left", padx=(0, 4))
            self._view_buttons[name] = button
        self._view_toolbar_buttons = (
            *self._view_group_buttons.values(),
            *self._view_buttons.values(),
        )
        for button in (
            self._elapsed_label,
            self._utc_label,
            self._play_pause_button,
            self._speed_label,
            self._speed_1_button,
            self._speed_10_button,
            self._speed_100_button,
            self._speed_1000_button,
            self._reverse_button,
            self._seek_time_button,
            *self._navigation_buttons,
            self._speed_scale_caption,
            self._speed_scale_button,
            self._timeline_button,
            *self._view_toolbar_buttons,
        ):
            button.bind("<space>", self._on_space)
            button.bind("<KeyRelease-space>", self._on_space_release)
        self._render_speed_scale(1.0)
        self._render_timeline(0.0)
        self.root.protocol("WM_DELETE_WINDOW", on_close)

    def update_time(self, text: str) -> None:
        """Update the visible elapsed-time and UTC readout."""
        elapsed_text, separator, utc_text = text.partition("\n")
        self._elapsed_label.configure(text=elapsed_text)
        self._utc_label.configure(text=utc_text if separator else "")

    def show_time_error(self, message: str) -> None:
        """Display a time-entry error without changing the playback clock."""
        self._time_error_label.configure(text=message)

    def clear_time_error(self) -> None:
        """Clear a previously displayed time-entry error."""
        self._time_error_label.configure(text="")

    def _create_time_entry_image(self, width: int) -> tk.PhotoImage:
        height = TIME_ENTRY_FIELD_HEIGHT_PX
        image = tk.PhotoImage(master=self.root, width=width, height=height)
        image.put("#8b8b8b", to=(0, 0, width, height))
        if width > 4 and height > 4:
            image.put("#292929", to=(2, 2, width - 2, height - 2))
        return image

    def _resize_time_entry_display(self, event: tk.Event) -> None:
        width = max(1, event.width)
        if self._time_entry_image.width() == width:
            return
        self._time_entry_image = self._create_time_entry_image(width)
        self._time_entry_display_button.configure(image=self._time_entry_image)

    def _focus_time_entry(self) -> None:
        self._time_entry_editing = True
        self.time_entry.focus_force()
        self.time_entry.icursor("end")
        self._refresh_time_entry_display()

    def _on_time_entry_focus_out(self, _event: tk.Event) -> None:
        self._time_entry_editing = False
        self._refresh_time_entry_display()

    def _refresh_time_entry_display(self, _event: tk.Event | None = None) -> None:
        text = self.time_entry.get()
        if not text and not self._time_entry_editing:
            text = "Click to enter elapsed time or UTC"
        self._time_entry_display_button.configure(text=text)

    def update_playback_state(
        self, text: str, progress: float, playing: bool, rate: float
    ) -> None:
        """Refresh readouts and controls without seeking from the programmatic slider update."""
        self.update_time(text)
        self._play_pause_button.configure(text="Pause" if playing else "Play")
        self._speed_label.configure(text=f"Speed: {rate:+g}x")
        for button, preset in zip(
            (
                self._speed_1_button,
                self._speed_10_button,
                self._speed_100_button,
                self._speed_1000_button,
            ),
            SPEED_PRESETS,
        ):
            button.configure(
                relief="sunken" if math.isclose(abs(rate), preset) else "raised"
            )
        self._reverse_button.configure(relief="sunken" if rate < 0.0 else "raised")
        self._render_speed_scale(abs(rate))
        self._render_timeline(progress)

    def _render_speed_scale(self, speed: float) -> None:
        progress = math.log10(min(max(speed, 1.0), 1000.0)) / 3.0
        cursor_x = round(
            SPEED_SCALE_LEFT_PX
            + progress * (SPEED_SCALE_RIGHT_PX - SPEED_SCALE_LEFT_PX)
        )
        self._speed_scale_image.tk.call(
            str(self._speed_scale_image),
            "copy",
            str(self._speed_scale_base_image),
        )
        self._speed_scale_image.put(
            "#2878c8",
            to=(
                SPEED_SCALE_LEFT_PX,
                SPEED_SCALE_CENTER_Y - 1,
                cursor_x + 1,
                SPEED_SCALE_CENTER_Y + 2,
            ),
        )
        self._speed_scale_image.put(
            "#303030",
            to=(
                cursor_x - 6,
                SPEED_SCALE_CENTER_Y - 8,
                cursor_x + 7,
                SPEED_SCALE_CENTER_Y + 9,
            ),
        )
        self._speed_scale_image.put(
            "#f8f8f8",
            to=(
                cursor_x - 4,
                SPEED_SCALE_CENTER_Y - 6,
                cursor_x + 5,
                SPEED_SCALE_CENTER_Y + 7,
            ),
        )

    def _on_speed_scale(self, event: tk.Event) -> None:
        progress = min(
            max(
                (event.x - SPEED_SCALE_LEFT_PX)
                / (SPEED_SCALE_RIGHT_PX - SPEED_SCALE_LEFT_PX),
                0.0,
            ),
            1.0,
        )
        speed = 10.0 ** (progress * 3.0)
        self._on_set_speed(speed)

    def _submit_time_entry(self, _event: tk.Event | None = None) -> str:
        self._on_seek_to_time(self.time_entry.get())
        return "break"

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
