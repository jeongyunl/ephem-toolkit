# Poetry Packaging Plan

## Goal

Package the repository's Python libraries and command-line tools with Poetry. The result should be installable in an isolated environment, usable through stable console commands, testable from a clean checkout, and ready for publication when the package boundary is agreed.

## Current Constraints

- The repository mixes Python modules, executable scripts, tests, and sample data.
- Reusable Python code is spread across `common/`, `diff_oem/`, `oem_to_omm/`, `plotting/`, and `propagation/`.
- User-facing scripts currently live in `bin/` and in domain directories and are commonly run directly with `python3`.
- TudatPy and NumPy are used by only some workflows, so dependency groups or optional extras may be preferable to forcing every install to include every heavy dependency.
- Existing tests and documentation are part of the compatibility contract.

## Recommended Packaging Shape

Use a `src/` layout for the distributable Python package, with an explicit package name such as `tudatpy_utils`. Move or copy reusable modules into that package in a focused migration. Keep `bin/` as a compatibility layer during the transition, then make those scripts call the packaged functions or console entry points.

The first Poetry package should cover the Python libraries and scripts only.

## Step-by-Step Implementation Plan

### 1. Inventory the public surface

- List every Python module imported outside its own directory.
- Identify package directories that need `__init__.py` files.
- Record each executable script, its current invocation, input/output behavior, and its documented name.
- Identify runtime dependencies by import and by execution path: standard library, NumPy, TudatPy, SGP4, SciPy, Matplotlib, and any others actually required.
- Mark scripts that depend on local working-directory behavior or untracked data files.
- Capture a baseline from the existing test commands and representative CLI invocations.

**Deliverable:** a packaging inventory and a list of compatibility-sensitive commands.

### 2. Agree on package and command names

- Choose the distribution name (`tudatpy-utils` is the likely project name).
- Choose the import package name (`tudatpy_utils` or a documented set of existing top-level packages).
- Decide whether existing top-level imports such as `common` remain supported or become deprecated aliases.
- Define canonical console commands for OEM, TLE, OMM, propagation, and plotting workflows.

**Deliverable:** a short public API and CLI compatibility decision recorded in the status document.

### 3. Introduce Poetry metadata

- Add `pyproject.toml` using Poetry's current package configuration.
- Declare the supported Python version and the minimum versions for direct runtime dependencies.
- Separate core dependencies from optional workflow dependencies where practical.
- Define development dependencies for pytest, coverage, formatting, linting, and type checking based on tools actually adopted by the repository.
- Configure package inclusion and include required non-Python files explicitly rather than relying on repository-relative paths.
- Add project metadata, README reference, license field if applicable, and repository URLs.
- Generate and commit `poetry.lock` after dependency choices are reviewed.

**Deliverable:** a clean `poetry install` creates a usable development environment.

### 4. Establish the importable package layout

- Create the selected package directory under `src/`.
- Move reusable modules in small groups, preserving public function names initially.
- Replace filesystem-relative imports and script-directory assumptions with package imports and `importlib.resources` where data is packaged.
- Add explicit package exports only for APIs intended to be public.
- Keep compatibility wrappers where moving modules would otherwise break documented imports.
- Update tests to import the package rather than relying on the checkout directory being on `sys.path`.

**Deliverable:** imports work from an installed wheel, an editable install, and a clean checkout.

### 5. Convert scripts into console entry points

- Add small `main()` functions where scripts currently execute work at import time.
- Register one console script per supported workflow in `pyproject.toml`.
- Make console scripts call library functions and return meaningful exit codes.
- Preserve existing argument names, stdin handling, output formats, and error behavior unless a compatibility change is explicitly approved.
- Keep `bin/` wrappers temporarily, forwarding to the new entry points or shared `main()` functions.
- Update every affected README and domain document with installed-command examples.

**Deliverable:** commands work after `poetry install` without invoking files by path.

### 6. Package data and external resources

- Locate leap-second tables, Earth-orientation data, sample templates, and other runtime resources.
- Decide which resources belong in the wheel and which must be downloaded or configured externally.
- Use package-resource APIs instead of `Path(__file__).parent` assumptions for included data.
- Add tests that load each packaged resource from an installed artifact.
- Document environment variables, cache locations, and network requirements.

**Deliverable:** resource-dependent workflows behave the same from an editable install and a built wheel.

### 7. Validate the distribution

- Run the full Python test suite inside the Poetry environment.
- Build sdist and wheel artifacts with Poetry.
- Install the wheel into a fresh environment with no repository path on `PYTHONPATH`.
- Run smoke tests for every registered console command, including representative OEM/TLE/OMM and plotting workflows.
- Inspect wheel contents for missing modules, unwanted build files, and accidental data omissions.
- Add a CI job that fails if the lock file is stale or the built artifact cannot be installed.

**Deliverable:** reproducible, clean-install validation evidence recorded in the status document.

### 8. Publish and maintain

- Choose the package index and configure trusted publishing or token-based publishing outside the repository.
- Add release-versioning and changelog rules.
- Publish a test release before a production release.
- Deprecate direct `bin/` execution only after console commands are documented and verified.
- Remove compatibility wrappers only in a planned breaking release.

**Deliverable:** a repeatable release checklist and a documented deprecation path.

## Suggested Validation Commands

```text
poetry check
poetry install
poetry run pytest
poetry build
python -m venv /tmp/tudatpy-utils-wheel-check
/tmp/tudatpy-utils-wheel-check/bin/pip install dist/*.whl
/tmp/tudatpy-utils-wheel-check/bin/python -c "import tudatpy_utils"
```

Replace the import smoke test and command names after the package-boundary decision in Step 2.

## Definition Of Done

- `pyproject.toml` and a reviewed `poetry.lock` are present.
- A clean environment can install the wheel without the repository on `PYTHONPATH`.
- Public imports and documented commands are either preserved or explicitly documented as changed.
- Required package data is available from the installed artifact.
- Python tests pass in the Poetry environment.
- CI builds and installs the package before release.
- The status document records the final package name, command map, supported Python versions, and known limitations.