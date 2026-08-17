# CLI Command Details and Target Standards

This document captures the approved target design for the CLI cleanup and unification effort. It follows the conventions established in the CLI unification plan and is intended to serve as the implementation reference for command-by-command migration.

## Shared conventions

All commands should follow these patterns:

- Primary file input: positional argument(s)
- When the data format is known, use a format-aware positional name such as `input_oem`, `input_tle`, `input_omm`, or `input_csv`; otherwise use the generic `input_file`
- Output path: `-o, --output` with `-` meaning stdout
- Verbose logging: `-v, --verbose`
- Developer detail: `--debug`
- Time span: `--duration`
- Explicit interval bounds: `--start`, `--stop`
- Data-only output: `--data-only`
- Object naming: `--name`, `--object-name`, `--object-id` as appropriate
- Standard stdin/stdout sentinel: `-` for both input and output when explicitly streaming data
- Boolean flags: prefer `--foo` / `--no-foo` consistently; do not mix styles across commands
- Preserve command-specific names only where the context is uniquely established, such as `--x-ref-frame`, `--x-aer`, `--x-csv`, and `--rot-fit-span`

---

## Shared parser architecture

The CLI layer should provide a common parser foundation that enforces the shared conventions while keeping each command's argument definition in a dedicated parser module:

- standard `ArgumentParser` configuration
- consistent help footer and examples
- shared duration/timestamp parsing
- consistent boolean handling
- validation of `-` as stdin/stdout sentinel
- standard `--output` file handling
- common error wording and validation messages
- command entry scripts should import `parse_arguments` from a sibling `<command>_cli.py` file

Recommended structure:

```python
# command_file.py
from .command_cli import parse_arguments


def main() -> None:
    args = parse_arguments()
    ...
```

```python
# command_cli.py
import argparse


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="...",
        epilog="Examples:\n  ...",
    )

    parser.add_argument("input_oem", nargs="?", ...)  # use input_<format> when known
    parser.add_argument("-o", "--output", ...)  # when applicable
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()
```

When the format is not known or not meaningfully constrained, fall back to `input_file`.

This pattern is now the project convention for command modules under `src/ephem_toolkit/*`.

---

## Standard help format

Every command should use the same high-level help skeleton:

```text
usage: command [OPTIONS] [ARGS]

<one-sentence description>

Options:
  input_file             Primary input file path or '-' for stdin
  -o, --output <path>    output file path; use '-' to write to stdout
  -v, --verbose          print extra diagnostic output
  --debug                print low-level debug details
  --help                 show this help message and exit

Examples:
  command data.oem --output out.omm
  command data.oem --output -
  command data.oem --time-slice 0,1h

Notes:
  - Use '-' for stdin/stdout when piping data
  - Default values are shown explicitly in option help
```

Help quality rules:

- every command must have a clear one-sentence description
- every option must have a concise, explicit description
- every option value placeholder in usage/help must follow the project pattern `<lower_case_desc>`
- use lowercase descriptive placeholders such as `<path>`, `<file>`, `<duration>`, `<start>`, `<stop>`, `<id>`, `<timestamp>`, and `<value>`
- avoid generic placeholders like `<VALUE>`, `ARG`, or `PATH` when a more specific lower-case descriptor is available
- defaults must be shown in help text for nontrivial values
- examples should be limited to 2-4 lines
- avoid overloaded prose and duplicated wording

The placeholder convention for option arguments is `<lower_case_desc>`, so usage text should read like `--output <path>`, `--duration <duration>`, `--satellite-id <id>`, and `--start <timestamp>`. This is the expected pattern for all option arguments:

```text
--output <path>
--duration <duration>
--start <timestamp>
--stop <timestamp>
--object-id <id>
--name <name>
--format <format>
```

The value in angle brackets should describe the argument's meaning, not just its type. Prefer `<path>` over `<VALUE>`, `<id>` over `<ID>`, and `<timestamp>` over `<arg>`.

---

## Command matrix

| Command | Target style | Notes |
| --- | --- | --- |
| `diff-oem` | `diff-oem [OPTIONS] <reference.oem> <comparison.oem>` | Keep positional file inputs; standardize rotation/time-shift names; keep `--rot-fit-span` as-is |
| `slice-oem` | `slice-oem [OPTIONS] <file.oem>` | Keep primary file input positional; preserve `--slice` and `--time-slice`; standardize interpolation boolean style |
| `xform-oem` | `xform-oem [OPTIONS] <file.oem>` | Keep positional input and established `--x-*` transformation flags; standardize surrounding help text |
| `oem-to-omm` | `oem-to-omm [OPTIONS] <file.oem>` | Keep positional input; standardize `--output` semantics; choose a single mode convention or consistent explicit flags |
| `download-tle` | `download-tle [OPTIONS] --satellite-id <id> [--satellite-id <id> ...]` | Use explicit satellite IDs; add `--output-dir`; standardize format values |
| `omm-to-tle` | `omm-to-tle [OPTIONS] <file.omm>` | Keep positional input; align with other conversion commands |
| `tle-to-omm` | `tle-to-omm [OPTIONS] <file.tle>` | Keep positional input; align with conversion-family conventions |
| `tle-info` | `tle-info [OPTIONS] TLE_FILE [TLE_FILE ...]` | Keep positional file arguments consistent with file-collection commands |
| `propagate-orbit` | `propagate-orbit [OPTIONS]` | Standardize to `--initial-state` or `--input-state`, `--duration`, `--output`, and perturbation toggles |
| `propagate-kepler` | `propagate-kepler [OPTIONS]` | Match propagation-family conventions exactly |
| `propagate-tle` | `propagate-tle [OPTIONS]` | Match propagation-family conventions while retaining TLE-specific inputs |
| `plot-orbit` | `plot-orbit [OPTIONS] <file.oem>` | Keep primary input positional; standardize plot output flags |
| `plot-orbit-deltas` | `plot-orbit-deltas [OPTIONS] <reference.oem> <comparison.oem>` | Keep positional compare semantics explicit and readable |
| `plot-dependent-variables` | `plot-dependent-variables [OPTIONS] <dep_vars.csv>` | Keep positional input; align with plotting-family conventions |

---

## Detailed command notes

### `diff-oem`

Purpose:
- compare two OEM files and report state differences

Target syntax:

```text
diff-oem [OPTIONS] <reference.oem> <comparison.oem>
```

Recommended alignment:
- keep the primary file inputs positional
- standardize rotation/time-shift names to a consistent family such as `--rotate`, `--rotate-xy`, `--rotate-z`, and `--time-shift`
- keep `--rot-fit-span` as the established duration name
- align interpolation flags with project-wide boolean naming

### `slice-oem`

Purpose:
- extract a subset of an OEM by index or time range

Target syntax:

```text
slice-oem [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary input positional
- keep `--slice` and `--time-slice`
- standardize interpolation to a single boolean style such as `--interpolate` / `--no-interpolate`
- use consistent duration examples and help text

### `xform-oem`

Purpose:
- transform reference frames or convert to AER coordinates

Target syntax:

```text
xform-oem [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary file input positional
- preserve established `--x-ref-frame`, `--x-aer`, and `--x-csv` transformation flags
- standardize surrounding output/input help wording without renaming transform-specific options
- ensure `--data-only` is described the same way as in other output commands

### `oem-to-omm`

Purpose:
- convert OEM state vectors into Keplerian/OMM/TLE output

Target syntax:

```text
oem-to-omm [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary input positional
- standardize on `--output` and other shared options
- prefer `--mode {kepler,mean-kepler,tle}` or keep explicit flags if the mode is important
- keep TLE metadata flags but normalize their naming and help text

### `download-tle`

Purpose:
- fetch TLE/OMM data for a set of satellite identifiers

Target syntax:

```text
download-tle [OPTIONS] --satellite-id <id> [--satellite-id <id> ...]
```

Recommended alignment:
- replace positional ID handling with explicit repeated satellite-ID options
- add `--output-dir`
- standardize allowed format values and default output behavior

### `omm-to-tle`

Purpose:
- convert OMM to TLE format

Target syntax:

```text
omm-to-tle [OPTIONS] <file.omm>
```

Recommended alignment:
- keep the primary file input positional
- follow the same output and metadata conventions as other conversion commands

### `tle-to-omm`

Purpose:
- convert TLE to OMM format

Target syntax:

```text
tle-to-omm [OPTIONS] <file.tle>
```

Recommended alignment:
- keep the primary file input positional
- follow the same conversion pattern as `oem-to-omm`

### `tle-info`

Purpose:
- inspect TLE parameters and derived orbital elements

Target syntax:

```text
tle-info [OPTIONS] TLE_FILE [TLE_FILE ...]
```

Recommended alignment:
- keep positional file arguments consistent with other file-collection commands
- standardize the help text and examples for multiple TLE inputs

### `propagate-orbit`

Purpose:
- propagate a state history with configurable perturbations and outputs

Target syntax:

```text
propagate-orbit [OPTIONS]
```

Recommended alignment:
- standardize input semantics as `--input-state` or `--initial-state`
- keep `--duration`, `--output`, and shared logging flags consistent
- use one boolean convention for perturbation toggles
- ensure all output-file options appear in the same help block

### `propagate-kepler`

Purpose:
- propagate a simple two-body or Keplerian orbit

Target syntax:

```text
propagate-kepler [OPTIONS]
```

Recommended alignment:
- match the propagation-family conventions exactly
- standardize duration, output, and effect toggles the same way as `propagate-orbit`

### `propagate-tle`

Purpose:
- propagate TLE input using SGP4-compatible behavior

Target syntax:

```text
propagate-tle [OPTIONS]
```

Recommended alignment:
- match the propagation-family conventions
- keep TLE-specific values but normalize their names and help text

### `plot-orbit`

Purpose:
- plot orbit geometry or state evolution

Target syntax:

```text
plot-orbit [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary file input positional
- standardize output and figure-output options
- keep plot-specific options distinct from core file-processing options

### `plot-orbit-deltas`

Purpose:
- compare orbit trajectories and plot differences

Target syntax:

```text
plot-orbit-deltas [OPTIONS] <reference.oem> <comparison.oem>
```

Recommended alignment:
- keep the primary file inputs positional
- keep compare semantics explicit and readable
- maintain a single help pattern across the plotting family

### `plot-dependent-variables`

Purpose:
- plot dependent variables from propagation output

Target syntax:

```text
plot-dependent-variables [OPTIONS] <dep_vars.csv>
```

Recommended alignment:
- keep the primary file input positional
- align option names and help text with the other plotting commands

---

## Implementation order

1. Define the canonical CLI naming rules in one shared helper layer
2. Refactor `src/ephem_toolkit/core/cli.py` to own common parser utilities
3. Update the highest-traffic commands first:
   - `diff-oem`
   - `slice-oem`
   - `xform-oem`
   - `oem-to-omm`
   - `propagate-orbit`
4. Normalize the remaining conversion and plotting commands
5. Review all help text, examples, and notes in one pass
6. Validate the `--help` output for each command

---

## Status tracking workflow

After each step in the implementation plan is completed, the completed details for that step should be moved into a dedicated status file. The details document should then contain only lightweight links to those status entries for finished tasks.

This means:

- finish a task
- move the full implementation notes and validation details to the status file
- keep the details document as a pointer file, not a duplicate record of completed work
- use short links for each finished item, such as `[diff-oem status](status.md#diff-oem)`

This keeps the planning documents clean while preserving the full history of completed work in the status file.

## Definition of done

The CLI cleanup is complete when all project commands use the same language for input, output, data rules, and help text, and the output of `--help` is clear, consistent, and readable across the entire toolkit.
