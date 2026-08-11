# Poetry Packaging Status

Last updated: 2026-08-10

## Overall Status

**Step 8 complete; full-suite dependency blocker remains.** This document tracks the implementation of [POETRY_PACKAGING_PLAN.md](POETRY_PACKAGING_PLAN.md). Distribution build, clean-wheel installation, smoke validation, CI packaging checks, and the release procedure are present.

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
- [x] Add console entry points and compatibility wrappers.
- [x] Package and test runtime data resources.
- [x] Update README and domain documentation with installed-command examples.
- [x] Generate and review `poetry.lock`.
- [x] Build and install a wheel in a clean environment.
- [ ] Run Python tests in Poetry; currently blocked by external TudatPy/`astropy` dependencies.
- [x] Add CI packaging and clean-install checks.
- [x] Define release, versioning, and `bin/` deprecation procedures in [POETRY_PACKAGING_RELEASE.md](POETRY_PACKAGING_RELEASE.md).

## Decisions To Record

| Decision | Current value | Owner/status |
| --- | --- | --- |
| Distribution name | `tudatpy-utils` | Decided in Step 2 |
| Import package name | `tudatpy_utils` | Decided in Step 2 |
| Supported Python versions | `>=3.9,<4.0` (CI: 3.9 and 3.13) | Current package policy; review with dependency changes |
| Console command names | 15 lowercase hyphenated commands | Decided in Step 2 |
| Optional dependency groups | Core NumPy; `plotting` extra; TudatPy external prerequisite | Updated in Step 3 |
| Compatibility period for `bin/` | Supported during migration; deprecate for at least one minor release before removal in a major release | Recorded in [POETRY_PACKAGING_RELEASE.md](POETRY_PACKAGING_RELEASE.md) |

## Current Findings

- Step 1 inventory is recorded in [POETRY_PACKAGING_INVENTORY.md](POETRY_PACKAGING_INVENTORY.md).
- Step 2 decisions are recorded in the inventory's [Step 2 Decisions](POETRY_PACKAGING_INVENTORY.md#step-2-decisions) section.
- The baseline command `python3 -m pytest --collect-only -q` collected 607 tests in 1.23 seconds on 2026-08-10.
- Python functionality in scope is distributed across `src/common/`, `src/diff_oem/`, `src/oem_to_omm/`, `plotting/`, `propagation/`, and `bin/`.
- The `time_conversion/` directory is explicitly outside the Poetry packaging plan.
- Existing documentation presents direct script execution as a supported workflow.
- `diff_oem/` is already organized as a reusable module with a separate CLI wrapper.
- There is no existing `pyproject.toml`, Poetry lock file, or declared Python package metadata.
- The target package namespace is `tudatpy_utils`, with existing top-level imports retained temporarily as compatibility surfaces.
- Step 4 currently exposes the canonical namespace through an import bridge over the packaged legacy domains; physical source relocation remains a future cleanup option.
- `poetry build` produces sdist and wheel artifacts, and isolated wheel imports pass for canonical and legacy package paths when NumPy is installed.
- `poetry install` plus canonical import smoke tests pass in the editable Poetry environment.
- All 15 canonical console commands are installed; lightweight and plotting commands pass `--help` smoke tests.
- The target console command names are lowercase and hyphenated; underscore aliases will not be registered initially.
- `poetry check` passes with the PEP 621 metadata configuration.
- `poetry lock` succeeds and `poetry install --no-root` installs the locked core/development dependencies.
- TudatPy is not in the lock file because no `tudatpy` package is available from the configured package index; TudatPy workflows still require an external installation method.
- Resource policy is recorded in [POETRY_PACKAGING_RESOURCES.md](POETRY_PACKAGING_RESOURCES.md): the wheel contains Python modules only, test fixtures remain outside the wheel, and SPICE kernels remain TudatPy-managed external data.
- `test/test_packaging_resources.py` verifies the installed package root through `importlib.resources`.
- Wheel inspection found no test fixtures or generated data/build files.
- `poetry build` and a fresh virtual-environment wheel install passed; package imports, resource access, and representative console commands succeeded.
- `.github/workflows/poetry-package.yml` validates metadata, installs dependencies, runs the package-resource test, builds the distribution, and clean-installs the wheel on Python 3.9 and 3.13.
- Step 8 release, TestPyPI, production publishing, compatibility, and maintenance procedures are recorded in [POETRY_PACKAGING_RELEASE.md](POETRY_PACKAGING_RELEASE.md).

## Risks And Open Questions

- Moving modules may break existing top-level imports and scripts that depend on the checkout working directory.
- TudatPy is not available from the configured package index and needs a documented external installation path.
- Some runtime data may not currently have a clear package-data owner.
- CLI names and behavior are not yet unified; packaging should preserve behavior before attempting broader CLI cleanup.
- Supported Python versions and the compatibility-wrapper deprecation timeline remain open for the next steps.
- Three Poetry-environment test collection failures require external TudatPy support and its transitive `astropy` dependency; 583 tests collect before those failures.
- TudatPy-dependent console commands remain unverified until the external TudatPy/astropy environment is available.
- The full Poetry suite remains blocked during collection by missing `astropy` inside external TudatPy; the current result is 3 collection errors after the package environment reaches 583 tests.
- README and affected domain documents now identify canonical Poetry commands while preserving direct script examples as compatibility forms.
- No package-owned runtime templates or lookup tables were found, so no package-data inclusion rules were added.

## Work Log

| Date | Change | Validation | Result |
| --- | --- | --- | --- |
| 2026-08-10 | Added initial plan and status documents, then excluded `time_conversion/`. | Reviewed README, TODO, and Python module documentation. | Python packaging scope established; implementation remains pending. |
| 2026-08-10 | Completed Step 1 inventory and recorded the Python test baseline. | `python3 -m pytest --collect-only -q` collected 607 tests in 1.23 seconds. | Step 1 complete; package and command naming decisions remain pending. |
| 2026-08-10 | Completed Step 2 package, import, dependency-extra, console-command, and compatibility decisions. | Reviewed the Step 1 inventory and recorded the 15-command map. | Step 2 complete; Poetry metadata is the next implementation step. |
| 2026-08-10 | Added PEP 621 Poetry metadata and generated `poetry.lock`. | `poetry check`, `poetry lock`, and `poetry install --no-root` passed; TudatPy package-index resolution was tested and unavailable. | Step 3 complete; source package layout is the next implementation step. |
| 2026-08-10 | Added `src/tudatpy_utils`, package markers, and a transitional namespace bridge over legacy domains. | `poetry build`, isolated wheel imports, `poetry install`, and editable canonical imports passed. | Step 4 complete; console entry points are the next implementation step. |
| 2026-08-10 | Registered 15 Poetry console commands and added the canonical command table to README. | `poetry check`, `poetry install`, all command wrappers installed; plotting extra smoke tests passed. | Entry-point implementation complete; remaining Step 5 work is broader domain-document migration and TudatPy validation. |
| 2026-08-10 | Added canonical command notes to affected domain documentation. | Reviewed command references in eight Markdown documents; legacy examples remain intact. | Step 5 complete; package-data handling is the next implementation step. |
| 2026-08-10 | Added package-resource policy and installed-resource smoke test. | `poetry run pytest -q test/test_packaging_resources.py` passed; wheel contained no test fixtures or generated data files. | Step 6 complete; distribution validation is the next implementation step. |
| 2026-08-10 | Validated the built wheel and added the Poetry packaging CI workflow. | `poetry check`, clean wheel install, imports, resources, and representative commands passed; full suite stopped at 3 external TudatPy/astropy collection errors. | Step 7 distribution checks are implemented; full Python test validation remains blocked by external dependencies. |
| 2026-08-10 | Added the release and maintenance procedure for the Python distribution. | Reviewed versioning, TestPyPI, production publishing, artifact inspection, compatibility, and `bin/` deprecation rules. | Step 8 complete; production publishing remains an operational action requiring repository credentials and an approved package index. |