# diff_oem Module Structure

This directory contains the modularized components of the `diff_oem.py` script, which compares corresponding states from two OEM (Orbit Ephemeris Message) files.

## Module Organization

### Core Modules

- **`types.py`**: Type definitions
  - `State`: Single OEM-like state as `(timestamp, state_m)`
  - `StatePair`: Reference/comparison state pair

- **`data_structures.py`**: Data classes
  - `TransformationStageInput`: Input data for transformation stages
  - `ComparisonResult`: Results from state comparison operations

- **`comparison.py`**: Core comparison functions
  - `read_states()`: Read states from OEM files
  - `compare_states()`: Compare two OEM states
  - `resolve_state_pair()`: Resolve state pairs with interpolation
  - `rotate_state()`: Apply rotation to state vectors

- **`transformation_stages.py`**: Transformation stage implementations
  - `TransformationStage`: Abstract base class for transformation stages
  - `RotationStage`: Fit and apply 3D rotation
  - `RotationXYStage`: Fit and apply X/Y rotation only
  - `RotationZStage`: Fit and apply Z rotation only
  - `TimeShiftStage`: Fit and apply time shift

- **`pipeline.py`**: Pipeline management
  - `TransformationPipeline`: Execute ordered transformation stages
  - `create_interpolator()`: Create Lagrange interpolators

- **`output.py`**: Output formatting
  - `ComparisonOutput`: Format and print comparison results with statistics

- **`utils.py`**: Utility functions
  - `get_overlapping_time_range()`: Find time overlap between state histories
  - `resolve_time_bound()`: Parse time bounds
  - `build_comparison_pairs()`: Build state pairs for comparison
  - `compare_pairs()`: Compare multiple state pairs
  - Debug output helpers

- **`cli.py`**: Command-line interface
  - `parse_arguments()`: Parse CLI arguments
  - `extract_stage_sequence()`: Extract transformation stage order

## Usage

The main entry point remains `bin/diff_oem.py`, which imports and orchestrates these modules:

```bash
python3 bin/diff_oem.py <reference_oem.oem> <comparison_oem.oem>
```

## Design Principles

1. **Separation of Concerns**: Each module has a clear, focused responsibility
2. **Reusability**: Core functions can be imported and used independently
3. **Testability**: Smaller modules are easier to unit test
4. **Maintainability**: Changes to one component don't affect others
5. **Extensibility**: New transformation stages can be added easily

## Module Dependencies

```
bin/diff_oem.py (main script)
    ├── cli.py (argument parsing)
    ├── comparison.py (core comparison logic)
    ├── output.py (result formatting)
    ├── pipeline.py (transformation pipeline)
    ├── transformation_stages.py (transformation implementations)
    ├── utils.py (utility functions)
    ├── data_structures.py (data classes)
    └── types.py (type definitions)
```

## Adding New Transformation Stages

To add a new transformation stage:

1. Create a new class in `transformation_stages.py` inheriting from `TransformationStage`
2. Implement the required methods: `build_fit_pairs()`, `fit()`, `transform()`
3. Optionally implement `describe_fit()` for human-readable output
4. Add the stage key to `TRANSFORM_STAGE_OPTIONS` in `cli.py`
5. Add CLI argument in `parse_arguments()` in `cli.py`
6. Add stage instantiation logic in `bin/diff_oem.py`
