# `play-oem` User Configuration

`play-oem` reads a user config file for display and playback defaults, and an app-maintained state
file for window size, recent files, and open graph views. Both files use plain-text TOML and live
in the same XDG-style config directory. You can edit the user config file with any text editor;
the state file is maintained by the application.

## File location

`play-oem` uses the same XDG-style location on Linux and macOS:

```text
$XDG_CONFIG_HOME/ephem-toolkit/play-oem.toml
```

If `XDG_CONFIG_HOME` is not set, or is empty, the default will be:

```text
~/.config/ephem-toolkit/play-oem.toml
```

The application-maintained state file lives beside it:

```text
$XDG_CONFIG_HOME/ephem-toolkit/play-oem-state.toml
```

When `XDG_CONFIG_HOME` is unset or empty, its default path is:

```text
~/.config/ephem-toolkit/play-oem-state.toml
```

For example, if your home directory is `/home/alex`, the default user config file is:

```text
/home/alex/.config/ephem-toolkit/play-oem.toml
```

You can choose a different XDG config directory by setting `XDG_CONFIG_HOME` before starting
`play-oem`. It must be an absolute path. If it is relative, `play-oem` will use the default
under `~/.config` instead. The application uses built-in defaults when these files are absent.
It creates `play-oem.toml` when a setting is saved or when legacy station definitions are migrated.

## User config file

The file structure is:

```toml
config_version = 1

[playback]
speed = 1.0
reverse = false
render_rate_fps = 30

[display]
three_d_backend = "auto"
plots = ["overview"]

[interpolation]
use_oem_metadata = false
method = "hermite"
degree = 5

[ground_stations]
stations = [
  { id = "station-uuid", name = "North Site", latitude_deg = 64.1, longitude_deg = -21.9, altitude_m = 45.0, minimum_elevation_deg = 10 },
]
```

You can leave out settings you do not want to customize. Unspecified settings will use their
normal defaults. The `config_version` field identifies the config format for future updates;
leave it at `1` unless a later version of this guide says otherwise.

## Saved application state

`play-oem-state.toml` is maintained by the application. It stores changeable workspace details
separately from your user-edited defaults. You normally do not need to edit it.

```toml
state_version = 8

[window]
width = 1400
height = 900
maximized = false
position = [120, 80]

[recent_files]
paths = [
    "/home/alex/orbits/iss.oem",
    "/home/alex/orbits/transfer.oem",
]

[recent_files.settings]
"/home/alex/orbits/iss.oem" = { playback_range = [806400000.0, 806400600.0], plot_range = { enabled = true, start = { mode = "follow", value_s = 0.0 }, end = { mode = "offset", value_s = 300.0 } } }
"/home/alex/orbits/transfer.oem" = { playback_range = [806400120.0, 806400480.0] }

[workspace]
open_plots = ["trajectory-3d", "speed-altitude"]

[ground_track]
minimum_elevation_deg = 10
```

Ground station definitions are stored in the user config file, not the state file. Station
definitions in legacy state files are migrated to `play-oem.toml` when no `[ground_stations]`
section is present there.

The state file remembers the main window size and position, and up to 15 recently opened OEM files. The
most recently opened file appears first. A file is added after it loads successfully; opening it
again moves it to the top without creating a duplicate. Paths are stored as absolute paths, so
the recent-file list works regardless of the directory from which you launch `play-oem`.
Unavailable paths remain in the list in case a removable drive or mounted directory becomes
available again. Choose a path from **File → Open Recent** to reopen it.
The `recent_files.settings` table associates per-file settings with those absolute paths. The
playback range is saved as two absolute TT timestamps when a file is replaced or the application
exits, and is restored when that file is opened again. If the saved range no longer fits the
file's coverage, the application reports a warning and uses the full coverage instead. The plot
range rule is also saved and restored per file, including whether filtering is enabled and each
endpoint's mode and value. Follow endpoints track their corresponding playback bound, offset
values are seconds from current playback time, and fixed values are absolute TT timestamps.
This path-keyed table can hold additional per-file settings in future versions.

The state file also remembers the graph views open when you exit. On the next launch, those
views are restored unless you provide `--plots` or set `display.plots` in `play-oem.toml`.
The saved values are view names such as `trajectory-3d` and `speed-altitude`; plot groups are
expanded to their individual views when saved.
When you change the Settings pane's render rate, the selected render rate FPS is saved as
`playback.render_rate_fps` in `play-oem.toml` when the application exits. The app updates only
that setting, preserving the other user-config values. The legacy `playback.fps` key is still
accepted and is rewritten as `playback.render_rate_fps` when the selected rate is saved. Render
rate is no longer stored in the state file. The Settings pane's interpolation source, method, and
degree are also saved in `play-oem.toml` when the application exits. The Ground Track
minimum-elevation setting is saved here too.

The window size is adjusted if it does not fit the current display. The saved window position is
clamped to a connected display's work area if necessary, so a monitor change will not leave the
window off-screen. Position is saved only while the window is not maximized. If the state file is
missing or invalid, `play-oem` will use safe defaults and continue; it will report a warning for
invalid state. It will update the state file separately and will not save one-time command-line
overrides into `play-oem.toml`.

## Settings

### Playback

| Setting | Description |
|---|---|
| `speed` | Initial playback speed multiplier, from 1x through 9000x. Playback speed is currently controlled in the GUI. |
| `reverse` | Initial direction preference for the GUI. |
| `render_rate_fps` | Initial render-rate preference from 1 through 30 frames per second. The Settings pane slider's current value is saved in `play-oem.toml` at exit. The legacy `fps` key is also accepted. |

### Display

| Setting | Description |
|---|---|
| `three_d_backend` | 3D renderer: `"auto"`, `"vtk"`, or `"matplotlib"`. `"auto"` selects an available supported backend. |
| `plots` | Views or view groups to open at launch. This uses the same names and groups as `--plots`; for example, `["overview"]` or `["state", "motion"]`. |

### Interpolation

| Setting | Description |
|---|---|
| `use_oem_metadata` | When `true`, use the interpolation type and degree declared by the OEM file. The default is `false`, which uses `method` and `degree`. |
| `method` | Interpolator to use when `use_oem_metadata = false`: `"hermite"` (default), `"lagrange"`, or `"chebyshev"`. |
| `degree` | Non-negative interpolation degree to use when `use_oem_metadata = false`. The default is `5`, the default Hermite degree. |

These interpolation options are also available in the Settings pane. **Use settings below** is the
default and applies the selected method and degree immediately to the playback cursor. **Follow
OEM metadata** uses the current file's interpolation metadata. Changes are saved when the
application exits. The panel also displays the active method, degree, and source; if OEM
interpolation metadata is absent, it reports the linear fallback.

The input file is selected for an individual run. `play-oem` loads the full OEM file and chooses
the time-axis unit automatically: minutes for OEM spans shorter than one hour, and hours for spans
of one hour or more. Seek to a desired time in the GUI.

## Command-line options

`play-oem --config PATH` selects a specific user config TOML file instead of the default location.
It does not change the location of the app-maintained state file. An explicitly selected config
file that is missing or cannot be read produces an error. A missing config file at the default
location is treated as no user configuration.

For settings that have a corresponding command-line option, an explicitly supplied value will take
precedence over the config file, and the config file will take precedence over the built-in
default. Playback speed, direction, and FPS initialize GUI controls. Command-line overrides will
apply only to that run and will not be saved back to the file.

Malformed TOML, unknown setting names, and invalid values will be reported with an error that
identifies the config file and setting where possible.

## Related documentation

- [Configuration implementation report](../architecture/play-oem/old/PLAY_OEM_CONFIG_REPORT.md)
- [`play-oem` concepts and command-line options](../architecture/play-oem/PLAY_OEM_CONCEPTS.md)
