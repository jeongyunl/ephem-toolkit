# Orbit-File Metadata Preservation Investigation

**Status:** In progress  
**Last updated:** 2026-09-27

## Purpose

Determine, for each supported orbit-file conversion route, which metadata values are preserved, transformed, regenerated, intentionally omitted, or unexpectedly lost. Use the results to validate and correct the claims in [Metadata Comparison](ORBIT_FILE_METADATA_COMPARISON.md) and the route-specific guidance in [Orbit-File Conversion Matrix](ORBIT_FILE_CONVERSION_MATRIX.md).

## Investigation Plan

1. **Inventory conversion routes.** Use the conversion matrix as the route list. Include direct mappings, single-step conversions, and composed propagation/fitting workflows. For composed workflows, inspect each intermediate format as well as the final output.
2. **Define field-level outcomes.** Classify each field as copied unchanged, normalized/converted, regenerated, unsupported by the target, or unexpectedly lost/altered. Distinguish intentional format limitations from implementation defects.
3. **Trace serialization boundaries.** Follow source parsing, conversion/output-object construction, and writing. Re-read serialized output where practical so the audit covers the user-visible file, not only in-memory objects.
4. **Verify representative metadata.** Use fixtures with distinguishable values for required and optional fields. Assert field-level outcomes after conversion and after parse-write-parse. Check orbital data separately with route-appropriate tolerances.
5. **Compare evidence with documentation.** Update the comparison and route notes based on verified outcomes. Record unresolved behavior, model-specific caveats, and fields that cannot be represented by the target format.

## Metadata Coverage

Track these categories where the source and target formats support them:

- Header: format version, creation date, originator, classification, message ID, and comments.
- Object identification: object name, object ID, NORAD catalog ID, and international designator.
- Reference context: center, frame, frame epoch, and time system.
- Epoch and coverage: epoch, start/stop times, and usable start/stop times.
- Orbit representation: Cartesian state, Keplerian elements, mean-element theory, and TLE-specific parameters.
- Physical and dynamic parameters: mass, drag/SRP fields, maneuvers, and user-defined values.
- Uncertainty and ephemeris details: covariance, OEM acceleration, interpolation method, and interpolation degree.
- Provenance: source comments, transformation details, fit/propagation configuration, and companion reports.

## Progress

### 2026-09-27: Initial source and test reconnaissance

**Completed:**

- Identified the directed conversion routes in the conversion matrix and grouped them into direct mappings, fitting conversions, and composed propagation/fitting workflows.
- Audited the direct TLE↔OMM mapping and ran `pytest tests/ephem_toolkit/core/test_convert_tle.py -q` (25 passed). Its tests verify TLE-representable orbital values and parameters, not general CCSDS metadata preservation.
- Traced TLE→OMM: the converter creates CCSDS context values, takes creation date/originator as optional arguments, and starts with no comments. TLE contains no CCSDS-only source fields to carry over.
- Found and fixed missing generated OMM header values in the `tle-to-omm` CLI. It now passes a UTC creation date and `ORIGINATOR=tle_to_omm`; a serialized-output regression test checks both fields. `pytest tests/ephem_toolkit/tle_to_omm/test_tle_to_omm.py -q` passes (8 passed). The core conversion function still intentionally leaves these fields empty unless callers supply them.
- Traced OMM→TLE: TLE-representable fields are converted; CCSDS header values, comments, covariance, spacecraft parameters, and user-defined keys have no TLE representation.
- Found and fixed `OBJECT_ID` loss in OPM→OEM through `propagate-kepler`. Its input metadata now carries `OBJECT_ID` into `CcsdsOem.from_states`; tests verify both the parsed metadata and written OEM. `pytest tests/ephem_toolkit/propagate_kepler/test_propagate_kepler.py -q` passes (14 passed).
- Traced the other OPM→OEM path, numerical `propagate-orbit`: it reads only the state vector and epoch, writes a configured/default satellite name, and does not write the source `OBJECT_ID`. This route still loses source identity metadata and needs a follow-up decision/fix.
- Traced OMM/TLE→OEM propagation: it retains object name and object ID, generates an OEM header and provenance comment, and writes fixed `CENTER_NAME=EARTH`, `REF_FRAME=EME2000`, and `TIME_SYSTEM=UTC`. It does not copy OMM header metadata or source comments; source context fields are not generally carried through.
- Traced OMM→OPM and TLE→OPM wrappers: both generate an intermediate OEM and delegate to OEM→OPM fitting, so their context and comments reflect that generated OEM rather than copying the source message header or comments.
- Traced OEM→OMM fitting: it selects object name and object ID and copies OEM metadata comments into output comments, but builds a fresh OMM. The builder defaults to `REF_FRAME=ICRF`, `CENTER_NAME=EARTH`, and `TIME_SYSTEM=UTC`; it does not copy OEM reference-frame epoch, coverage/interpolation metadata, covariance, or other optional blocks. The input state frame is not transformed by this metadata assignment, so non-ICRF inputs need a semantic frame check.
- Traced OEM→OPM fitting: object name, object ID, center, frame, and time system are selected for output; OEM metadata comments are moved to OPM header comments. The builder creates a new header and does not carry covariance, maneuvers, spacecraft parameters, or OEM coverage/interpolation fields.
- Traced OEM→TLE: the wrapper fits an SGP4 OMM from the OEM, then converts that OMM to TLE. Only TLE-representable identity and element fields reach the final file; CCSDS header/comments and OEM-only fields do not.
- Updated [Metadata Comparison](ORBIT_FILE_METADATA_COMPARISON.md) for the audited routes, separating copied fields from generated values and identifying frame-label semantics that still need verification.
- Final focused route suite: 110 passed across direct TLE↔OMM tests, Kepler propagation, TLE→OMM CLI, OEM→OMM/OPM fits, and OMM/TLE→OPM wrappers.

**Initial hypothesis to verify:**

Several conversion paths rebuild output metadata from a deliberately selected subset of source fields. Some omissions will be format limitations; others may be undocumented or unintended. The field-level fixtures and serialization checks above will distinguish these cases.

**Not yet verified:**

- Exact preservation behavior for all fields and all supported route variants.
- Whether source comments and optional metadata survive every composed intermediate step.
- Whether metadata claims in the comparison document match serialized outputs.
- Whether test gaps correspond to actual conversion defects.

## Evidence Log

Use this table as the audit proceeds. Record references to focused tests or fixtures alongside the observed behavior.

| Route | Metadata categories checked | Outcome | Evidence / follow-up |
|---|---|---|---|
| TLE → OMM | Identity, context, orbital/TLE parameters, generated header | Source trace and existing conversion tests | 25 conversion tests pass; add serialized metadata assertions if broad coverage is required |
| OMM → TLE | TLE-representable identity and parameters; CCSDS-only fields | Source trace and existing conversion tests | 25 conversion tests pass; losses are target-format limitations |
| OPM → OEM (`propagate-kepler`) | Identity, frame/time, derived coverage, generated header | Source trace and focused regression tests | `OBJECT_ID` preservation fixed; 14 tests pass |
| OPM → OEM (`propagate-orbit`) | Input identity, frame/time, optional OPM blocks | Source trace | `OBJECT_ID` is not written and input object name is not the default output name; follow up |
| TLE/OMM → OEM propagation | Identity, frame/time, comments, generated header | Source trace | Only identity plus generated provenance survives; verify output frame semantics and serialized cases |
| OMM/TLE → OPM | Identity, frame/time, comments, generated header | Source trace through intermediate OEM and common fitter | Header/comments are regenerated through composition; verify route-specific serialized outputs |
| OEM → OMM | Identity, comments, context, coverage, covariance | Source trace | Fresh OMM defaults to ICRF/EARTH/UTC; verify frame semantics and document omissions |
| OEM → OPM | Identity, comments, context, covariance, maneuvers, physical parameters | Source trace | Selected identity/context and comments survive; optional blocks are not copied |
| OEM → TLE | Identity and TLE-representable fields through intermediate OMM | Wrapper/source trace | CCSDS and OEM-only metadata are discarded by final TLE format |
| Remaining model variants | Intermediate and final metadata | Partially traced | Verify composition-level serialized output and model-specific frame semantics |

## Completion Criteria

- Every supported directed route is covered, including relevant model variants and composed steps.
- Every applicable metadata category has a recorded outcome, with unsupported target fields distinguished from unexpected loss.
- Focused tests verify the key preservation and omission claims against serialized output where practical.
- The metadata comparison and conversion documentation agree with the verified behavior, and unresolved limitations are explicit.
