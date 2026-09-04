# Task 9: Add provenance reporting to OEM-to-TLE

## Goal

Ensure an OEM-to-TLE conversion communicates that it creates a new SGP4 model
and preserves the source history and fit quality outside the fixed-width TLE.

## Scope

- Keep the existing SGP4-compatible mean-element fit and TLE formatting path.
- Emit source OEM provenance, fit configuration, fit span, and residuals in a
  companion `--fit-report` JSON file or stdout report.
- Preserve source information in intermediate OMM comments where possible.
- Ensure the report identifies the generated TLE as an SGP4 fit rather than a
  lossless conversion of the source model.

## Acceptance criteria

- `oem-to-tle` accepts `--fit-report <path|->`.
- The report is produced for successful fits and contains residual RMS/maxima,
  selected SGP4 fit settings, and source model information.
- TLE output itself remains valid fixed-width data with correct checksums.
- Tests cover report path, stdout, and absent/unknown source provenance.
