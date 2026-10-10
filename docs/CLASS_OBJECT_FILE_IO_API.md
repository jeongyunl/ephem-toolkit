# Class/Object File I/O API Migration

## Purpose

This document defines a consistent class-based file I/O API for the
structured orbital formats in this repository:

- CCSDS Orbit Ephemeris Message (OEM)
- CCSDS Orbit Mean-Elements Message (OMM)
- CCSDS Orbit Parameter Message (OPM)
- NORAD Two-Line Element sets (TLE)

It is an implementation plan, not a behavior change by itself. The design
uses the existing parsing and formatting logic internally while exposing one
uniform object API that separates path, stream, and text operations.

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
| `from_file` / `to_file` | `str | Path` | Yes | Ordinary filesystem I/O |
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

## Proposed Format APIs

### OEM: `CcsdsOem`

**Implementation:** `src/ephem_toolkit/core/ccsds/oem.py`  
**Structured class:** `CcsdsOem`  
**Supporting classes:** `OemHeader`, `OemMeta`, `OemCovariance`  
**Existing object API:** `read(source)`, `write(dest, format_type=...)`,
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

`CcsdsOem.read` and `CcsdsOem.write` accept streams only. All path callers
must use `from_file` and `to_file`; support for paths passed directly to
`read` and `write` is removed.

### OMM: `CcsdsOmm`

**Implementation:** `src/ephem_toolkit/core/ccsds/omm.py`  
**Structured class:** `CcsdsOmm`  
**Supporting classes:** `TleParameters`, `OmmSpacecraftParameters`,
`OmmCovariance`  
**Existing object API:** `from_source(source)`, `to_file(dest)`.

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

Remove `from_source`. `read` accepts streams, `from_file` accepts paths,
`write` accepts streams, and `to_file` accepts paths.

Replace the public low-level `read_omm` and `write_omm` functions with
private parser and serializer helpers used only by `CcsdsOmm`. Dictionary
representations remain available through `CcsdsOmm.to_dict()`.

### OPM: `CcsdsOpm`

**Implementation:** `src/ephem_toolkit/core/ccsds/opm.py`  
**Structured class:** `CcsdsOpm`  
**Supporting classes:** `OpmHeader`, `OpmStateVector`,
`OpmKeplerianElements`, `OpmSpacecraftParameters`, `OpmCovariance`, and
`OpmManeuver`  
**Existing object API:** `from_source(source)`, `to_file(dest)`.

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

Remove `from_source`. `read` accepts streams, `from_file` accepts paths,
`write` accepts streams, and `to_file` accepts paths.

Replace the public low-level `read_opm` and `write_opm` functions with
private parser and serializer helpers used only by `CcsdsOpm`. Dictionary
representations remain available through `CcsdsOpm.to_dict()`.

### TLE: `Tle`

**Implementation:** `src/ephem_toolkit/core/tle.py`  
**Structured class:** `Tle`  
**Existing object API:** data accessors only; parsing and writing are module
functions `read_tle` and `write_tle`.

```python
class Tle:
    @classmethod
    def read(cls, source: TextIO) -> Tle: ...

    def write(self, dest: TextIO) -> tuple[str, str]: ...

    @classmethod
    def from_file(cls, path: str | Path) -> Tle: ...

    def to_file(self, path: str | Path) -> tuple[str, str]: ...

    @classmethod
    def from_text(cls, text: str) -> Tle: ...

    def to_text(self) -> str: ...
```

`Tle.write` and `Tle.to_file` return `(line1, line2)`. `to_text` returns the complete two- or
three-line payload, including a final newline. `format_tle_strings` remains
the no-I/O formatter for callers that only need the two raw lines.

Remove public `read_tle` and `write_tle`. Implement the object methods with
one canonical private parser and formatter so checksum and name-line behavior
cannot diverge.

## Existing API to Target API Mapping

| Current API | Target API | Migration action |
| --- | --- | --- |
| `CcsdsOem.read(path_or_stream)` | `CcsdsOem.from_file(path)` or `CcsdsOem.read(stream)` | Remove path-or-stream overload and update every caller |
| `CcsdsOem.write(path_or_stream)` | `oem.to_file(path)` or `oem.write(stream)` | Remove path-or-stream overload and update every caller |
| `CcsdsOmm.from_source(path_or_stream)` | `CcsdsOmm.from_file(path)` or `CcsdsOmm.read(stream)` | Remove `from_source` |
| `CcsdsOmm.to_file(path_or_stream)` | `omm.to_file(path)` or `omm.write(stream)` | Make `to_file` path-only |
| `CcsdsOpm.from_source(path_or_stream)` | `CcsdsOpm.from_file(path)` or `CcsdsOpm.read(stream)` | Remove `from_source` |
| `CcsdsOpm.to_file(path_or_stream)` | `opm.to_file(path)` or `opm.write(stream)` | Make `to_file` path-only |
| `read_tle(path_or_stream)` | `Tle.from_file(path)` or `Tle.read(stream)` | Remove procedural reader |
| `write_tle(path_or_stream, tle_data)` | `tle_data.to_file(path)` or `tle_data.write(stream)` | Remove procedural writer |
| `read_omm` / `write_omm` | `CcsdsOmm` object methods | Make dictionary parser and serializer private |
| `read_opm` / `write_opm` | `CcsdsOpm` object methods | Make dictionary parser and serializer private |

## Related Callers and Required Updates

The following production files call the format APIs or implement adjacent
file I/O. Update them when the object API is introduced.

| Area | Files | Required change |
| --- | --- | --- |
| Core format models | `src/ephem_toolkit/core/ccsds/oem.py`, `src/ephem_toolkit/core/ccsds/omm.py`, `src/ephem_toolkit/core/ccsds/opm.py`, `src/ephem_toolkit/core/tle.py` | Implement only the standard object methods and private parser/serializer helpers |
| TLE conversions | `src/ephem_toolkit/core/convert_tle.py`, `src/ephem_toolkit/oem_to_omm/fit_tle/tle_builder.py`, `src/ephem_toolkit/oem_to_omm/fit_tle/refinement.py` | Use `Tle` object methods where an object is already available; retain no-I/O formatting helpers |
| OEM comparison and plotting | `src/ephem_toolkit/diff_oem/comparison.py`, `src/ephem_toolkit/plot_oem/plot_oem.py`, `src/ephem_toolkit/plot_oem_diff/file_io.py` | Use `from_file` for paths and `read` for streams; move the raw-state fallback into `StateHistory.from_orbit_file` |
| OMM propagation | `src/ephem_toolkit/propagate_omm/propagation.py` | Replace `CcsdsOmm.from_source` with `from_file` or `read` after its stdin dispatch |
| OPM propagation | `src/ephem_toolkit/propagate_orbit/input_handling.py`, `src/ephem_toolkit/propagate_kepler/propagation.py` | Replace `CcsdsOpm.from_source` according to source kind |
| OEM output | `src/ephem_toolkit/propagate_omm/propagation.py`, `src/ephem_toolkit/propagate_orbit/output_handling.py`, `src/ephem_toolkit/slice_oem/__main__.py`, `src/ephem_toolkit/xform_oem/__main__.py` | Use `write` for stdout/open handles and `to_file` for paths |
| Format conversion CLIs | `src/ephem_toolkit/oem_to_omm/__main__.py`, `src/ephem_toolkit/oem_to_opm/__main__.py`, `src/ephem_toolkit/omm_to_tle/__main__.py`, `src/ephem_toolkit/tle_to_omm/__main__.py`, `src/ephem_toolkit/tle_to_opm/__main__.py` | Route stdin/stdout through stream APIs and named files through path APIs |
| TLE utility CLIs | `src/ephem_toolkit/tle_info/__main__.py`, `src/ephem_toolkit/download_tle/__main__.py` | Prefer `Tle.read`/`from_file` when parsing downloaded or named content; leave network ownership in the CLI |
| CSV domain I/O | `src/ephem_toolkit/plot_dep_vars/plot_dependent_variables.py`, `src/ephem_toolkit/propagate_orbit/output_handling.py`, `src/ephem_toolkit/plot_oem_diff/csv_utils.py` | Out of scope for orbit-message objects; assess `CsvDependentVariableData.from_file` separately |

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

| Current API | File and current return/value | Recommendation | Rationale |
| --- | --- | --- | --- |
| `read_dependent_variables_csv(path)` | `plot_dep_vars/plot_dependent_variables.py`; arrays and header list | **Convert** to `CsvDependentVariableData.from_file(path)` | `CsvDependentVariableData` already owns the parsed times, columns, and metadata |
| `load_csv_dependent_variable_data(path)` | Same file; `CsvDependentVariableData` | **Convert** to `CsvDependentVariableData.from_file(path)` | This is already semantically a class factory; its name is redundant after conversion |
| `read_orbit_file(path)` | `plot_oem_diff/file_io.py`; raw `dict[float, ndarray]` | **Convert** to `StateHistory.from_orbit_file(path)` | `StateHistory` is the consumer-facing owner, and can expose the source-format fallback explicitly |
| `read_states(source)` | `diff_oem/comparison.py`; list of state tuples | **Keep procedural** | It is a comparison-specific projection of `CcsdsOem.states`, not a separate serializable model |
| `read_oem_states(path)` | `plot_oem/plot_oem.py`; OEM plus split arrays | **Keep procedural** | It is a plotting adapter whose tuple shape is tailored to existing plotting code |
| `write_state_history_oem(...)` | `propagate_orbit/output_handling.py`; constructs metadata and writes OEM | **Keep procedural; extract object construction if needed** | It combines propagator configuration, provenance policy, stdout routing, and OEM serialization |
| `write_dependent_variables_csv(...)` | `propagate_orbit/output_handling.py`; writes Tudat data | **Keep procedural** | Its inputs are third-party settings and arrays, not `CsvDependentVariableData` |
| `write_csv(dest, header, rows)` | `plot_oem_diff/csv_utils.py`; generic CSV output | **Keep procedural** | It is an intentionally generic utility with no owned domain object |
| `write_fit_report(...)` / `resolve_source_model(...)` | `core/provenance.py`; JSON report dictionaries | **Defer; introduce `FitReport` only if reports become public models** | The current writer accepts multiple diagnostics/configuration shapes and is a report builder, not a stable model |
| `read_tle_input`, `read_omm_input`, `read_kepler_input`, `read_initial_state_from_opm_file_or_stdin` | Propagation modules | **Keep procedural** | These are CLI adapters that interpret `"-"`, inspect `sys.stdin`, and create propagation inputs |
| Direct CLI `open`, `read_text`, and `write_text` calls | command `__main__.py` modules | **Keep at the CLI boundary** | Commands own stdin/stdout conventions, exit status, and user-facing diagnostics |
| `load_kernel(...)` and SPICE cache reads/writes | `core/spice_utils.py` | **Keep procedural** | Loading a kernel mutates process-global SPICE state and does not represent file-backed object data |
| `save_or_show_figure(...)` | `plot_oem/plot_oem.py` | **Keep procedural** | It is a presentation action on a Matplotlib object, not a serializable domain model |

### Dependent-variable CSV: convert

`CsvDependentVariableData` in
`src/ephem_toolkit/plot_dep_vars/plot_dependent_variables.py` is already the
right value object. Add:

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

The class does not need `write`, `to_file`, or `to_text` yet: it represents
parsed output generated by Tudat, and the repository has no requirement to
round-trip or author this data through the plotting layer. Add writers only if
the data class becomes the canonical producer of the dependent-variable CSV
format.

Implement `read` as the canonical CSV validator, preserving the current
header, row-width, and numeric-value errors. Remove
`read_dependent_variables_csv(path)` and
`load_csv_dependent_variable_data(path)`, and update
`plot_dependent_variables_from_csv` to call `CsvDependentVariableData.from_file`.

### Plot-delta state histories: convert with a named format boundary

`StateHistory` in
`src/ephem_toolkit/plot_oem_diff/data_structures.py` already owns the
timestamp-to-state mapping and interpolation behavior. Add a format-specific
factory rather than a misleading generic file method:

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

Remove `read_orbit_file(path)`. The command module constructs and passes
`StateHistory` directly, avoiding an intermediate dictionary-only API.

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

## Implementation Sequence

1. Add stream-only `read` and `write`, then `from_file`, `to_file`,
   `from_text`, and `to_text` to `CcsdsOem`.
2. Add the same methods to `CcsdsOmm` and `CcsdsOpm`; remove `from_source`,
   the public dictionary readers, and the public dictionary writers.
3. Add class methods to `Tle`; remove `read_tle` and `write_tle`, while
   retaining `format_tle_strings` as a no-I/O formatter.
4. Add `CsvDependentVariableData.read`, `from_file`, and `from_text`; remove
   the two procedural CSV readers.
5. Add `StateHistory.from_orbit_file`; remove `read_orbit_file`.
6. Migrate all production callers according to whether they hold a path or
   an open stream.
7. Delete obsolete tests, add tests for the new object methods, and update
   affected tests to use only the replacement APIs.
8. Update public docstrings, examples, and
   [CORE_LIBRARY_TLE_OMM.md](CORE_LIBRARY_TLE_OMM.md).

## Test Plan

Add or update the following tests for every format:

1. `read(StringIO(text))` and `from_text(text)` produce equivalent objects.
2. `from_file(path)` is equivalent to `read(open_stream)`.
3. `write(StringIO())` and `to_text()` produce equivalent serialization.
4. `to_file(path)` round-trips through `from_file(path)`.
5. Caller-owned streams remain open after `read` and `write`.
6. Existing validation errors, checksum behavior, native units, metadata,
   comments, covariance, and optional blocks are preserved.

Primary format test files:

- `tests/ephem_toolkit/core/ccsds/test_oem.py`
- `tests/ephem_toolkit/core/ccsds/test_omm.py`
- `tests/ephem_toolkit/core/ccsds/test_opm.py`
- `tests/ephem_toolkit/core/test_tle.py`

Caller regression coverage also resides in:

- `tests/ephem_toolkit/core/test_convert_tle.py`
- `tests/ephem_toolkit/diff_oem/test_diff_oem.py`
- `tests/ephem_toolkit/plot_oem_diff/test_plot_oem_diff.py`
- `tests/ephem_toolkit/plot_dep_vars/test_plot_dependent_variables.py`
- `tests/ephem_toolkit/propagate_orbit/test_input_handling.py`
- `tests/ephem_toolkit/propagate_orbit/test_output_handling.py`
- `tests/ephem_toolkit/propagate_kepler/test_propagate_kepler.py`
- `tests/ephem_toolkit/propagate_omm/test_dsst_propagation.py`
- conversion-package tests under `tests/ephem_toolkit/oem_to_omm/`,
  `tests/ephem_toolkit/oem_to_opm/`, `tests/ephem_toolkit/oem_to_tle/`,
  `tests/ephem_toolkit/omm_to_opm/`, `tests/ephem_toolkit/omm_to_tle/`,
  `tests/ephem_toolkit/tle_to_omm/`, and `tests/ephem_toolkit/tle_to_opm/`.

## Acceptance Criteria

- All four structured format classes present the same six object-I/O method
  names.
- Stream methods neither open nor close caller-owned streams.
- Filesystem methods use UTF-8 and normalize writer newlines to `"\n"`.
- All existing format round-trip tests and affected CLI tests pass.
- The removed procedural and path-or-stream object I/O APIs have no production
  callers or tests.
- The public examples use explicit path or stream methods rather than an
  ambiguous path-or-stream call.
