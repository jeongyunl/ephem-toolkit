# Task 1: Define provenance and fit-report handling

## Goal

Make generated CCSDS products explain which source model produced the input
history and which model or theory produced the output. Make fit diagnostics
available even when the output format cannot carry them.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Affected commands

### Existing commands

- `oem-to-omm`: generates OMM output and currently owns the Brouwer/DSST/TLE
  fitting paths.
- `oem-to-opm`: generates OPM output from an OEM and currently performs the
  two-body fit.
- `oem-to-tle`: wraps the OEM-to-OMM and OMM-to-TLE workflows; provenance for
  its TLE must be external to the TLE.
- `omm-to-tle`: performs the direct OMM-to-TLE mapping.
- `propagate-omm`, `propagate-kepler`, `propagate-orbit`, and `propagate-tle`:
  generate the OEM histories whose selected source/target model must be
  represented in provenance.
- `tle-to-omm`: is relevant when a TLE is preserved as an intermediate OMM.

### Proposed commands with no current implementation

`omm-to-opm`, `tle-to-opm`, `opm-to-omm`, and `opm-to-tle` are named by the
conversion design but are not currently registered in `pyproject.toml` and do
not have corresponding `src/ephem_toolkit/<command>/` packages. Their future
implementations should consume the shared reporting API defined here.

## Scope

- Emit portable `COMMENT` entries using the `EPHEMERIS_PROVENANCE` and
  `EPHEMERIS_FIT` forms specified in `ORBIT_FILE_CONVERSION.md`.
- Preserve source frame and time system, target gravity/force model,
  integrator and step settings, user-supplied physical parameters, fit span, sample count,
  residual RMS/maxima, and convergence status where applicable.
- Add JSON `--fit-report <path|->` output for the conversion commands listed in
  the source document.
- For TLE output, write provenance to the fit report and/or preceding OMM/OEM;
  do not try to add arbitrary fields to the TLE itself.
- Preserve portable comments when structured OPM `USER_DEFINED_EPHEMERIS_*`
  values are also used.

## Affected source files

### Existing implementation files

- [`src/ephem_toolkit/oem_to_omm/oem_to_omm_cli.py`](../../../src/ephem_toolkit/oem_to_omm/oem_to_omm_cli.py): add report/source options
  and expose fit metadata from the CLI.
- [`src/ephem_toolkit/oem_to_omm/__main__.py`](../../../src/ephem_toolkit/oem_to_omm/__main__.py): attach provenance comments and
  fit diagnostics to generated OMMs.
- [`src/ephem_toolkit/oem_to_omm/fit_common.py`](../../../src/ephem_toolkit/oem_to_omm/fit_common.py),
  [`fit_brouwer.py`](../../../src/ephem_toolkit/oem_to_omm/fit_brouwer.py), and
  [`fit_tle/`](../../../src/ephem_toolkit/oem_to_omm/fit_tle/): expose the
  existing mean-element fit results needed by reports.
- [`src/ephem_toolkit/oem_to_opm/oem_to_opm_cli.py`](../../../src/ephem_toolkit/oem_to_opm/oem_to_opm_cli.py) and
  [`src/ephem_toolkit/oem_to_opm/__main__.py`](../../../src/ephem_toolkit/oem_to_opm/__main__.py): add report options and OPM
  provenance.
- [`src/ephem_toolkit/oem_to_opm/fit_common.py`](../../../src/ephem_toolkit/oem_to_opm/fit_common.py) and
  [`fit_osculating_kepler.py`](../../../src/ephem_toolkit/oem_to_opm/fit_osculating_kepler.py): expose two-body fit settings,
  parameters, and residuals.
- [`src/ephem_toolkit/oem_to_tle/__main__.py`](../../../src/ephem_toolkit/oem_to_tle/__main__.py): carry report arguments through its
  delegated OEM→OMM→TLE pipeline.
- [`src/ephem_toolkit/omm_to_tle/omm_to_tle_cli.py`](../../../src/ephem_toolkit/omm_to_tle/omm_to_tle_cli.py) and
  [`src/ephem_toolkit/omm_to_tle/__main__.py`](../../../src/ephem_toolkit/omm_to_tle/__main__.py): support companion reports while
  preserving direct-conversion semantics.
- [`src/ephem_toolkit/core/ccsds/oem.py`](../../../src/ephem_toolkit/core/ccsds/oem.py),
  [`omm.py`](../../../src/ephem_toolkit/core/ccsds/omm.py), and
  [`opm.py`](../../../src/ephem_toolkit/core/ccsds/opm.py): preserve and write
  portable `COMMENT` entries; OPM is also the location to retain structured
  user-defined values.
- [`src/ephem_toolkit/core/cli.py`](../../../src/ephem_toolkit/core/cli.py):
  shared output/report path handling if the option is centralized.
- [`pyproject.toml`](../../../pyproject.toml): register future conversion
  entry points when the proposed commands are implemented.

### Supporting propagation files

- [`src/ephem_toolkit/propagate_omm/propagation.py`](../../../src/ephem_toolkit/propagate_omm/propagation.py),
  [`propagate_omm_cli.py`](../../../src/ephem_toolkit/propagate_omm/propagate_omm_cli.py)
- [`src/ephem_toolkit/propagate_kepler/propagation.py`](../../../src/ephem_toolkit/propagate_kepler/propagation.py),
  [`propagate_kepler_cli.py`](../../../src/ephem_toolkit/propagate_kepler/propagate_kepler_cli.py)
- [`src/ephem_toolkit/propagate_orbit/propagation.py`](../../../src/ephem_toolkit/propagate_orbit/propagation.py),
  [`output_handling.py`](../../../src/ephem_toolkit/propagate_orbit/output_handling.py), and
  [`propagate_orbit_cli.py`](../../../src/ephem_toolkit/propagate_orbit/propagate_orbit_cli.py)
- [`src/ephem_toolkit/propagate_tle/`](../../../src/ephem_toolkit/propagate_tle/):
  identify SGP4/TEME/UTC source provenance for generated OEMs.

### Tests to extend or add

- Existing conversion suites under `tests/ephem_toolkit/oem_to_omm/`,
  `oem_to_opm/`, `oem_to_tle/`, and `omm_to_tle/`.
- CCSDS serialization suites under `tests/ephem_toolkit/core/ccsds/`.
- Propagation suites under `tests/ephem_toolkit/propagate_omm/`,
  `propagate_orbit/`, `propagate_tle/`, and `propagate_kepler/`.
- Add focused tests for JSON schema/content, file versus stdout reports,
  comment round-tripping, missing/unknown provenance, and TLE companion
  reports.

The files above are affected-file candidates, not instructions to change every
file in the list. The implementation should first identify the narrowest
shared provenance/reporting seam, then update only the command paths that
actually produce or transform the relevant output.

## Progress

### Completed

- Added [`src/ephem_toolkit/core/provenance.py`](../../../src/ephem_toolkit/core/provenance.py)
  with portable provenance/fit-comment formatting and JSON fit-report writing
  to a file or stdout.
- Added `--fit-report`, `--source-model`, and `--source-report` parsing to
  `oem-to-omm` and `oem-to-opm`.
- Added provenance and fit-summary comments to generated OMMs from all current
  `oem-to-omm` modes and to generated OPMs from `oem-to-opm`.
- Added focused unit coverage in
  [`tests/ephem_toolkit/core/test_provenance.py`](../../../tests/ephem_toolkit/core/test_provenance.py),
  including dataclass and mapping-style diagnostics, stdout output, and
  rejection of non-finite JSON values.
- Added parser coverage for provenance/report options in the OEM-to-OMM and
  OEM-to-OPM test suites.
- Wired `oem-to-tle` to forward provenance/report options through its delegated
  OEM-to-OMM stage, including safe handling of `--fit-report -`; ambiguous
  simultaneous stdout output is rejected.
- Added automatic report naming: output `name.ext` produces `name.fit.json`;
  stdout output falls back to the input filename, and stdin-to-stdout requires
  an explicit report path if a report is wanted.
- Added `--no-fit-report` to disable automatic report creation; it conflicts
  with an explicit `--fit-report` value.
- Implemented `--source-report` JSON loading. With `--source-model auto`, the
  report's `provenance.source` is now used; an explicit source model overrides
  it, and invalid reports produce an actionable error.
- Generated fit reports now retain the complete parsed source report in a
  top-level `source_report` field.
- Generated reports now explicitly record successful `status=converged` and
  expose available `fit_method` and `iterations` fields at the report top level.
- Reports now include RMS and maximum position/velocity residuals when the
  existing propagation-comparison data provides them.
- Existing OEM conversion reports now record available fit configuration,
  including fit mode, gravitational parameter, source frame, and time system;
  TLE fits also record refinement method.
- Preserved compatibility with existing mocked diagnostics used by conversion
  tests.

### Verification

Command:

```text
PYTHONPATH=src pytest -q tests/ephem_toolkit/oem_to_omm tests/ephem_toolkit/oem_to_opm tests/ephem_toolkit/oem_to_tle tests/ephem_toolkit/core/ccsds/test_oem.py tests/ephem_toolkit/core/ccsds/test_omm.py tests/ephem_toolkit/core/ccsds/test_opm.py
```

Result: `223 passed, 2 deselected`.
`PYTHONPATH=src python -m compileall -q src` and `git diff --check` also pass.

### Remaining work

- Define and implement direct/refit report behavior for `omm-to-tle`; direct
  model validation is now implemented under Task 10.
- Extend force-model and integrator configuration reporting to any remaining
  production numerical-fitting workflows.
- Implement reporting for the proposed `omm-to-opm`, `tle-to-opm`,
  `opm-to-omm`, and `opm-to-tle` commands after those commands exist.

## Acceptance criteria

- Generated OEM, OMM, and OPM files contain source/target model provenance when
  the conversion is not model-neutral.
- Fit reports are valid, documented JSON and include configuration, fitted
  state values, supplied physical parameters, residual statistics, and
  convergence status.
- Direct lossless TLE↔SGP4-compatible OMM mappings do not require a fabricated
  fit report.
- Tests cover path output, stdout output (`-`), missing provenance, and TLE
  companion-report behavior.
