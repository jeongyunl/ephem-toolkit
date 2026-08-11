# Poetry Packaging Inventory

Last updated: 2026-08-10

This inventory completes Step 1 of [POETRY_PACKAGING_PLAN.md](POETRY_PACKAGING_PLAN.md). The `time_conversion/` directory is excluded from this inventory and from the Poetry packaging scope.

## Importable And Reusable Python Code

| Directory | Current package marker | Contents and packaging implication |
| --- | --- | --- |
| `common/` | No `__init__.py` | Shared modules: `aer.py`, `common.py`, `consts.py`, `convert_tle.py`, `frame_utils.py`, `kepler.py`, `mean_kepler.py`, `slice_oem.py`, `spice_utils.py`, `time_utils.py`, `tle.py`, and `wgs.py`. |
| `common/interpolator/` | Has `__init__.py` | Reusable `Interpolator` and `LagrangeInterpolator` implementations. |
| `common/ccsds/` | No `__init__.py` | CCSDS ODM/OEM/OMM definitions and parsers; currently relies on namespace-package behavior from the checkout. |
| `diff_oem/` | Has `__init__.py` | Reusable comparison pipeline: CLI parsing, comparison, transformations, output, data structures, and utilities. |
| `src/oem_to_omm/` | Has `__init__.py` | OEM-to-OMM fitting workflow and reusable TLE-fitting modules. |
| `src/oem_to_omm/fit_tle/` | Has `__init__.py` | TLE fitting models, estimation, linear algebra, refinement, and TLE construction. |
| `propagation/` | No `__init__.py` | Three propagation scripts; package conversion is needed if their functions become public imports. |
| `plotting/` | No `__init__.py` | Three plotting scripts; package conversion is needed if their functions become public imports. |

The current layout is not one installable package. `common/`, `common/ccsds/`, `propagation/`, and `plotting/` need an explicit package-boundary decision before Poetry metadata is added.

## Executable Scripts And Compatibility Commands

These are the current documented script entry points. Direct `python3 path/to/script.py` invocation is part of the existing workflow and should remain supported during migration through compatibility wrappers.

| Script | Current invocation shape | Primary behavior |
| --- | --- | --- |
| `bin/diff_oem.py` | `python3 bin/diff_oem.py <reference.oem> <comparison.oem> [options]` | Compare two OEM state histories and write differences/statistics. |
| `src/download_tle/download_tle.py` | `python3 src/download_tle/download_tle.py [--format FORMAT] <satellite-id> ...` | Download TLE or OMM data to files. |
| `bin/omm_to_tle.py` | `python3 bin/omm_to_tle.py <input.omm>` | Convert OMM input to TLE output. |
| `bin/slice_oem.py` | `python3 bin/slice_oem.py <oem> --slice START:STOP:STEP` | Slice an OEM stream or file. |
| `bin/tle_info.py` | `python3 bin/tle_info.py <file.tle> ...` | Print TLE metadata and derived orbital values. |
| `bin/tle_to_omm.py` | `python3 bin/tle_to_omm.py <input.tle>` | Convert TLE input to OMM output. |
| `bin/xform_oem.py` | `python3 bin/xform_oem.py <oem> --x-ref-frame FRAME [-o OUTPUT]` | Transform OEM states between supported frames or coordinate forms. |
| `src/oem_to_omm/oem_to_omm.py` | `python3 src/oem_to_omm/oem_to_omm.py --kepler\|--mean-kepler\|--tle <input.oem>` | Fit OEM states and emit an OMM. |
| `src/oem_to_omm/evaluate_fit_tle.py` | `python3 src/oem_to_omm/evaluate_fit_tle.py [--fit-span HOURS] <input.oem>` | Evaluate TLE fit quality. |
| `propagation/propagate_orbit.py` | `python3 propagation/propagate_orbit.py -i STATE [-d DURATION] [--oem OUTPUT]` | Propagate a Cartesian state with configured models. |
| `propagation/propagate_kepler.py` | `python3 propagation/propagate_kepler.py` | Propagate a two-body Kepler state. |
| `propagation/propagate_tle.py` | `python3 propagation/propagate_tle.py --tle FILE [-d DURATION]` | Propagate a TLE. |
| `plotting/plot_orbit.py` | `python3 plotting/plot_orbit.py --csv FILE` | Plot orbit and dependent-variable data. |
| `plotting/plot_orbit_deltas.py` | `python3 plotting/plot_orbit_deltas.py <oem> ...` | Plot orbit differences. |
| `plotting/plot_dependent_variables.py` | `python3 plotting/plot_dependent_variables.py --csv FILE` | Plot dependent variables. |

Common behavior includes stdin support through `-` or omitted input paths, stdout-oriented output, optional `-o/--output` file destinations, and CCSDS/OEM/TLE/OMM text formats.

## Dependency Inventory

| Dependency | Observed usage | Likely scope |
| --- | --- | --- |
| NumPy | Array operations, linear algebra, orbital calculations, fitting, and tests across `common/`, `diff_oem/`, `oem_to_omm/`, `propagation/`, and `plotting/`. | Core dependency for the full Python package. |
| TudatPy | Frame conversion, SPICE access, time/ephemeris helpers, SGP4-backed propagation, and orbit propagation. | External prerequisite for propagation, frame, SPICE, and TLE workflows; no Poetry dependency because no `tudatpy` distribution is available from the configured package index. |
| Matplotlib | Orbit, delta, and dependent-variable plotting scripts. | Optional plotting dependency unless plotting is part of the core install. |
| Python standard library | Argument parsing, paths, CSV/JSON, streams, dates, URL access, and formatting. | No package dependency. |
| SGP4 | No direct `sgp4` import was found in the inventory. SGP4 behavior is accessed through TudatPy. | Do not declare separately until a direct import is confirmed. |
| SciPy | No direct import was identified in the inventory. | Do not declare until a direct import is confirmed. |

Dependency declarations should be based on import and execution-path verification rather than on the repository's broad workflow list.

## Runtime Data And Path Assumptions

- Tests use files under `test/data/` through paths relative to each test file. The inventory includes OEM files, OMM/TLE pairs, and propagation CSV outputs.
- SPICE kernels are resolved through TudatPy and cached under `~/.cache/tudatpy-utils/` or `$XDG_CACHE_HOME`, rather than being packaged in this repository.
- Several scripts insert a repository parent directory into `sys.path` using `Path(__file__)`. This currently makes sibling top-level modules importable and will not be reliable from an installed wheel.
- Runtime code uses `pathlib` and does not rely on known absolute filesystem paths.
- Package-data decisions are needed for any future templates or runtime files that are not supplied by TudatPy. Test fixtures should remain test-only unless a user workflow requires them.

## Test Baseline

- Test files follow pytest's `test_*.py` discovery pattern under `test/`.
- Baseline command: `python3 -m pytest --collect-only -q`.
- Baseline result on 2026-08-10: **607 tests collected in 1.23 seconds**.
- Collection emitted an existing `urllib3` `NotOpenSSLWarning` because the local Python 3.9 build uses LibreSSL. This is an environment warning, not a packaging failure.
- The test suite covers bin subprocesses, common modules, interpolation, OEM-to-OMM fitting, plotting, and propagation.

Representative smoke commands are listed in the plan's source documentation and include OEM comparison, OEM slicing, frame transformation, TLE/OMM conversion, OEM-to-OMM fitting, TLE propagation, and plotting. These commands currently use repository-relative script paths and sample data.

## Compatibility-Sensitive Surface

- Existing direct script paths under `bin/`, `src/oem_to_omm/`, `propagation/`, and `plotting/` are documented interfaces.
- `sys.path` insertion in scripts is a migration blocker for isolated wheel installs.
- `common/slice_oem.py` and `bin/slice_oem.py` have the same stem but different roles; the package and CLI names must avoid ambiguity.
- OEM, OMM, TLE, CSV, and stdout formats are consumed by tests and shell pipelines. Formatting and column-order changes are compatibility risks.
- SPICE kernel filenames and TudatPy-managed cache resolution are runtime assumptions for frame and propagation workflows.
- Existing top-level imports such as `common.*`, `diff_oem.*`, and `oem_to_omm.*` may be used by tests or downstream scripts and need a compatibility policy.

## Step 2 Decisions

### Distribution And Import Names

- Distribution name: `tudatpy-utils`.
- Canonical import namespace: `tudatpy_utils`.
- Target package layout: `tudatpy_utils.common`, `tudatpy_utils.diff_oem`, `tudatpy_utils.oem_to_omm`, `tudatpy_utils.propagation`, and `tudatpy_utils.plotting` under `src/`.
- Step 4 implementation uses a transitional namespace bridge: Poetry packages the existing top-level domains and `tudatpy_utils` aliases them at import time. Physical relocation under `src/tudatpy_utils/` remains a later cleanup option.
- Existing top-level imports such as `common.*`, `diff_oem.*`, and `oem_to_omm.*` remain transition compatibility surfaces while downstream users migrate to the canonical namespace.

### Console Commands

Poetry console scripts will use lowercase hyphenated names:

| Current script | Canonical command |
| --- | --- |
| `bin/diff_oem.py` | `diff-oem` |
| `src/download_tle/download_tle.py` | `download-tle` |
| `bin/omm_to_tle.py` | `omm-to-tle` |
| `bin/slice_oem.py` | `slice-oem` |
| `bin/tle_info.py` | `tle-info` |
| `bin/tle_to_omm.py` | `tle-to-omm` |
| `bin/xform_oem.py` | `xform-oem` |
| `src/oem_to_omm/oem_to_omm.py` | `oem-to-omm` |
| `src/oem_to_omm/evaluate_fit_tle.py` | `evaluate-fit-tle` |
| `propagation/propagate_orbit.py` | `propagate-orbit` |
| `propagation/propagate_kepler.py` | `propagate-kepler` |
| `propagation/propagate_tle.py` | `propagate-tle` |
| `plotting/plot_orbit.py` | `plot-orbit` |
| `plotting/plot_orbit_deltas.py` | `plot-orbit-deltas` |
| `plotting/plot_dependent_variables.py` | `plot-dependent-variables` |

Direct script invocation remains supported through the migration. No underscore aliases will be registered initially; compatibility belongs in the existing wrapper paths rather than duplicate Poetry commands.

### Dependency Groups

- Core runtime dependency: NumPy.
- TudatPy remains an external prerequisite for frame conversion, SPICE, propagation, and TLE-fitting workflows.
- `plotting` extra: Matplotlib for plotting workflows.
- No direct SGP4 or SciPy dependency is declared until a direct import is verified.
- Development tooling and supported Python versions remain Step 3 decisions because they depend on the Poetry configuration and CI environment.

### Compatibility Policy

- Preserve documented argument names, stdin/stdout behavior, output formats, and exit behavior.
- Keep `bin/` and domain-script wrappers during the initial package release and deprecate them only after the console commands are documented and smoke-tested.
- Treat canonical imports under `tudatpy_utils` and the 15 console commands as the new public surface.
