# `play-oem` — Configuration File Development Plan

This document plans a per-user configuration file for `play-oem`. The same XDG-style
location is used on Linux and macOS. The design uses two files: a user-edited config for
longer-lived defaults and an app-maintained state file for changeable workspace state such as
window size and recent files. The proposed end-user guide is
[PLAY_OEM_CONFIG.md](../../tools/PLAY_OEM_CONFIG.md).

Requirements and CLI options: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Software design:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Main implementation sequence:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until
the current step's checklist and completion criteria pass. Keep pending steps in dependency
order; each dependency field identifies its prerequisite. Step 1 has no dependency.

When a step is complete, move its full entry to the `Completed steps` section at the end of this
document. Preserve its original number, status, progress, checklist, completion criteria,
evidence, and dependency so the completion record remains auditable. Keep active steps at the
beginning in dependency order.

If implementation cannot proceed in the documented order, stop and reevaluate the plan before
starting work out of sequence. Update step order, dependencies, completion criteria, and status
to reflect the revised order before continuing.

If the approach changes CLI behavior, config paths, schema, or other user-facing behavior,
update the relevant sections of [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md),
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md), and the end-user guide as needed.
Keep this plan consistent with the implementation and published documentation.

For every step, keep status and progress current:

- `Not started` — no work begun.
- `In progress` — implementation or its checks are underway.
- `Blocked` — cannot proceed; record the blocker.
- `Done` — all checklist items and completion criteria pass.

Progress is the number of checklist items completed. Do not mark a step done based only on code
being written.

## Current directive — add per-user configuration

Implement two TOML files for Linux and macOS in the same XDG-style application directory. Keep
the user-edited config for defaults and the app-maintained state file for mutable UI state. Keep
both readers independent of wxPython; preserve current behavior when either file is absent; and
apply explicit CLI values over config values over built-in defaults where the CLI supports the
same setting. Playback settings initialize GUI controls. This plan supplements the main
`play-oem` implementation plan; it does not change its existing GUI or view milestones.

## Goals

- Let users set recurring `play-oem` defaults without repeating command-line options.
- Use a plain-text format that is readable and editable by hand.
- Follow XDG Base Directory conventions on both Linux and macOS.
- Keep command-line invocations reproducible: explicit CLI options take precedence and are
  not silently written back to the config file.
- Keep configuration loading independent of wxPython so parsing and CLI behavior work in
  headless environments.

## Decisions

### File format

Use **TOML**. The project supports Python 3.9 and later, while the standard-library `tomllib` is
available starting with Python 3.11. Use `tomllib` on Python 3.11 and later, and add the small
`tomli` compatibility dependency for Python 3.9 and 3.10. Do not introduce a general-purpose
configuration framework.

### Config and state file locations

Use these paths on both Linux and macOS, in the same application-specific directory:

```text
${XDG_CONFIG_HOME}/ephem-toolkit/play-oem.toml
${XDG_CONFIG_HOME}/ephem-toolkit/play-oem-state.toml
```

When `XDG_CONFIG_HOME` is unset or empty, use these paths:

```text
~/.config/ephem-toolkit/play-oem.toml
~/.config/ephem-toolkit/play-oem-state.toml
```

If `XDG_CONFIG_HOME` is set to a relative path, ignore it and use the fallback; XDG base
directories must be absolute. Expand the home directory and environment variable, but do not
resolve symlinks. Create the parent directory only when writing. Do not create an empty config or
state file just because the application starts. `play-oem.toml` contains user-selected defaults;
`play-oem-state.toml` is maintained by the application and contains changeable workspace
information, not command-line defaults.

The initial supported platform policy is Linux and macOS, both using this same path. Windows is
outside the initial support scope and is not advertised; the path has not been validated on
Windows.

### Explicit config selection

Add `--config PATH` to load a specific file instead of the default path. An explicit missing
file or unreadable/malformed file is an error with the path and a useful explanation. If the
default config file does not exist, continue with built-in defaults. Do not add multiple
automatic search locations; one deterministic default avoids ambiguity.

### Precedence

For settings that are also command-line options, use:

1. Explicit command-line value.
2. Value from the selected config file.
3. Built-in default.

The parser must distinguish an omitted option from one explicitly supplied with its default
value. Apply this rule to supported display options such as plot selection. Playback
speed and render rate have no CLI override; config values for those settings initialize their GUI
controls. Preserve current behavior when no config file exists.

Config values use the same validation rules as CLI values. Unknown keys and invalid values
should be reported as configuration errors, rather than silently ignored. Include the setting
name and config path in diagnostics.

## Proposed file structure

Use a versioned root table and grouped settings. The version allows future migrations to be
explicit without guessing how older files should be interpreted.

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

The file may omit any table or key; missing values inherit from the next lower-precedence
source where one exists. Keep display names aligned with supported CLI destinations
(`three_d_backend`, `plots`). Playback settings initialize corresponding GUI
controls and have no CLI counterpart.

## Settings policy

| Setting | Initial config support | Reason / constraints |
|---|---:|---|
| `playback.speed` | Yes | Initial playback rate; validate from 1x through 9000x. |
| `playback.reverse` | Yes | Initial playback direction preference for the GUI. |
| `playback.fps` | Yes | Render-rate preference from 1 through 30 FPS; initializes the Playback pane slider. |
| `display.three_d_backend` | Yes | Persistent renderer preference; validate choices and availability behavior consistently with CLI. |
| `display.plots` | Yes | Initial views; parse with the same registry/group rules as `--plots`. |
| Input OEM path | No | File-specific and likely to become stale; continue accepting it as a CLI argument. |
| Duration | No | `play-oem` loads the entire OEM file; no duration CLI option is provided. |
| Start time | No | Tied to the current OEM timeline and can become invalid for another file; seek in the GUI. |
| Window geometry and pane layout | No | These are app-maintained workspace state and belong in `play-oem-state.toml`. |

Do not persist transient runtime state such as current cursor time, playing/paused state after
launch, or a one-off command-line override in the user config. Keep window size and recent-file
history in the separate state file described below.

### State file structure

The state file is TOML with its own version so it can evolve independently from user defaults.
The application creates it only when there is state to save.

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

Store at most 15 recent OEM paths, most recently opened first. Record a file only after it loads
successfully. When a path is opened again, move it to the front rather than adding a duplicate.
Store absolute, normalized paths so the recent list does not depend on the launch directory.
Keep unavailable paths in the list; a removable drive or mounted directory may return later, and
opening an unavailable item can use the normal file-open error handling.

Save window width and height when the main window closes, and restore them on the next launch.
Clamp restored dimensions to a usable size for the current display. Do not persist window
position in the initial version because monitor arrangements can change. `maximized` may be
restored when true.

Missing state is normal and uses the application defaults. If state TOML is malformed or a
stored value is invalid, report a warning and continue with safe defaults; state-file problems
must not prevent opening an OEM. Save updates atomically using a temporary file in the same
directory followed by replacement. Do not write per-run CLI overrides to `play-oem.toml`.

## Active work

No pending steps. Completed implementation records follow the acceptance criteria.

## Acceptance criteria

- Linux and macOS use the same documented XDG-style path rules for both files.
- Neither file is required; absent user config preserves current behavior and absent state uses
  safe initial UI defaults.
- Config parsing and CLI merging work without wxPython or a display.
- State-file parsing and saving are independent of the user-config file.
- The state file holds usable window dimensions and no more than 15 recent OEM paths, ordered
  newest first.
- CLI options override config values, and config values override built-in defaults.
- Malformed TOML, unknown keys, invalid values, and explicit missing paths produce useful errors.
- A one-off command-line invocation does not modify the user's config; state updates do not
  overwrite it.
- User documentation reflects the actual implementation.

## Completed steps

### 1. Define and document the configuration contract

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Confirm the Python 3.9–3.10 TOML reader and dependency declaration, while using
      `tomllib` on Python 3.11 and later.
- [x] Finalize XDG path selection for unset, empty, relative, and absolute
      `XDG_CONFIG_HOME` values.
- [x] Define the schema, supported keys, types, bounds, and unknown-key policy from this
      document.
- [x] Record Windows path behavior before advertising config-path support on Windows.

**Evidence:** The project uses `tomllib` on Python 3.11 and later and the conditional `tomli`
dependency on Python 3.9 and 3.10. The config and state modules share the XDG-style directory
resolver. The Linux/macOS scope and unvalidated Windows status are documented in this plan and
the user guide.

**Done when:** the supported platform and file/schema contract is documented without
contradictions in the CLI, package requirements, software design, and user guide.
**Depends on:** None.

### 2. Implement configuration path resolution and loading

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add a focused configuration module under `src/ephem_toolkit/play_oem/`.
- [x] Resolve the default file using `XDG_CONFIG_HOME` on Linux and macOS, with
      `~/.config` fallback.
- [x] Load TOML without importing wxPython or starting the GUI.
- [x] Validate schema, types, known keys, and setting ranges; report actionable errors.
- [x] Keep missing default config distinct from a missing explicitly selected config.

**Evidence:** `config.py` loads and validates versioned TOML, rejects unknown or invalid
settings, and distinguishes an absent default file from an explicitly selected missing file.
A smoke run loaded display and playback settings and confirmed the explicit missing-path error.
The config loader imports no wxPython modules.

**Done when:** configuration path and loading behavior are deterministic, validated, and
usable in a headless process.
**Depends on:** Step 1.

### 3. Merge config values with CLI arguments

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add `--config PATH` and document it in `--help`.
- [x] Track whether each config-capable CLI option was explicitly provided.
- [x] Apply CLI-over-config-over-built-in-default precedence per setting.
- [x] Reuse CLI validators for config values, including plots and backend choices.
- [x] Preserve behavior exactly when no config file exists.

**Evidence:** The CLI records explicit `--plots`, `--3d-backend`, and `--config` use. An
integration smoke run loaded configured playback values while explicit plot/backend options
overrode config values. Missing config preserves parser and GUI defaults.

**Done when:** omitted CLI options use config values, explicit CLI options win even when they
match built-in defaults, and no-config invocations retain current defaults.
**Depends on:** Step 2.

### 4. Define and implement the separate state file

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Resolve `play-oem-state.toml` beside the user config using the same XDG path rules.
- [x] Define and validate the independent state schema and version.
- [x] Restore and save usable window width/height and maximized state.
- [x] Save and restore the open graph views, with explicit CLI and user config selections
      taking precedence.
- [x] Add successfully loaded OEM paths to a most-recent-first list capped at 15, moving
      duplicates to the front.
- [x] Preserve unavailable recent paths and handle attempts to reopen them through the normal
      file-open flow.
- [x] Warn and continue with defaults for invalid state; write valid updates atomically without
      touching `play-oem.toml`.

**Evidence:** `saved_state.py` validates and writes open view names alongside window geometry and
recent files. The CLI restores saved views when neither `--plots` nor `display.plots` is set;
explicit selections take precedence. The wx application saves the current open views on exit.
Native wx window restore, plot restoration, and menu interaction were not smoke-tested in this
environment.

**Done when:** window size, open views, and up to 15 recent OEM files survive a restart through
the separate state file, invalid state does not prevent startup, and the user config file remains
unchanged.
**Depends on:** Step 3.

### 5. Publish user documentation

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Document both file paths for Linux and macOS and the `XDG_CONFIG_HOME` override.
- [x] Include example TOML structures and explain which file is user-edited versus app-maintained.
- [x] Document `--config`, precedence, missing-file behavior, and error behavior for user
      config; document state recovery behavior.
- [x] Verify docs match the implemented schema and CLI help.

**Evidence:** [PLAY_OEM_CONFIG.md](../../tools/PLAY_OEM_CONFIG.md) documents both files,
their TOML structures, recent-file behavior, config selection, precedence, and error handling.
CLI help exposes `--config`.

**Done when:** users can locate, edit, select, and troubleshoot their config file from the
published `play-oem` documentation.
**Depends on:** Steps 3 and 4.
