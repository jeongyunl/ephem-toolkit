# Design & Plan: Modularizing `propagate_orbit`'s Propagation Engine into `core`

## 1. Motivation

`propagate_orbit/` currently bundles two distinct concerns in one feature package:

1. A **reusable numerical propagation engine** (Tudat environment/acceleration/propagator
   setup) that has no dependency on CLI concepts.
2. **CLI-specific glue** (argument parsing, OPM/OEM/CSV I/O, human-readable summaries).

This mirrors the split the project already applies elsewhere: `core.kepler` provides
two-body Keplerian propagation used by `propagate_kepler`'s thin CLI wrapper, and
`core.mean_kepler` provides J2 mean-element propagation. `propagate_orbit`'s Tudat-based
engine is the odd one out — it's the only propagator implementation still living entirely
inside a CLI feature package instead of `core/`.

This also directly serves two open `TODO.md` items:

- *Propagators → "Numerical propagator (Tudat wrapper)"* — implies a core-level engine,
  analogous to the planned Keplerian/DSST/USM propagators.
- *`propagate-orbit` → "give a less generic name"* — easier once `propagate_orbit/` is
  reduced to a thin CLI, since the CLI name and the engine name can be decoupled.

**Goal:** Extract the reusable propagation engine into `core/`, leaving `propagate_orbit/`
as a thin CLI layer (arg parsing, I/O, summaries) that calls into `core`, exactly like
`propagate_kepler` and `propagate_tle` already do for their respective engines.

## 2. Current State Analysis

```
propagate_orbit/
├── propagate_orbit_cli.py   CLI arg parsing (argparse)
├── constants.py             Mix of CLI defaults + engine defaults
├── data_structures.py       PropagationInputs dataclass (pure config, no argparse dep)
├── input_handling.py        OPM reading + CLI args -> PropagationInputs
├── tudat_setup.py           *** Engine: environment, accelerations, dep-vars, propagator settings ***
├── propagation.py           *** Engine orchestration (run_propagation) + output I/O calls ***
├── output_handling.py       OEM/CSV writing + summary printing
└── __main__.py              Orchestrates CLI -> input_handling -> tudat_setup -> propagation
```

Key observations:

- `tudat_setup.py` (`load_spice_kernels`, `create_environment_and_bodies`,
  `create_acceleration_models`, `create_dependent_variables_to_save`,
  `create_translational_propagator_settings`) has **no CLI or argparse dependency**. It
  only depends on `PropagationInputs`, `tudatpy`, and `core.spice_utils`/`core.time_utils`.
  This is the engine.
- `PropagationInputs` (in `data_structures.py`) is already a clean domain dataclass — no
  `argparse.Namespace` leakage. It is effectively a `NumericalPropagationConfig` in
  disguise.
- `propagation.py::run_propagation` mixes engine orchestration (creating bodies,
  accelerations, propagator settings, running `simulator.create_dynamics_simulator`) with
  output I/O (`write_state_history_oem`, `write_dependent_variables_csv`) and `sys.exit`
  error handling that belongs to the CLI layer.
- `constants.py` mixes two kinds of defaults:
  - **Engine defaults** used by `tudat_setup.py`: `DEFAULT_BODIES_TO_CREATE`,
    `DEFAULT_GLOBAL_FRAME_ORIGIN`, `DEFAULT_GLOBAL_FRAME_ORIENTATION`,
    `SUPPORTED_INTEGRATOR_METHODS`, `INTEGRATOR_METHOD_DESCRIPTIONS`,
    `DEFAULT_INTEGRATOR_METHOD`.
  - **CLI/scenario defaults**: `DEFAULT_SATELLITE_NAME`, `DEFAULT_SATELLITE_MASS_KG`,
    cubesat geometry constants, `DEFAULT_SIMULATION_DURATION_S`,
    `DEFAULT_INTEGRATOR_STEP_SIZE_S`, drag/SRP coefficient defaults.
- No existing unit tests exercise `tudat_setup.py` or `propagation.py` directly (only
  `propagate_orbit_cli.parse_arguments` is tested in
  [tests/ephem_toolkit/propagate_orbit/test_propagate_orbit.py](../tests/ephem_toolkit/propagate_orbit/test_propagate_orbit.py)),
  so relocation carries low regression risk for tests but no safety net either — manual
  smoke propagation should be re-run after the move.

## 3. Proposed Design

### 3.1 New core module: `core/numerical_propagation.py`

A single new module (mirroring the flat-file convention of `core/kepler.py`,
`core/mean_kepler.py`) containing the engine, with no `propagate_orbit` imports:

```
core/numerical_propagation.py
├── NumericalPropagationConfig      (renamed from PropagationInputs, moved as-is)
├── NumericalPropagator             (implements Propagator[NumericalPropagationConfig])
├── load_spice_kernels()
├── create_environment_and_bodies(config)
├── create_acceleration_models(config, bodies, bodies_to_propagate, central_bodies)
├── create_dependent_variables_to_save(config)
├── create_translational_propagator_settings(config, central_bodies,
│                                             acceleration_models,
│                                             bodies_to_propagate,
│                                             dependent_variables_to_save)
└── run_numerical_propagation(config)
    -> (state_history, dep_var_dict, dependent_variables_to_save)
```

`run_numerical_propagation` is a **new** consolidating entry point extracted from the
non-I/O portion of `propagation.py::run_propagation`: it wires together bodies,
accelerations, dependent variables, propagator settings, and calls
`simulator.create_dynamics_simulator`, returning raw results. It performs no file I/O and
raises exceptions rather than calling `sys.exit`, so it is usable from any caller (CLI,
notebook, test).

`NumericalPropagator` implements the `Propagator[NumericalPropagationConfig]` interface
from `core/propagator/base.py` (see
[docs/PROPAGATOR_INTERFACE_DESIGN.md](PROPAGATOR_INTERFACE_DESIGN.md)), providing
`set_initial_state`, `get_initial_epoch`, `propagate_to`, and `propagate_history` methods
that wrap `run_numerical_propagation`. This class will live in `core/propagator/numerical.py`
and is added after the initial migration lands, as part of the broader propagator interface
rollout.

Engine-only constants (`DEFAULT_BODIES_TO_CREATE`, `DEFAULT_GLOBAL_FRAME_ORIGIN`,
`DEFAULT_GLOBAL_FRAME_ORIENTATION`, `SUPPORTED_INTEGRATOR_METHODS`,
`INTEGRATOR_METHOD_DESCRIPTIONS`, `DEFAULT_INTEGRATOR_METHOD`) move into this module
alongside the functions that use them.

### 3.2 Slimmed `propagate_orbit/`

```
propagate_orbit/
├── propagate_orbit_cli.py   unchanged behavior; imports SUPPORTED_INTEGRATOR_METHODS /
│                             INTEGRATOR_METHOD_DESCRIPTIONS from core.numerical_propagation
├── constants.py              CLI/scenario-only defaults remain (satellite name/mass,
│                             cubesat geometry, duration, step-size default, drag/SRP coeffs)
├── input_handling.py         builds core.numerical_propagation.NumericalPropagationConfig
│                             from CLI args + OPM input (unchanged logic, updated import)
├── propagation.py            thin: calls core.numerical_propagation.load_spice_kernels()
│                             + run_numerical_propagation(config), then delegates to
│                             output_handling for OEM/CSV writing and sys.exit on OSError
├── output_handling.py        unchanged (OEM/CSV writing, summary printing)
└── __main__.py               unchanged orchestration, only import paths updated
```

`tudat_setup.py` and `data_structures.py` are removed from `propagate_orbit/` (fully
relocated, not duplicated).

### 3.3 Naming

`NumericalPropagationConfig` is chosen over keeping `PropagationInputs` because the type
now lives in `core` as a public, reusable config object — "Inputs" reads as CLI-argument
framing, whereas "Config" better matches how other engines would reference it. Renaming is
mechanical (dataclass fields are unchanged) and can be done with a project-wide symbol
rename.

## 4. Migration Steps

1. Create `core/numerical_propagation.py` with `NumericalPropagationConfig` (moved from
   `data_structures.py`) and the five engine functions moved verbatim from
   `tudat_setup.py`, updating internal constant references.
2. Add `run_numerical_propagation(config)` to the new module, extracted from
   `propagation.py::run_propagation`'s non-I/O body.
3. Update `propagate_orbit/input_handling.py`, `propagate_orbit_cli.py`, and
   `propagation.py` to import from `ephem_toolkit.core.numerical_propagation` instead of
   local `tudat_setup`/`data_structures`.
4. Delete `propagate_orbit/tudat_setup.py` and `propagate_orbit/data_structures.py`.
5. Trim `propagate_orbit/constants.py` down to CLI/scenario-only defaults; move
   engine-only constants into `core/numerical_propagation.py`.
6. Update `propagate_orbit/__main__.py` imports (`tudat_setup.load_spice_kernels()` call
   site) to use the core module.
7. Run existing test suite
   ([tests/ephem_toolkit/propagate_orbit/test_propagate_orbit.py](../tests/ephem_toolkit/propagate_orbit/test_propagate_orbit.py))
   and a manual smoke propagation
   (`propagate-orbit tests/opm/iss.opm -d 6h -o -`) to confirm output is unchanged.
8. Add `tests/ephem_toolkit/core/test_numerical_propagation.py` for the relocated engine
   (at minimum, config-driven construction of acceleration models and dependent-variable
   lists, without requiring a full Tudat propagation run), following the style of
   existing `tests/ephem_toolkit/core/test_kepler.py`.
9. Update `docs/CORE_LIBRARY_SUMMARY.md` and `docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md` (or a
   new `docs/CORE_LIBRARY_NUMERICAL_PROPAGATION.md`) to document the new core module,
   consistent with how other core modules are documented.
10. Update `docs/PROPAGATE_ORBIT.md` to reflect the thinner CLI-only responsibility.

Steps 1–6 can land as one PR; steps 7–10 (tests/docs) should follow immediately after to
avoid an undocumented, untested core module.

## 5. Risks / Open Questions

- **`tudatpy` import cost**: `core/numerical_propagation.py` will import `tudatpy` at
  module scope, unlike other `core` modules which are lightweight. This is consistent with
  `propagate_orbit`'s existing late-import discipline (imports deferred until after CLI
  parsing in `__main__.py`), so no regression — but worth noting `core` is no longer
  uniformly "lightweight to import."
- **Naming collision**: confirm no other `core` module or planned DSST/USM propagator
  claims `numerical_propagation` as a name before finalizing.
- **Rename scope**: `PropagationInputs` → `NumericalPropagationConfig` touches every file
  in `propagate_orbit/` that references it; use a symbol rename tool rather than manual
  find/replace to avoid missed references.

## 6. Future Extensibility

Once this lands, `core/` will hold three propagator engines: `core.kepler` (two-body),
`core.mean_kepler` (J2 mean-element), and `core.numerical_propagation` (perturbed
numerical). The common `Propagator` interface (see
[docs/PROPAGATOR_INTERFACE_DESIGN.md](PROPAGATOR_INTERFACE_DESIGN.md)) will be added
separately in `core/propagator/` submodule, with propagator classes in:
- `core/propagator/kepler.py` - `KeplerPropagator`
- `core/propagator/mean_j2.py` - `MeanJ2Propagator`
- `core/propagator/numerical.py` - `NumericalPropagator`
- `core/propagator/sgp4.py` - `Sgp4Propagator`

Future DSST/USM propagators would follow the same `core/propagator/<name>.py` pattern.
