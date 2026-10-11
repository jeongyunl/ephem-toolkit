# Class/Object File I/O API

## Purpose

This document records the implemented class-based file I/O design for the
structured orbital formats in this repository:

- CCSDS Orbit Ephemeris Message (OEM)
- CCSDS Orbit Mean-Elements Message (OMM)
- CCSDS Orbit Parameter Message (OPM)
- NORAD Two-Line Element sets (TLE)

The API separates path, stream, and text operations. The migration is complete,
and this document describes the current object I/O design.

The authoritative naming and type conventions remain in
[python_style_guide.md](python_style_guide.md), especially its File I/O
section.

## Goals

1. Give every structured format the same public object API.
2. Make path I/O, stream I/O, and in-memory text serialization unambiguous.
3. Replace public procedural format I/O with object methods.
4. Preserve CCSDS validation, encoding, units, output ordering, and
   CLI behavior.
5. Make one direct repository-wide API change rather than maintaining
   compatibility layers.

## Non-goals

- Changing file formats, CCSDS validation rules, or TLE checksum behavior.
- Replacing format-specific conversion functions such as `tle_to_omm`.
- Adding extension-based auto-detection across OEM, OMM, OPM, and TLE.
- Moving command-line stdin/stdout management into domain objects.

## Standard Public Object API

Each structured format class should expose the following methods. `TextIO`
means an already-open readable or writable text stream.

```python
from __future__ import annotations

from pathlib import Path
from typing import TextIO

class FormatMessage:
    @classmethod
    def read(cls, source: TextIO) -> FormatMessage:
        """Construct an object from an open text stream."""

    def write(self, dest: TextIO) -> None:
        """Write this object to an open text stream."""

    @classmethod
    def from_file(cls, path: str | Path) -> FormatMessage:
        """Construct an object from a UTF-8 file."""

    def to_file(self, path: str | Path) -> None:
        """Write this object to a UTF-8 file."""

    @classmethod
    def from_text(cls, text: str) -> FormatMessage:
        """Construct an object from serialized text."""

    def to_text(self) -> str:
        """Return the serialized text representation."""
```

### Responsibilities and ownership

| API | Input/output | Opens or closes a file | Intended use |
| --- | --- | --- | --- |
| `read` / `write` | `TextIO` | No | Embedding, stdin/stdout, `StringIO`, archives |
| `from_file` / `to_file` | `str \| Path` | Yes | Ordinary filesystem I/O |
| `from_text` / `to_text` | `str` | No filesystem access | Tests, network payloads, generated data |

`read` and `write` are the primitive operations. `from_file`, `to_file`,
`from_text`, and `to_text` must be thin wrappers around them. A caller that
passes a stream continues to own its lifetime; the API must not close it.

Path wrappers use UTF-8. Text-format writers use `newline="\n"` when opening
a path so generated files are reproducible across platforms. The object API
does not accept `"-"` as a special path; that is CLI routing and remains in
the command modules.

### Naming rules

- Use `source` for a reader's stream parameter and `dest` for a writer's
  stream parameter.
- Use `path` for filesystem convenience methods rather than overloading
  `source` or `dest`.
- Use class factories (`from_*`) for construction and instance methods
  (`to_*`, `write`) for serialization.
- Keep format-specific parameters on the relevant serializer. For example,
  OEM's `format_type` remains available on `write`, `to_file`, and `to_text`.
- Do not make constructors parse files. `CcsdsOem("orbit.oem")` is ambiguous
  and must not be introduced.

## Format APIs

### OEM: `CcsdsOem`

**Implementation:** `src/ephem_toolkit/core/ccsds/oem.py`  
**Structured class:** `CcsdsOem`  
**Supporting classes:** `OemHeader`, `OemMeta`, `OemCovariance`  
**Current object API:** `read(source)`, `write(dest, format_type=...)`,
`from_states(...)`, `write_states(...)`, and `write_state(...)`.

```python
class CcsdsOem:
    @classmethod
    def read(cls, source: TextIO) -> CcsdsOem: ...

    def write(
        self, dest: TextIO, *, format_type: OemFormat = OemFormat.OEM
    ) -> None: ...

    @classmethod
    def from_file(cls, path: str | Path) -> CcsdsOem: ...

    def to_file(
        self, path: str | Path, *, format_type: OemFormat = OemFormat.OEM
    ) -> None: ...

    @classmethod
    def from_text(cls, text: str) -> CcsdsOem: ...

    def to_text(
        self, *, format_type: OemFormat = OemFormat.OEM
    ) -> str: ...
```

`from_states`, `write_state`, and `write_states` are domain-specific APIs
and remain unchanged. OEM state vectors remain internally in meters and
meters per second; serialization continues to use CCSDS km and km/s.

`CcsdsOem.read` and `CcsdsOem.write` accept streams only. Use `from_file` and
`to_file` for filesystem paths.

### OMM: `CcsdsOmm`

**Implementation:** `src/ephem_toolkit/core/ccsds/omm.py`  
**Structured class:** `CcsdsOmm`  
**Supporting classes:** `TleParameters`, `OmmSpacecraftParameters`,
`OmmCovariance`  
**Current object API:** `read(source)`, `write(dest)`, `from_file(path)`,
`to_file(path)`, `from_text(text)`, and `to_text()`.

```python
class CcsdsOmm:
    @classmethod
    def read(cls, source: TextIO) -> CcsdsOmm: ...

    def write(self, dest: TextIO) -> None: ...

    @classmethod
    def from_file(cls, path: str | Path) -> CcsdsOmm: ...

    def to_file(self, path: str | Path) -> None: ...

    @classmethod
    def from_text(cls, text: str) -> CcsdsOmm: ...

    def to_text(self) -> str: ...
```

`read` accepts streams, `from_file` accepts paths, `write` accepts streams,
and `to_file` accepts paths.

Use the object API for parsing and serialization. Dictionary representations
remain available through `CcsdsOmm.to_dict()`.

### OPM: `CcsdsOpm`

**Implementation:** `src/ephem_toolkit/core/ccsds/opm.py`  
**Structured class:** `CcsdsOpm`  
**Supporting classes:** `OpmHeader`, `OpmStateVector`,
`OpmKeplerianElements`, `OpmSpacecraftParameters`, `OpmCovariance`, and
`OpmManeuver`  
**Current object API:** `read(source)`, `write(dest)`, `from_file(path)`,
`to_file(path)`, `from_text(text)`, and `to_text()`.

```python
class CcsdsOpm:
    @classmethod
    def read(cls, source: TextIO) -> CcsdsOpm: ...

    def write(self, dest: TextIO) -> None: ...

    @classmethod
    def from_file(cls, path: str | Path) -> CcsdsOpm: ...

    def to_file(self, path: str | Path) -> None: ...

    @classmethod
    def from_text(cls, text: str) -> CcsdsOpm: ...

    def to_text(self) -> str: ...
```

`read` accepts streams, `from_file` accepts paths, `write` accepts streams,
and `to_file` accepts paths.

Use the object API for parsing and serialization. Dictionary representations
remain available through `CcsdsOpm.to_dict()`.

### TLE: `Tle`

**Implementation:** `src/ephem_toolkit/core/tle.py`  
**Structured class:** `Tle`  
**Current object API:** all six stream, path, and text operations are methods
on `Tle`.

```python
class Tle:
    @classmethod
    def read(cls, source: TextIO) -> Tle: ...

    def write(self, dest: TextIO) -> None: ...

    @classmethod
    def from_file(cls, path: str | Path) -> Tle: ...

    def to_file(self, path: str | Path) -> None: ...

    @classmethod
    def from_text(cls, text: str) -> Tle: ...

    def to_text(self) -> str: ...
```

`Tle.write` and `Tle.to_file` return `None`, like the other format writers.
`to_text` returns the complete two- or three-line payload, including a final
newline. `format_tle_strings` returns `(line1, line2)` for callers that need
the raw TLE lines without performing I/O.

The no-I/O `format_tle_strings` helper returns raw TLE lines when needed;
ordinary parsing and serialization use the `Tle` methods.

## Related Callers and Completed Updates

The following production files were updated for the object APIs or retain
adjacent procedural I/O at the CLI boundary.

| Area | Files | Implemented design |
| --- | --- | --- |
| Core format models | `src/ephem_toolkit/core/ccsds/oem.py`, `src/ephem_toolkit/core/ccsds/omm.py`, `src/ephem_toolkit/core/ccsds/opm.py`, `src/ephem_toolkit/core/tle.py` | Stream-only object methods with separate path and text wrappers |
| TLE conversions | `src/ephem_toolkit/core/convert_tle.py`, `src/ephem_toolkit/oem_to_omm/fit_tle/tle_builder.py`, `src/ephem_toolkit/oem_to_omm/fit_tle/refinement.py` | Use `Tle` objects; no-I/O formatting helpers remain available |
| OEM comparison and plotting | `src/ephem_toolkit/diff_oem/comparison.py`, `src/ephem_toolkit/plot_oem/plot_oem.py`, `src/ephem_toolkit/plot_oem_diff/file_io.py` | Select path or stream methods by source kind; the raw-state fallback lives in `StateHistory.from_orbit_file` |
| OMM/OPM propagation | `src/ephem_toolkit/propagate_omm/propagation.py`, `src/ephem_toolkit/propagate_orbit/input_handling.py`, `src/ephem_toolkit/propagate_kepler/propagation.py` | CLI dispatch selects the stream or path object APIs |
| OEM output | `src/ephem_toolkit/propagate_omm/propagation.py`, `src/ephem_toolkit/propagate_orbit/output_handling.py`, `src/ephem_toolkit/slice_oem/__main__.py`, `src/ephem_toolkit/xform_oem/__main__.py` | Stream output uses `write`; path output uses `to_file` |
| Format conversion CLIs | `src/ephem_toolkit/oem_to_omm/__main__.py`, `src/ephem_toolkit/oem_to_opm/__main__.py`, `src/ephem_toolkit/omm_to_tle/__main__.py`, `src/ephem_toolkit/tle_to_omm/__main__.py`, `src/ephem_toolkit/tle_to_opm/__main__.py` | stdin/stdout use stream APIs; named files use path APIs |
| TLE utility CLIs | `src/ephem_toolkit/tle_info/__main__.py`, `src/ephem_toolkit/download_tle/__main__.py` | Network and CLI routing stay in command modules; TLE content is parsed through `Tle` |
| CSV domain I/O | `src/ephem_toolkit/plot_dep_vars/plot_dependent_variables.py`, `src/ephem_toolkit/propagate_orbit/output_handling.py`, `src/ephem_toolkit/plot_oem_diff/csv_utils.py` | `CsvDependentVariableData` handles parsed data; output orchestration remains procedural |

The raw-state fallback in `plot_oem_diff/file_io.py` must remain explicit. It
accepts input that is not a complete OEM, so it cannot be replaced solely by
`CcsdsOem.from_file`.

## Non-object File I/O Assessment

The repository also has procedural file-I/O functions outside the four
structured orbit-message formats. They do not all benefit from being converted
to methods: an object API is appropriate when a stable domain object owns both
the parsed data and its serialization contract. CLI routing, conversion
orchestration, generic utilities, and side-effecting resource operations
should remain functions.

| Current API | File and current return/value | Current treatment | Rationale |
| --- | --- | --- | --- |
| `CsvDependentVariableData.from_file(path)` | `plot_dep_vars/plot_dependent_variables.py`; parsed data object | Object factory | The data object owns parsed times, columns, and metadata |
| `StateHistory.from_orbit_file(path)` | `plot_oem_diff/data_structures.py`; state-history object | Object factory | `StateHistory` owns the mapping and explicit source-format fallback |
| `read_states(source)` | `diff_oem/comparison.py`; list of state tuples | Procedural adapter | It is a comparison-specific projection of `CcsdsOem.states`, not a separate serializable model |
| `read_oem_states(path)` | `plot_oem/plot_oem.py`; OEM plus split arrays | Procedural adapter | It is a plotting adapter whose tuple shape is tailored to existing plotting code |
| `write_state_history_oem(...)` | `propagate_orbit/output_handling.py`; constructs metadata and writes OEM | Procedural orchestration | It combines propagator configuration, provenance policy, stdout routing, and OEM serialization |
| `write_dependent_variables_csv(...)` | `propagate_orbit/output_handling.py`; writes Tudat data | Procedural orchestration | Its inputs are third-party settings and arrays, not `CsvDependentVariableData` |
| `write_csv(dest, header, rows)` | `plot_oem_diff/csv_utils.py`; generic CSV output | Generic utility | It has no owned domain object |
| `write_fit_report(...)` / `resolve_source_model(...)` | `core/provenance.py`; JSON report dictionaries | Deferred design item | The current writer accepts multiple diagnostics/configuration shapes and is a report builder, not a stable model |
| `read_tle_input`, `read_omm_input`, `read_kepler_input`, `read_initial_state_from_opm_file_or_stdin` | Propagation modules | CLI adapters | They interpret `"-"`, inspect `sys.stdin`, and create propagation inputs |
| Direct CLI `open`, `read_text`, and `write_text` calls | command `__main__.py` modules | CLI boundary | Commands own stdin/stdout conventions, exit status, and user-facing diagnostics |
| `load_kernel(...)` and SPICE cache reads/writes | `core/spice_utils.py` | Procedural resource operation | Loading a kernel mutates process-global SPICE state and does not represent file-backed object data |
| `save_or_show_figure(...)` | `plot_oem/plot_oem.py` | Presentation operation | It acts on a Matplotlib object, not a serializable domain model |

### Dependent-variable CSV: implemented

`CsvDependentVariableData` in
`src/ephem_toolkit/plot_dep_vars/plot_dependent_variables.py` owns the parsed
times, columns, and metadata and exposes:

```python
@dataclass
class CsvDependentVariableData:
    @classmethod
    def read(cls, source: TextIO) -> CsvDependentVariableData: ...

    @classmethod
    def from_file(cls, path: str | Path) -> CsvDependentVariableData: ...

    @classmethod
    def from_text(cls, text: str) -> CsvDependentVariableData: ...
```

The class does not expose `write`, `to_file`, or `to_text`: it represents
parsed output generated by Tudat, and the repository has no requirement to
round-trip or author this data through the plotting layer.

`read` is the canonical CSV validator, preserving header, row-width, and
numeric-value errors. `plot_dependent_variables_from_csv` calls
`CsvDependentVariableData.from_file`.

### Plot-delta state histories: implemented with a named format boundary

`StateHistory` in
`src/ephem_toolkit/plot_oem_diff/data_structures.py` owns the timestamp-to-state
mapping and interpolation behavior, and exposes a format-specific factory:

```python
@dataclass
class StateHistory:
    @classmethod
    def from_orbit_file(
        cls, path: str | Path, *, label: str | None = None
    ) -> StateHistory: ...
```

The factory first loads a complete OEM through `CcsdsOem.from_file`, then
falls back to the raw-state-line parser only when OEM parsing fails. It must
preserve the current `FileNotFoundError` and "no state data" errors, and the
fallback must not silently discard an OEM validation error when the input
contains no valid raw state rows.

Command modules construct and pass `StateHistory` directly.

### Fit-report JSON: defer until a stable schema exists

`write_fit_report` creates a JSON document from flexible diagnostics and
configuration inputs. Converting it immediately to a class would either
require an overly broad `dict[str, Any]` object or prematurely freeze a
schema. Leave it as a report-builder function for now.

If JSON fit reports become a documented interchange format, introduce a
`FitReport` dataclass with `from_dict`, `to_dict`, `read`, `write`,
`from_file`, `to_file`, `from_text`, and `to_text`. At that point,
`resolve_source_model` should accept `FitReport` rather than reopening its
file argument.

### Procedural APIs that must remain

Do not convert functions merely because they call `open`:

- CLI input helpers need to own `"-"` handling, terminal checks, and user
  errors.
- `write_state_history_oem` and `write_dependent_variables_csv` are
  propagation-output orchestration. Their serialization should delegate to
  object methods, but their configuration-to-output transformation is
  intentionally procedural.
- Generic CSV writing, figure saving, and SPICE kernel loading do not have a
  corresponding repository-owned data model.

## CLI Boundary

CLI modules are responsible for interpreting `"-"` as stdin/stdout and for
presenting `OSError` and `ValueError` to users. Their routing pattern should
be:

```python
if input_path == "-":
    message = CcsdsOmm.read(sys.stdin)
else:
    message = CcsdsOmm.from_file(input_path)

if output_path == "-":
    message.write(sys.stdout)
else:
    message.to_file(output_path)
```

This keeps path handling out of the format model while maintaining the
command behavior.
