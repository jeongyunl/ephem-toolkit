# Numerical Accuracy Testing Framework

## Overview

Optional test suite to evaluate numerical accuracy of core library functions and tools against reference data and analytical solutions.

## Directory Structure

```
tests/
  accuracy/
    core/
      test_accuracy_time_utils.py
      test_accuracy_kepler.py
      test_accuracy_frame_utils.py
      test_accuracy_coordinate_transforms.py
    integration/
      test_accuracy_propagation.py
      test_accuracy_tle_fitting.py
    fixtures/
      reference_data.py
      tolerance_config.py
    conftest.py
```

## Reference Data Strategy

- **High-precision ephemerides**: JPL HORIZONS, SPICE kernels
- **Analytical solutions**: Two-body Kepler propagation
- **Cross-validation**: SGP4, GMAT, Orekit
- **Known test cases**: Documented scenarios with expected results

## Test Categories

### Unit Accuracy
Individual function precision:
- Coordinate transformations
- Time conversions
- Orbital element conversions
- Frame transformations

### Integration Accuracy
End-to-end workflow precision:
- TLE → propagation → OEM
- OEM → OMM fitting
- Frame transformation pipelines

### Regression Accuracy
Track numerical degradation across versions

## Accuracy Metrics

- **Position error**: meters, kilometers
- **Velocity error**: m/s
- **Time conversion error**: microseconds, milliseconds
- **Angular error**: arcseconds, degrees
- **Relative error**: percentages

## Implementation Pattern

```python
@pytest.mark.accuracy
@pytest.mark.parametrize("scenario", REFERENCE_SCENARIOS)
def test_kepler_propagation_accuracy(scenario):
    """Test Kepler propagation against analytical solution."""
    result = propagate(scenario.initial_state, scenario.duration)
    error = compute_error(result, scenario.reference)
    assert error.position_km < TOLERANCE[scenario.regime]['position']
    assert error.velocity_mps < TOLERANCE[scenario.regime]['velocity']
```

## Tolerance Configuration

Define acceptable errors per function and orbital regime:

```python
# tests/accuracy/fixtures/tolerance_config.py
TOLERANCE = {
    'LEO': {
        'position': 1.0,      # km
        'velocity': 0.001,    # m/s
        'time': 1.0,          # microseconds
    },
    'GEO': {
        'position': 10.0,
        'velocity': 0.01,
        'time': 1.0,
    },
    'HEO': {
        'position': 50.0,
        'velocity': 0.1,
        'time': 1.0,
    }
}
```

## Making Tests Optional

### Method 1: Pytest Markers (Recommended)

**pytest.ini:**
```ini
[tool:pytest]
markers =
    accuracy: numerical accuracy tests (deselect with '-m "not accuracy"')

# Optional: skip by default
addopts = -m "not accuracy"
```

**Usage:**
```bash
# Skip accuracy tests (default if addopts set)
pytest -m "not accuracy"

# Run ONLY accuracy tests
pytest -m accuracy

# Run all tests
pytest -m ""
```

### Method 2: Separate Directory

Configure pytest to ignore accuracy directory by default:

```ini
[tool:pytest]
testpaths = tests/unit tests/integration
# Explicitly include: pytest tests/accuracy
```

## CI Integration

### Fast Suite (Every Commit)
```bash
pytest -m "not accuracy"
```

### Accuracy Suite (Nightly/Weekly)
```bash
pytest -m accuracy --verbose --tb=short
```

### Benchmark Tracking
- Store accuracy metrics over time
- Alert on degradation beyond thresholds
- Generate accuracy trend reports

## Reporting

Generate detailed accuracy reports:
- Error statistics (mean, max, std dev)
- Plots: error vs. time, error vs. orbital regime
- Comparison tables against reference solutions
- HTML report with visualizations

## Example Test Structure

```python
# tests/accuracy/core/test_accuracy_kepler.py
import pytest
from tests.accuracy.fixtures.reference_data import KEPLER_SCENARIOS
from tests.accuracy.fixtures.tolerance_config import TOLERANCE

@pytest.mark.accuracy
class TestKeplerAccuracy:
    
    @pytest.mark.parametrize("scenario", KEPLER_SCENARIOS)
    def test_two_body_propagation(self, scenario):
        """Validate against analytical two-body solution."""
        # Implementation
        pass
    
    def test_eccentric_anomaly_conversion(self):
        """Test E, M, ν conversions against high-precision values."""
        # Implementation
        pass
```

## Best Practices

1. **Separate concerns**: Unit vs integration accuracy
2. **Document tolerances**: Justify acceptable error bounds
3. **Use parametrization**: Test multiple scenarios efficiently
4. **Version reference data**: Track alongside code
5. **Fail informatively**: Report actual vs expected errors
6. **Optional by default**: Don't slow down regular testing
7. **Regular execution**: Run comprehensive suite periodically
