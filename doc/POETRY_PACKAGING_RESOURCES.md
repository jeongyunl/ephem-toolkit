# Poetry Packaging Resources

Last updated: 2026-08-10

## Resource Policy

The initial Poetry wheel contains Python modules only. No repository-owned runtime data is currently required by the in-scope Python package.

| Resource type | Current owner | Package treatment |
| --- | --- | --- |
| OEM, OMM, TLE, and CSV files under `tests/data/` | Tests and examples | Keep outside the wheel as test fixtures. Tests resolve them relative to the test files. |
| User-provided OEM, OMM, TLE, and CSV inputs | CLI users | Read from explicit paths or stdin; never package them. |
| SPICE kernels | TudatPy data installation | Resolve through `tudatpy.data.get_spice_kernel_path()` and cache the directory under `$XDG_CACHE_HOME/tudatpy-utils/` or `~/.cache/tudatpy-utils/`. Do not duplicate kernels in the wheel. |
| CMake/native build outputs | Native build system | Outside the Python distribution. |

## Packaging Rules

- Keep package discovery limited to the Python packages declared in `pyproject.toml`.
- Do not add `tests/data/`, `build/`, `dist/`, or user-generated orbit files to package data.
- If a future workflow needs repository-owned templates or lookup tables, add them under the owning Python package and load them with `importlib.resources`.
- If a future resource must be downloaded, document its source, cache location, versioning, and offline failure behavior before adding it to a workflow.

## Validation

The package smoke test in `tests/test_packaging_resources.py` verifies that the installed `tudatpy_utils` root is accessible through `importlib.resources`. Wheel inspection must also confirm that test fixtures and build artifacts are absent.
