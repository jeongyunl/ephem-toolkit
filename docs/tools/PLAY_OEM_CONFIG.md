# `play-oem` User Configuration

> **Status: Planned.** This page describes the proposed config and state files. Until configuration
> loading is implemented, `play-oem` does not read these files. Choose playback speed, direction,
> and render rate in the GUI; use command-line options for file, display units, views, and backend.

The user config file will let you choose defaults for `play-oem`, so you do not need to repeat
the same display preferences and playback defaults each time you launch it. It will be plain-text
TOML and can be edited with any text editor.

## File location

`play-oem` will use the same XDG-style location on Linux and macOS:

```text
$XDG_CONFIG_HOME/ephem-toolkit/play-oem.toml
```

If `XDG_CONFIG_HOME` is not set, or is empty, the default will be:

```text
~/.config/ephem-toolkit/play-oem.toml
```

The application-maintained state file will live beside it:

```text
$XDG_CONFIG_HOME/ephem-toolkit/play-oem-state.toml
```

When `XDG_CONFIG_HOME` is unset or empty, its default path will be:

```text
~/.config/ephem-toolkit/play-oem-state.toml
```

For example, if your home directory is `/home/alex`, the default user config file is:

```text
/home/alex/.config/ephem-toolkit/play-oem.toml
```

You can choose a different XDG config directory by setting `XDG_CONFIG_HOME` before starting
`play-oem`. It must be an absolute path. If it is relative, `play-oem` will use the default
under `~/.config` instead. The application will not create either file just by starting; it will
use built-in defaults and initial window settings when the files are absent.

## Example file

The proposed file structure is:

```toml
config_version = 1

[playback]
speed = 1.0
reverse = false
fps = 30

[display]
three_d_backend = "auto"
plots = ["overview"]
```

You can leave out settings you do not want to customize. Unspecified settings will use their
normal defaults. The `config_version` field identifies the config format for future updates;
leave it at `1` unless a later version of this guide says otherwise.

## Saved application state

`play-oem-state.toml` is maintained by the application. It stores changeable workspace details
separately from your user-edited defaults. You normally do not need to edit it.

```toml
state_version = 1

[window]
width = 1400
height = 900
maximized = false

[recent_files]
paths = [
    "/home/alex/orbits/iss.oem",
    "/home/alex/orbits/transfer.oem",
]
```

The state file will remember the main window size and up to 15 recently opened OEM files. The
most recently opened file appears first. A file is added after it loads successfully; opening it
again moves it to the top without creating a duplicate. Paths are stored as absolute paths, so
the recent-file list works regardless of the directory from which you launch `play-oem`.
Unavailable paths remain in the list in case a removable drive or mounted directory becomes
available again.

The window size will be adjusted if it does not fit the current display. Window position is not
saved initially, so changing monitors will not leave the window off-screen. If the state file is
missing or invalid, `play-oem` will use safe defaults and continue; it will report a warning for
invalid state. It will update the state file separately and will not save one-time command-line
overrides into `play-oem.toml`.

## Settings

### Playback

| Setting | Description |
|---|---|
| `speed` | Initial playback speed multiplier, from 1x through 9000x. Playback speed is currently controlled in the GUI. |
| `reverse` | Initial direction preference for the GUI. |
| `fps` | Initial render-rate preference from 1 through 30 frames per second. The Playback pane slider currently controls this value. |

### Display

| Setting | Description |
|---|---|
| `three_d_backend` | 3D renderer: `"auto"`, `"vtk"`, or `"matplotlib"`. `"auto"` selects an available supported backend. |
| `plots` | Views or view groups to open at launch. This uses the same names and groups as `--plots`; for example, `["overview"]` or `["state", "motion"]`. |

The input file is selected for an individual run. `play-oem` loads the full OEM file and chooses
the time-axis unit automatically: minutes for OEM spans shorter than one hour, and hours for spans
of one hour or more. Seek to a desired time in the GUI.

## Command-line options

When implemented, `play-oem --config PATH` will select a specific user config TOML file instead
of the default location. It will not change the location of the app-maintained state file. An
explicitly selected config file that is missing or cannot be read will produce an error. A
missing config file at the default location will be treated as no user configuration.

For settings that have a corresponding command-line option, an explicitly supplied value will take
precedence over the config file, and the config file will take precedence over the built-in
default. Playback speed, direction, and FPS initialize GUI controls. Command-line overrides will
apply only to that run and will not be saved back to the file.

Malformed TOML, unknown setting names, and invalid values will be reported with an error that
identifies the config file and setting where possible.

## Related documentation

- [Configuration development plan](../architecture/play-oem/PLAY_OEM_CONFIG_PLAN.md)
- [`play-oem` concepts and command-line options](../architecture/play-oem/PLAY_OEM_CONCEPTS.md)
