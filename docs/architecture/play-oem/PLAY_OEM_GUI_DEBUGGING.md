# Play-OEM GUI Debugging

This document records practical techniques for investigating Play-OEM GUI
behavior. Add future debugging recipes here as issues are investigated.

## Focus debugging

### Temporary focus tracing

The floating settings panel's focus issue was investigated with temporary
instrumentation in
`src/ephem_toolkit/play_oem/widgets/floating_settings_panel.py`. It logged
focus snapshots around expand/collapse and bound handlers for wx focus and
mouse-button events on the popup and its content controls. Each event log
included its wx event type, source window, `wx.Window.FindFocus()`, and panel
state; mouse logs also included client and screen positions.

That instrumentation was removed after the behavior was understood. The
following launch command configures logging but does not produce focus traces
unless temporary debug calls and event bindings have been added again:

```bash
PYTHONPATH=src .venv/bin/python -c '
import logging
from ephem_toolkit.play_oem.__main__ import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger(
    "ephem_toolkit.play_oem.widgets.floating_settings_panel"
).setLevel(logging.DEBUG)
main()
' 2>&1 | tee play-oem.trace
```

`tee` writes combined stdout and stderr to the terminal and `play-oem.trace`.
Append an OEM path after the closing quote and before `2>&1` to load it at
startup.

To reproduce the focus scenario after adding temporary instrumentation:

1. Open a view with a floating settings panel, such as Ground Track.
2. Hover over the handle to expand the panel, then move away to collapse it.
3. Repeat while clicking a control and blank space in the panel.
4. Inspect the trace with `rg "Settings panel" play-oem.trace`.

When instrumenting wx events, compare event types with `wx.EVT_SET_FOCUS`,
`wx.EVT_KILL_FOCUS`, and the corresponding mouse event constants rather than
assuming numeric event IDs are stable across wx versions. Log both the event
source and `FindFocus()`: composite controls can emit events from native child
windows, so the source alone may not identify the final focus target. Call
`event.Skip()` in diagnostic handlers to preserve normal event processing.

### Findings from the settings-panel investigation

- `wx.PopupWindow` is intended for transient menu- and combo-style popups. Its
  `wx.PU_CONTAINS_CONTROLS` option, which lets the popup take focus for its
  child controls, is implemented only on wxMSW and does nothing on macOS. In
  the tested macOS environment, programmatic focus therefore remained on the
  host instead of moving to a settings control, so `wx.PopupWindow` could not
  provide the required keyboard behavior.
- We replaced it with a borderless `wx.Frame` using
  `wx.FRAME_FLOAT_ON_PARENT`. This keeps the settings window layered over its
  owner without forcing it above unrelated windows, while allowing its
  contents to receive focus. See the wxPython
  [`wx.PopupWindow` documentation](https://docs.wxpython.org/wx.PopupWindow.html).
- Focusing the first eligible child selected an individual input (the
  Center longitude field). The intended behavior is to focus the
  `wx.ScrolledWindow` content host instead.
- The regression test checks that focus is on the content host after expansion
  and returns to the previous host window after collapse.

### Future debugging recipes

For each new GUI debugging example, record the symptom and minimal reproduction,
temporary instrumentation and launch setup, how to interpret the resulting
trace, and the permanent fix or regression test. Remove temporary logging and
event bindings when they are no longer needed; keep only intentional
application behavior and focused tests.
