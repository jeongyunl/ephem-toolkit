# Poetry Packaging Status

Last updated: 2026-08-10

## Overall Status

**Step 1 complete; Step 2 pending.** This document tracks the implementation of [POETRY_PACKAGING_PLAN.md](POETRY_PACKAGING_PLAN.md). No Poetry metadata or package migration has been added yet.

## Checklist

- [x] Inventory reusable modules, scripts, imports, data files, and runtime dependencies.
- [x] Record baseline Python tests and representative CLI smoke tests.
- [ ] Decide the distribution name and import package name.
- [ ] Record which existing imports and commands remain compatibility-supported.
- [ ] Decide whether TudatPy, SciPy, Matplotlib, and SGP4 are core dependencies or optional workflow extras.
- [x] Exclude `time_conversion/` from the Poetry packaging scope.
- [ ] Add and review `pyproject.toml`.
- [ ] Create the selected `src/` package layout.
- [ ] Migrate reusable modules and repair package imports.
- [ ] Add console entry points and compatibility wrappers.
- [ ] Package and test runtime data resources.
- [ ] Update README and domain documentation with installed-command examples.
- [ ] Generate and review `poetry.lock`.
- [ ] Build and install a wheel in a clean environment.
- [ ] Run Python tests in Poetry.
- [ ] Add CI packaging and clean-install checks.
- [ ] Define release, versioning, and `bin/` deprecation procedures.

## Decisions To Record

| Decision | Current value | Owner/status |
| --- | --- | --- |
| Distribution name | TBD, likely `tudatpy-utils` | Pending agreement |
| Import package name | TBD | Pending package-boundary review |
| Supported Python versions | TBD | Pending dependency review |
| Console command names | TBD | Pending CLI inventory |
| Optional dependency groups | TBD | Pending import and workflow inventory |
| Compatibility period for `bin/` | TBD | Pending migration plan |

## Current Findings

- Step 1 inventory is recorded in [POETRY_PACKAGING_INVENTORY.md](POETRY_PACKAGING_INVENTORY.md).
- The baseline command `python3 -m pytest --collect-only -q` collected 607 tests in 1.23 seconds on 2026-08-10.
- Python functionality in scope is distributed across `common/`, `diff_oem/`, `oem_to_omm/`, `plotting/`, `propagation/`, and `bin/`.
- The `time_conversion/` directory is explicitly outside the Poetry packaging plan.
- Existing documentation presents direct script execution as a supported workflow.
- `diff_oem/` is already organized as a reusable module with a separate CLI wrapper.
- There is no existing `pyproject.toml`, Poetry lock file, or declared Python package metadata.

## Risks And Open Questions

- Moving modules may break existing top-level imports and scripts that depend on the checkout working directory.
- TudatPy and scientific plotting dependencies may make a single minimal install unnecessarily large.
- Some runtime data may not currently have a clear package-data owner.
- CLI names and behavior are not yet unified; packaging should preserve behavior before attempting broader CLI cleanup.

## Work Log

| Date | Change | Validation | Result |
| --- | --- | --- | --- |
| 2026-08-10 | Added initial plan and status documents, then excluded `time_conversion/`. | Reviewed README, TODO, and Python module documentation. | Python packaging scope established; implementation remains pending. |
| 2026-08-10 | Completed Step 1 inventory and recorded the Python test baseline. | `python3 -m pytest --collect-only -q` collected 607 tests in 1.23 seconds. | Step 1 complete; package and command naming decisions remain pending. |