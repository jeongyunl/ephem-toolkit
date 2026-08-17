# CLI Unification Status

## Step 1 — shared CLI conventions (completed)

This step establishes the project-wide baseline for CLI naming, help patterns, and option-value placeholders.

### Included conventions

- primary file inputs stay positional when the format is known
- shared option names include `--output`, `--duration`, `--start`, `--stop`, `--verbose`, and `--debug`
- boolean flags prefer a single style, with `--foo` and `--no-foo` as the default convention
- format-aware names such as `input_oem`, `input_tle`, `input_omm`, and `input_csv` are used when appropriate
- generic fallback names such as `input_file` are reserved for unclear or mixed input types
- option value placeholders follow the project pattern `<lower_case_desc>`

### Placeholder examples

```text
--output <path>
--duration <duration>
--start <timestamp>
--stop <timestamp>
--object-id <id>
--name <name>
--format <format>
```

The placeholder value should describe the argument meaning, not a generic token. Prefer `<path>` over `<VALUE>`, `<id>` over `<ID>`, and `<timestamp>` over `<arg>`.

### Help wording rules

- all option help text should be concise and action-oriented
- option descriptions use lowercase wording
- usage lines and examples should stay short and practical
- error messages use the format `error: <problem>` followed by `try 'command --help' for usage.`
- warnings use the format `warning: <issue>; continuing with default behavior.`

### Status note

The active plan can now point to this file instead of keeping the detailed completion notes in the main details document.
