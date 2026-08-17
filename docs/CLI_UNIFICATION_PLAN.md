# CLI Unification Plan

## Goal

Streamline the command-line interface so every tool follows the same conventions for arguments, option naming, parsing, and help output. The objective is to make the project feel like one coherent toolkit rather than a collection of independent scripts with similar but non-uniform interfaces.

## Scope

This plan covers:

- CLI argument conventions and syntax
- CLI parsing code and argument names
- CLI help and usage messages
- consistency across all commands registered in `pyproject.toml`

## Current issues

The codebase already has a valid CLI layer, but it is inconsistent across commands:

- some commands use positional file arguments while others use `-i/--input`
- some use `-o/--output`, others embed output in positional conventions
- some commands use `--foo`, others use `--x-foo`, `--rot`, `--rot-xy`, `--time-shift`, or `--no-interpolate`
- boolean toggles are inconsistent across scripts
- help text varies in description style, examples, and default-value formatting

The result is a toolkit that works, but is harder to learn and harder to document.

---

## Target conventions

Use one standard CLI vocabulary for every command.

### Shared conventions

- Primary file input: positional argument(s)
- Output path: `-o, --output` with `-` meaning stdout
- Verbose logging: `-v, --verbose`
- Developer detail: `--debug`
- Time span: `--duration`
- Explicit interval bounds: `--start`, `--stop`
- Data-only output: `--data-only`
- Object naming: `--name`, `--object-name`, `--object-id` as appropriate
- Standard stdin/stdout sentinel: `-` for both input and output when explicitly streaming data

### Naming rules

1. Prefer format-aware positional names when the file type is known.
   - Use `input_oem`, `input_tle`, `input_omm`, `input_csv`, etc. for primary file inputs when the file format is known and unambiguous.
   - Use the generic fallback `input_file` only when the input type is not known or not specific to one format.
   - Avoid names such as `oem_file`, `reference_oem`, `comparison_oem`, `tle_files`, and `x_ref_frame` when the project-standard positional naming is available.

2. Prefer generic nouns over script-specific names.
   - Prefer positional file arguments for primary file inputs, plus `output`, `format`, `duration`, `start`, `stop`
   - Keep the naming concise and consistent across commands.

3. Prefer consistent verbs and scope, while preserving command-specific transform names when they are already clear and established.
   - Use positional file arguments as the standard for input paths.
   - Keep `--x-ref-frame`, `--x-aer`, and `--x-csv` for `xform-oem` because they are explicit and unambiguous in the context of that command.
   - Use broader shared conventions elsewhere when they are not tied to a dedicated transformation command.

3. Prefer one boolean style per project.
   - Recommended: `--foo` and `--no-foo`
   - Alternative valid option: `--enable-foo` and `--disable-foo`
   - Do not mix styles across commands

4. Keep option names stable and descriptive.
   - Keep `--rot-fit-span` as the established name for the rotation-fit duration in `diff-oem`.
   - `--fit-span` is clearer for generic fitting commands.
   - `--satellite-id` is clearer than unstructured positional IDs.

---

## Shared parser architecture

Create a small shared CLI helper layer and use it across commands, while keeping each command's parser in a dedicated sibling module named `<command>_cli.py`.

### Shared helper responsibilities

- create standard `ArgumentParser` config
- apply the same help footer across commands
- parse common durations and timestamps
- parse bool flags consistently
- validate `-` as stdin/stdout sentinel
- standardize `--output` file handling
- expose consistent error messages
- keep parser logic separate from execution logic using dedicated CLI modules

### Recommended parser pattern

Each command entry script should delegate to its dedicated parser module:

```python
# command_file.py
from .command_cli import parse_arguments


def main() -> None:
    args = parse_arguments()
    ...
```

with the parser defined in a sibling file named `<command>_cli.py`:

```python
# command_cli.py
import argparse


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="...",
        epilog="Examples:\n  ...",
    )

    parser.add_argument("input_file", nargs="?", ...)  # primary positional file input
    parser.add_argument("-o", "--output", ...)  # when applicable
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()
```

Then add command-specific arguments after the common options.

---

## Standard help output format

Every CLI should present the same high-level help skeleton:

```text
usage: command [OPTIONS] [ARGS]

<one-sentence description>

Options:
  input_file             Primary input file path or '-' for stdin
  -o, --output <path>    Output file path; use '-' to write to stdout
  -v, --verbose          Print extra diagnostic output
  --debug                Print low-level debug details
  --help                 Show this help message and exit

Examples:
  command data.oem --output out.omm
  command data.oem --output -
  command data.oem --time-slice 0,1h

Notes:
  - Use '-' for stdin/stdout when piping data
  - Default values are shown explicitly in option help
```

### Help quality rules

- every command must have a clear one-sentence description
- every option must have a concise, explicit description
- every option value placeholder in usage/help must use the project pattern `<lower_case_desc>`
- use lowercase descriptive placeholders such as `<path>`, `<file>`, `<duration>`, `<start>`, `<stop>`, `<id>`, `<timestamp>`, and `<value>`
- avoid generic placeholders like `<VALUE>`, `ARG`, `FILE`, or `PATH` when a more specific lower-case descriptor is available
- defaults must be shown in help text for nontrivial values
- examples should be limited to 2-4 lines
- avoid overloaded prose and duplicated wording

The canonical placeholder style is `<lower_case_desc>`; for example, `--output <path>`, `--duration <duration>`, `--satellite-id <id>`, and `--start <timestamp>`. In other words, option arguments should be written as values that describe the data being supplied, not as generic tokens. For example:

```text
--output <path>
--duration <duration>
--start <timestamp>
--stop <timestamp>
--object-id <id>
--name <name>
--format <format>
```

This pattern keeps help output readable and makes each option argument self-describing.

---

## Command-by-command migration strategy

### 1) `diff-oem`

Current shape:
- positional `reference_oem` and `comparison_oem`
- `--rot`, `--rot-xy`, `--rot-z`, `--time-shift`
- `--interpolate-ref`, `--interpolate-data`
- `--rot-fit-span`, `--start`, `--stop`

Target shape:

```text
diff-oem [OPTIONS] <reference.oem> <comparison.oem>
```

Recommended alignment:
- keep primary file inputs positional
- rename long names to `--reference`, `--comparison` or `--ref-file`, `--cmp-file` only if needed for clarity, but prefer positional inputs as the default
- rename transform flags to a consistent family such as:
  - `--rotate`
  - `--rotate-xy`
  - `--rotate-z`
  - `--time-shift`
- keep `--rot-fit-span` as-is

### 2) `slice-oem`

Current shape:
- positional `oem_file`
- `-s/--slice` and `-t/--time-slice`
- `--interpolate` and `--no-interpolate`

Target shape:

```text
slice-oem [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary file input positional
- keep `--slice` and `--time-slice`
- standardize on `--output` and one boolean style for interpolation

### 3) `xform-oem`

Current shape:
- positional `oem_file`
- `--x-ref-frame`, `--x-aer`, `--x-csv`
- `--set-meta`, `--set-header`

Target shape:

```text
xform-oem [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary file input positional
- keep the established `--x-*` transformation flags for this command (`--x-ref-frame`, `--x-aer`, `--x-csv`)
- standardize surrounding input/output conventions and help descriptions without renaming the transformation-specific options
- ensure `--data-only` is described exactly the same as in other file-writing commands

### 4) `oem-to-omm`

Current shape:
- positional `oem_file`
- `--kepler`, `--mean-kepler`, `--tle`
- many TLE-specific metadata flags

Target shape:

```text
oem-to-omm [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary file input positional
- standardize to `--output` and other shared options
- use `--mode {kepler,mean-kepler,tle}` or keep explicit flags if the mode is important
- keep TLE metadata names but standardize the long option prefix and help descriptions

### 5) `download-tle`

Current shape:
- positional `satellite_ids`
- `--format`

Target shape:

```text
download-tle [OPTIONS] --satellite-id <id> [--satellite-id <id> ...]
```

Recommended alignment:
- move to explicit satellite ID option(s)
- add `--output-dir`
- standardize allowed format values
- ensure required output dir and default behavior are clear in help text

### 6) `omm-to-tle`

Target shape:

```text
omm-to-tle [OPTIONS] <file.omm>
```

Recommended alignment:
- keep the primary file input positional
- follow the same output and metadata conventions as other conversion commands

### 7) `tle-to-omm`

Target shape:

```text
tle-to-omm [OPTIONS] <file.tle>
```

Recommended alignment:
- keep the primary file input positional
- follow the same conversion pattern as `oem-to-omm`

### 8) `tle-info`

Current shape:
- positional `tle_files`

Target shape:

```text
tle-info [OPTIONS] TLE_FILE [TLE_FILE ...]
```

Recommended alignment:
- either keep positional file arguments or normalize to `--input` style
- if positional is kept, keep the order and usage consistent with all other file-collection commands

### 9) `propagate-orbit`

Current shape:
- `-i/--initial-state`, `-d/--duration`, `--oem`, `--data-only`, `--dep-vars`
- many physical model options and perturbation toggles

Target shape:

```text
propagate-orbit [OPTIONS]
```

Recommended alignment:
- standardize to `--input-state` or `--initial-state`
- keep `--duration` and `--output`
- use one consistent convention for enabled/disabled perturbations
- ensure all output-file options are in the same help block as other commands

### 10) `propagate-kepler`

Target shape:

```text
propagate-kepler [OPTIONS]
```

Recommended alignment:
- match the propagation command family exactly
- same conventions for duration, output, state input, and effect toggles

### 11) `propagate-tle`

Target shape:

```text
propagate-tle [OPTIONS]
```

Recommended alignment:
- match the same propagation family conventions
- keep TLE-specific values but map them to a shared parser and help format

### 12) `plot-orbit`

Target shape:

```text
plot-orbit [OPTIONS] <file.oem>
```

Recommended alignment:
- keep the primary file input positional
- standardize output and figure-output options
- keep plot-specific options distinct from core file-processing options

### 13) `plot-orbit-deltas`

Target shape:

```text
plot-orbit-deltas [OPTIONS] <reference.oem> <comparison.oem>
```

Recommended alignment:
- keep the primary file inputs positional
- keep compare semantics explicit and readable
- maintain a single help pattern across the plotting family

### 14) `plot-dependent-variables`

Target shape:

```text
plot-dependent-variables [OPTIONS] <dep_vars.csv>
```

Recommended alignment:
- keep the primary file input positional
- align with the general plotting command family
- standardize option names and help text with the other plot commands

---

## Implementation order

1. Define shared CLI conventions in one place
2. Refactor the shared helper layer in `src/ephem_toolkit/core/cli.py`
3. Update the highest-traffic commands first:
   - `diff-oem`
   - `slice-oem`
   - `xform-oem`
   - `oem-to-omm`
   - `propagate-orbit`
4. Update the remaining conversion and plotting commands
5. Review all help text and examples in a single pass
6. Validate with `--help` output for each command

### Status tracking workflow

After each step is completed, the details for that step should be moved into a dedicated status file. The main details document should not keep long-form finished task notes; it should instead contain only lightweight links to status entries for tasks that are complete.

In other words:

- complete a step
- move the completed details to the status file
- keep the details file focused on pointers to finished work
- for each finished task, add a brief link such as `[completed: diff-oem](CLI_STATUS.md#step-1---shared-cli-conventions)`

This keeps the plan concise while preserving a full record of completed work in the status file.

Completed step pointer:
- [Step 1 status](CLI_STATUS.md#step-1---shared-cli-conventions)

---

## Success criteria

The CLI is considered unified when all commands satisfy the following:

- same option naming pattern
- same input/output language across commands
- same boolean toggle style
- same help skeleton and usage wording
- same default-value and unit formatting
- consistent examples and notes

At that point, the toolkit reads as one product instead of many independent utilities.
