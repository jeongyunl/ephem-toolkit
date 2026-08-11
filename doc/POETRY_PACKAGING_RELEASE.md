# Poetry Packaging Release Procedure

This procedure covers the Python distribution only. The `time_conversion/`
directory and its CMake release process are outside this procedure.

## Release Policy

- The distribution version is the single release identifier and follows
  semantic versioning: patch releases fix compatible behavior, minor releases
  add compatible functionality, and major releases may remove compatibility
  surfaces.
- Update the version in `pyproject.toml` and add a dated entry to the project
  changelog before building a release.
- Keep `poetry.lock` synchronized with `pyproject.toml`; do not update it as a
  side effect of an unrelated release.
- TudatPy remains an external prerequisite until a supported package source
  and compatible dependency policy are agreed.

## Pre-release Checklist

Run from a clean checkout with the intended Python version:

```text
poetry check
poetry install
poetry run pytest -q test/test_packaging_resources.py
poetry build
```

Also verify the wheel in a fresh virtual environment without the repository on
`PYTHONPATH`, and run representative `--help` checks for the registered
commands. The full suite should be run when the external TudatPy and
`astropy` dependencies are available; otherwise record the collection blocker
in the release notes.

Inspect both artifacts before publishing:

```text
unzip -l dist/*.whl
tar -tzf dist/*.tar.gz
```

The artifacts must contain the intended Python packages and metadata, and must
not contain `time_conversion/`, test fixtures, generated build output, or
local credentials.

## Test Release

Publish the first release candidate to TestPyPI and install it into a clean
environment using the TestPyPI index plus the configured dependency index.
Verify imports, package resources, and representative commands before any
production upload. Credentials and repository authentication belong in the
developer or CI secret store, not in tracked files.

## Production Release

1. Confirm the version, changelog entry, lock file, and release checklist.
2. Build fresh sdist and wheel artifacts with `poetry build`.
3. Publish through the configured trusted-publishing workflow when available;
   otherwise use an explicitly scoped token outside the repository.
4. Install the published version in a clean environment and repeat the smoke
   checks.
5. Create the corresponding repository release and retain the artifact and
   validation logs.

## Compatibility And Deprecation

- The 15 hyphenated console commands are canonical.
- Existing direct script paths under `bin/` remain supported while the
  console-command migration is documented and validated.
- New documentation should use console commands. Existing direct-invocation
  examples may remain as compatibility examples.
- When a future release begins deprecating direct `bin/` execution, add a
  deprecation notice to the affected command documentation and retain the
  wrappers for at least one minor release.
- Remove `bin/` compatibility wrappers only in a planned major release, with
  a changelog entry and migration instructions.

## Maintenance

- Keep the Python version matrix in CI aligned with the supported classifiers
  in `pyproject.toml`.
- Review dependency constraints and the external TudatPy installation path at
  each minor release.
- Re-run wheel-content inspection whenever package layout or resource policy
  changes.