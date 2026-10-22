# `play-oem` — Configuration Implementation Report

This report records the completed implementation of user configuration and saved application
state for `play-oem`. The feature uses TOML files in an XDG-style directory on Linux and macOS:
one user-edited file for recurring defaults and one application-maintained file for mutable UI
state. The [user guide](../../../tools/PLAY_OEM_CONFIG.md) describes the files and their
settings. See the [implementation plan](../PLAY_OEM_IMPLEMENTATION_PLAN.md) for the broader
`play-oem` development history.

## Objective and scope

The implementation lets users keep recurring playback and display defaults while preserving
workspace state between launches. Configuration parsing stays independent of wxPython, and
neither file is required for startup.

The work includes:

- TOML configuration and state files under a shared XDG-style directory.
- Validation, defaults, and explicit CLI precedence for supported settings.
- Window geometry, recent OEM files, and open graph views in application-maintained state.
- User documentation for file locations, structure, precedence, and recovery behavior.

## File locations and format

Both files use the same location on Linux and macOS:

```text
${XDG_CONFIG_HOME}/ephem-toolkit/play-oem.toml
${XDG_CONFIG_HOME}/ephem-toolkit/play-oem-state.toml
```

When `XDG_CONFIG_HOME` is unset, empty, or relative, the application uses:

```text
~/.config/ephem-toolkit/play-oem.toml
~/.config/ephem-toolkit/play-oem-state.toml
```

The files use versioned TOML schemas. The application does not create empty files at launch.
It creates the parent directory and state file only when saving state. `--config PATH` selects
the user-edited config file; the state file remains in the default XDG-style directory.

## User configuration

The user config file contains recurring playback and display preferences:

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

Playback speed, direction, and FPS initialize the GUI. The display values select the 3D backend
and initial graph views. Unknown keys, malformed TOML, and invalid values produce errors with
the config path and relevant setting when available. An absent default config uses built-in
defaults; an explicitly selected missing or unreadable file is an error.

For settings shared with command-line options, explicit CLI values take precedence over config
values, which take precedence over built-in defaults. CLI overrides are not written back to the
user config.

## Saved application state

The application-maintained `play-oem-state.toml` stores window size and maximized state, up to
15 recently opened OEM paths, and the open graph views. A representative file is:

```toml
state_version = 1

[window]
width = 1400
height = 900
maximized = false

[recent_files]
paths = ["/home/alex/orbits/iss.oem"]

[workspace]
open_plots = ["trajectory-3d", "speed-altitude"]
```

Recent files are absolute paths ordered most-recent-first. A path is recorded after a successful
load; opening it again moves it to the front. The Open OEM dialog starts in the directory of the
most recently opened file when one is available. Saved graph views are restored at launch unless
`--plots` or `display.plots` explicitly selects views. Empty saved view lists fall back to the
configured or built-in selection.

Window dimensions are clamped to the current display when restored. Window position is not
saved. Invalid state produces a warning and startup continues with safe defaults. State updates
are written atomically and do not modify the user config. Transient playback time and run-specific
CLI overrides are not persisted.

## Implementation

- `config.py` resolves the XDG-style directory and loads and validates user defaults without
  importing wxPython.
- `saved_state.py` loads, validates, and atomically writes application state. It also normalizes
  and caps the recent-file list.
- `__main__.py` merges CLI, user config, saved graph selection, and built-in defaults before
  constructing the GUI.
- `app/controller.py` restores and saves window and workspace state, maintains the recent-file
  menu, and initializes the Open OEM dialog directory from the recent-file list.
- The package uses `tomllib` where available and `tomli` for supported Python versions that do
  not include `tomllib`.

## Verification and limitations

Recorded implementation checks covered TOML load/save behavior, recent-file ordering and limits,
CLI/config precedence, CLI help, syntax compilation, and `git diff --check`. The config loader was
checked independently of wxPython. Native wx window restoration, plot restoration, and menu
interaction were not verified in a live GUI environment.

## Related documentation

- [End-user configuration guide](../../../tools/PLAY_OEM_CONFIG.md)
- [`play-oem` concepts and command-line options](../PLAY_OEM_CONCEPTS.md)
- [`play-oem` software design](../PLAY_OEM_SOFTWARE_DESIGN.md)
- [`play-oem` implementation plan](../PLAY_OEM_IMPLEMENTATION_PLAN.md)
