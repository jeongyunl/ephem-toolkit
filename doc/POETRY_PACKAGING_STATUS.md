# Poetry Packaging Status

Last updated: 2026-08-10

## Overall Status

**Step 4 complete; Step 5 pending.** This document tracks the implementation of [POETRY_PACKAGING_PLAN.md](POETRY_PACKAGING_PLAN.md). Poetry metadata, a lock file, and a transitional importable package layout are present.

## Checklist

- [x] Inventory reusable modules, scripts, imports, data files, and runtime dependencies.
- [x] Record baseline Python tests and representative CLI smoke tests.
- [x] Decide the distribution name and import package name.
- [x] Record which existing imports and commands remain compatibility-supported.
- [x] Decide whether TudatPy, SciPy, Matplotlib, and SGP4 are core dependencies or optional workflow extras.
- [x] Exclude `time_conversion/` from the Poetry packaging scope.
- [x] Add and review `pyproject.toml`.
- [x] Create the selected `src/` package layout.
- [x] Migrate reusable modules and repair package imports through the transitional namespace bridge.
- [ ] Add console entry points and compatibility wrappers.
- [ ] Package and test runtime data resources.
- [ ] Update README and domain documentation with installed-command examples.
- [x] Generate and review `poetry.lock`.
- [ ] Build and install a wheel in a clean environment.
- [ ] Run Python tests in Poetry.
- [ ] Add CI packaging and clean-install checks.
- [ ] Define release, versioning, and `bin/` deprecation procedures.

## Decisions To Record

| Decision | Current value | Owner/status |
| --- | --- | --- |
| Distribution name | `tudatpy-utils` | Decided in Step 2 |
| Import package name | `tudatpy_utils` | Decided in Step 2 |
| Supported Python versions | TBD | Pending dependency review |
| Console command names | 15 lowercase hyphenated commands | Decided in Step 2 |
| Optional dependency groups | Core NumPy; `plotting` extra; TudatPy external prerequisite | Updated in Step 3 |
| Compatibility period for `bin/` | TBD | Pending migration plan |

## Current Findings

- Step 1 inventory is recorded in [POETRY_PACKAGING_INVENTORY.md](POETRY_PACKAGING_INVENTORY.md).
- Step 2 decisions are recorded in the inventory's [Step 2 Decisions](POETRY_PACKAGING_INVENTORY.md#step-2-decisions) section.
- The baseline command `python3 -m pytest --collect-only -q` collected 607 tests in 1.23 seconds on 2026-08-10.
- Python functionality in scope is distributed across `common/`, `diff_oem/`, `oem_to_omm/`, `plotting/`, `propagation/`, and `bin/`.
- The `time_conversion/` directory is explicitly outside the Poetry packaging plan.
- Existing documentation presents direct script execution as a supported workflow.
- `diff_oem/` is already organized as a reusable module with a separate CLI wrapper.
- There is no existing `pyproject.toml`, Poetry lock file, or declared Python package metadata.
- The target package namespace is `tudatpy_utils`, with existing top-level imports retained temporarily as compatibility surfaces.
- Step 4 currently exposes the canonical namespace through an import bridge over the packaged legacy domains; physical source relocation remains a future cleanup option.
- `poetry build` produces sdist and wheel artifacts, and isolated wheel imports pass for canonical and legacy package paths when NumPy is installed.
- `poetry install` plus canonical import smoke tests pass in the editable Poetry environment.
- The target console command names are lowercase and hyphenated; underscore aliases will not be registered initially.
- `poetry check` passes with the PEP 621 metadata configuration.
- `poetry lock` succeeds and `poetry install --no-root` installs the locked core/development dependencies.
- TudatPy is not in the lock file because no `tudatpy` package is available from the configured package index; TudatPy workflows still require an external installation method.

## Risks And Open Questions

- Moving modules may break existing top-level imports and scripts that depend on the checkout working directory.
- TudatPy is not available from the configured package index and needs a documented external installation path.
- Some runtime data may not currently have a clear package-data owner.
- CLI names and behavior are not yet unified; packaging should preserve behavior before attempting broader CLI cleanup.
- Supported Python versions and the compatibility-wrapper deprecation timeline remain open for the next steps.
- Three Poetry-environment test collection failures require external TudatPy support and its transitive `astropy` dependency; 583 tests collect before those failures.

## Work Log

| Date | Change | Validation | Result |
| --- | --- | --- | --- |
| 2026-08-10 | Added initial plan and status documents, then excluded `time_conversion/`. | Reviewed README, TODO, and Python module documentation. | Python packaging scope established; implementation remains pending. |
| 2026-08-10 | Completed Step 1 inventory and recorded the Python test baseline. | `python3 -m pytest --collect-only -q` collected 607 tests in 1.23 seconds. | Step 1 complete; package and command naming decisions remain pending. |
| 2026-08-10 | Completed Step 2 package, import, dependency-extra, console-command, and compatibility decisions. | Reviewed the Step 1 inventory and recorded the 15-command map. | Step 2 complete; Poetry metadata is the next implementation step. |
| 2026-08-10 | Added PEP 621 Poetry metadata and generated `poetry.lock`. | `poetry check`, `poetry lock`, and `poetry install --no-root` passed; TudatPy package-index resolution was tested and unavailable. | Step 3 complete; source package layout is the next implementation step. |
| 2026-08-10 | Added `src/tudatpy_utils`, package markers, and a transitional namespace bridge over legacy domains. | `poetry build`, isolated wheel imports, `poetry install`, and editable canonical imports passed. | Step 4 complete; console entry points are the next implementation step. |