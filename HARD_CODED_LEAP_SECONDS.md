# Hard-coded leap seconds in Tudat / SOFA

## Context

This repository contains several time-conversion experiments and tools under `time_conversion/`, plus Python helpers in `common/` that rely on TudatPy time-conversion functionality.

A recurring caveat is that some UTC/TAI-related conversions ultimately depend on leap-second data that may be hard-coded inside upstream libraries rather than loaded dynamically from an external leap-second file.

## SOFA and `TerrestrialTimeScaleConverter`

Tudat's `TerrestrialTimeScaleConverter` relies heavily on SOFA routines for time conversions.

In particular, SOFA's `iauDat()` computes:

- `Delta(AT) = TAI - UTC`

for a given UTC date, and this leap-second knowledge is hard-coded in SOFA.

That means some Tudat / TudatPy UTC-related conversions may not automatically reflect leap seconds introduced after the SOFA version bundled into the upstream dependency chain.

## Incomplete call graph

Illustrative call graph noted during investigation:

- `iauDat()`
  - `tudat::sofa_interface::getDeltaAtFromUtc()`
    - `tudat::sofa_interface::convertTAItoUTC()`
      - `tudat::earth_orientation::TerrestrialTimeScaleConverter::calculateUniversalTimes()`
        - `tudat::earth_orientation::TerrestrialTimeScaleConverter::updateTimes()`
          - `tudat::earth_orientation::TerrestrialTimeScaleConverter::getCurrentTime()`
      - `tudat::sofa_interface::getTDBminusTT()`
    - `tudat::sofa_interface::convertUTCtoTAI()`
      - `tudat::earth_orientation::TerrestrialTimeScaleConverter::updateTimes()`
      - `tudat::earth_orientation::TerrestrialTimeScaleConverter::calculateAtomicTimesFromUtc()`
      - `tudat::sofa_interface::convertUTCtoTT()`
  - `tudat::sofa_interface::getDeltaAtFromTai()`

## Related note on `DateTime`

`tudat::basic_astrodynamics::DateTime` was also observed to rely on hard-coded leap-second knowledge.

## Practical implication for this repository

When validating behavior of:

- `time_conversion/tools/convert_time_cli`
- Python helpers in `common/common.py`
- scripts under `misc/` that probe leap-second or UTC edge cases

be aware that discrepancies near future leap seconds may come from upstream leap-second handling rather than from this repository's wrapper logic.

## Status

This file is a technical note, not a complete fix description. It documents an upstream limitation/caveat that should be kept in mind when interpreting UTC/TAI/TT/TDB conversion results.
