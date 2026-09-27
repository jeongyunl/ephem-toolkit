# Orbit-File Metadata Preservation Investigation

**Status:** In progress  
**Last updated:** 2026-09-27

## Purpose

Determine, for each supported orbit-file conversion route, which metadata values are preserved, transformed, regenerated, intentionally omitted, or unexpectedly lost. Use the results to validate and correct the claims in [Metadata Comparison](ORBIT_FILE_METADATA_COMPARISON.md) and the route-specific guidance in [Orbit-File Conversion Matrix](ORBIT_FILE_CONVERSION_MATRIX.md).

## Investigation Plan

Apply these steps to every route and model variant in [Next Routes to Examine](#next-routes-to-examine), using the route matrix as the complete scope.

1. **Select a route.** Record its source, target, model variant, command sequence, and every intermediate file. Treat each intermediate conversion as its own boundary in a composed route.
2. **List applicable fields.** Use [Metadata Coverage](#metadata-coverage) to identify source and target fields. Mark fields the source does not contain and fields the target format cannot represent so they are not mistaken for conversion bugs.
3. **Choose a representative input.** Use a fixture with non-default identity, header, frame/time, comments, and optional values wherever the source format supports them. Include covariance, maneuvers, physical parameters, user-defined keys, or OEM coverage/interpolation fields when applicable.
4. **Trace the implementation.** Follow parsing, conversion or propagation, metadata construction, and file writing. For composed routes, inspect each intermediate file and note where each field first changes or disappears.
5. **Run the conversion and re-read its output.** Compare serialized output after parsing it with the target-format reader. For composed routes, do this for intermediate outputs as well as the final output. Do not rely only on the in-memory object.
6. **Classify every applicable field.** Record one outcome: copied unchanged, normalized/converted, derived, regenerated, intentionally unsupported/lost, or unexpectedly lost/altered. Include the observed output and the code/test evidence.
7. **Decide whether action is needed.** For expected format limitations, document the loss and identify any companion report needed. For unexpected behavior, add a focused regression test first, make the smallest corrective change, and rerun that route's tests.
8. **Update the record.** Mark the route evidence as source-traced or behavior-verified, update the conversion comparison only from verified results, and capture unresolved questions such as frame semantics separately.
9. **Repeat and close out.** Continue through the route checklist, including every listed model variant. When all routes are behavior-verified, run the focused route suite and check that the matrix, comparison, test evidence, and unresolved limitations agree.

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
- Fixed OPM header comment loss through `propagate-kepler`: `read_kepler_input` now carries comments to the OEM metadata, before the generated provenance comment. Direct propagation tests and composed OPM(2B)→OMM tests verify the serialized comments.
- Fixed numerical OPM→OEM identity loss in `propagate-orbit`: the reader returns both object identity fields, the config carries them, and the writer serializes them. An explicit `--name` overrides the source `OBJECT_NAME`; otherwise the source name is used, then `Satellite` as fallback.
- Confirmed numerical propagation is Earth-centered J2000/UTC. The OPM reader now rejects missing or incompatible `CENTER_NAME`, `REF_FRAME`, and `TIME_SYSTEM`, avoiding silent frame/time relabeling. The old numerical composition fixture used `REF_FRAME=TOD`; it was replaced with an explicit J2000 fixture rather than continuing to accept the mismatch.
- OPM header comments are now carried into OEM metadata comments; a composed numerical OPM→OEM→OMM test verifies the comment at both serialized boundaries. Other OPM header fields are regenerated, while covariance, maneuvers, spacecraft parameters, and Keplerian elements remain uncopied.
- Classified remaining numerical OPM fields: OEM has no representation for OPM maneuvers, spacecraft parameters, or Keplerian elements. The CCSDS OEM standard supports covariance, but this toolkit's `CcsdsOem` parser/model/writer has no covariance support, so its loss is an implementation capability gap; preserving it also requires frame-aware handling when the OPM covariance frame differs from J2000.
- OPM mass/drag/SRP values are parsed by the OPM model but are not consumed by `build_propagation_inputs`; the numerical model uses CLI values/defaults instead. This is a source-parameter-to-force-model gap, distinct from metadata representation in the output OEM.
- Verified with `pytest tests/ephem_toolkit/propagate_orbit tests/ephem_toolkit/oem_to_omm/test_integration_opm_to_omm_composed.py -q` (69 passed; one LibreSSL/urllib3 warning and one near-equatorial DSST warning).
- Verified `OBJECT_ID` end to end for OPM(2B)→OMM(DSST) and OPM(NUM)→OMM(DSST) with parser-based integration assertions; `pytest tests/ephem_toolkit/oem_to_omm/test_integration_opm_to_omm_composed.py -q` passes (2 passed, with existing environment/orbit warnings).
- Extended the numerical OPM→OMM integration coverage to Brouwer and SGP4. All three supported fit models preserve `OBJECT_NAME`, `OBJECT_ID`, and numerical-source comments and produce fit reports with the selected target model. Serialized Brouwer/DSST OMMs use `REF_FRAME=ICRF`; SGP4 uses `REF_FRAME=TEME`. The composed test file passes (4 passed). Semantic frame transformation for fitted states remains a separate accuracy question.
- Extended OPM(2B)→OMM integration coverage to Brouwer and SGP4. Brouwer, DSST, and SGP4 preserve identity and source comments and emit the selected theory/report target; the SGP4 OMM uses TEME, while Brouwer/DSST use ICRF. Semantic frame transformation remains a separate accuracy question.
- Traced OMM/TLE→OEM propagation: it retains object name and object ID, generates an OEM header and provenance comment, and writes fixed `CENTER_NAME=EARTH`, `REF_FRAME=EME2000`, and `TIME_SYSTEM=UTC`. A serialized DSST test showed OMM comments were initially omitted; source comments are now carried into OEM metadata comments on SGP4, DSST, and Kepler paths. The `propagate-omm` suite passes (23 passed; one LibreSSL/urllib3 warning). Source OMM header fields and frame/time labels are still not generally copied.
- Added a serialized SGP4 OMM→OEM test using a TEME-declared input; identity, comments, generated header, coverage, provenance, and output `EME2000` label are verified. TudatPy docs say it converts raw TEME to J2000, and the installed runtime reports Earth/J2000. With the stated inertial-frame equivalence, the generated EME2000 label is consistent.
- Added an assertion to `test_sgp4_propagator_initialization` that the installed TudatPy ephemeris reports `frame_origin=Earth` and `frame_orientation=J2000`; the focused test passes. Running the full SGP4 file has two unrelated propagation failures because its test environment does not load leap-second kernels (`SPICE(NOLEAPSECONDS)`).
- The OMM→OPM wrapper delegates to a fitter that copies intermediate OEM metadata comments into the OPM header. Serialized OMM(DSST), OMM(SGP4), and TLE wrapper tests verify source comments or generated-only provenance reaches the OPM/report.
- Added a serialized OMM(DSST)→OPM wrapper test: object identity, `EARTH`/`EME2000`/`UTC` context, regenerated originator, source/provenance comments in the OPM header, and fit-report source comments/target provenance are verified. The OMM→OPM and shared fitter suites pass (33 passed).
- Added serialized SGP4 wrapper checks for OMM→OPM and TLE→OPM. OMM identity, comments, generated context/header, and fit-report comment/provenance survive; TLE identity and generated SGP4 provenance appear in the OPM/report. The OMM/TLE wrapper and shared fitter suites pass (39 passed). Both routes emit `REF_FRAME=EME2000`; TudatPy's TEME-to-J2000 conversion and the stated inertial equivalence support that label.
- Traced OMM→OPM and TLE→OPM wrappers: both generate an intermediate OEM and delegate to OEM→OPM fitting, so their context and comments reflect that generated OEM rather than copying the source message header or comments.
- Traced OEM→OMM fitting: it selects object name and object ID and copies OEM metadata comments into output comments, but builds a fresh OMM. The builder defaults to `REF_FRAME=ICRF`, `CENTER_NAME=EARTH`, and `TIME_SYSTEM=UTC`; it does not copy OEM reference-frame epoch, coverage/interpolation metadata, covariance, or other optional blocks. The input state frame is not transformed by this metadata assignment, so non-ICRF inputs need a semantic frame check.
- Traced OEM→OPM fitting: object name, object ID, center, frame, and time system are selected for output; OEM metadata comments are moved to OPM header comments. The builder creates a new header and does not carry covariance, maneuvers, spacecraft parameters, or OEM coverage/interpolation fields.
- Traced OEM→TLE: the wrapper fits an SGP4 OMM from the OEM, then converts that OMM to TLE. Only TLE-representable identity and element fields reach the final file; CCSDS header/comments and OEM-only fields do not.
- Updated [Metadata Comparison](ORBIT_FILE_METADATA_COMPARISON.md) for the audited routes, separating copied fields from generated values and identifying frame-label semantics that still need verification.
- Final focused route suite: 110 passed across direct TLE↔OMM tests, Kepler propagation, TLE→OMM CLI, OEM→OMM/OPM fits, and OMM/TLE→OPM wrappers.
- Latest focused regression suite: 124 passed across numerical propagation, OMM propagation, both OPM→OMM compositions, OEM→OPM, and OMM/TLE→OPM wrappers. Three environment/orbit warnings were reported (LibreSSL/urllib3 and near-equatorial DSST accuracy).

**Initial hypothesis to verify:**

Several conversion paths rebuild output metadata from a deliberately selected subset of source fields. Some omissions will be format limitations; others may be undocumented or unintended. The field-level fixtures and serialization checks above will distinguish these cases.

**Not yet verified:**

- Exact preservation behavior for all fields and all supported route variants.
- Whether source comments and optional metadata survive every composed intermediate step.
- Whether metadata claims in the comparison document match serialized outputs.
- Whether test gaps correspond to actual conversion defects.

## Next Routes to Examine

Prioritize the following routes. The source-level behavior below has been
partially traced; the remaining work is to verify serialized results with
representative metadata fixtures and classify losses as intentional or
unexpected.

1. **OPM(NUM) → OEM (`propagate-orbit`)**
   - `OBJECT_NAME` and `OBJECT_ID` now reach the generated OEM; explicit
     `--name` overrides the source name.
   - OPM header comments are carried into OEM metadata comments; the OEM
     header itself is regenerated.
   - Unsupported or missing center/frame/time metadata is rejected. OPM
     maneuvers and Keplerian elements have no OEM equivalent. The toolkit
     currently drops covariance despite OEM standard support and ignores OPM
     physical parameters when building the numerical force model; track both
     as explicit follow-up findings.
2. **OPM(NUM) → OMM(2B/BROUWER/DSST/SGP4)**
   - Identity, numerical-source comments, generated context, theory label, and
     fit-report target model are verified for Brouwer, DSST, and SGP4.
   - Continue separately with semantic frame validation: serialized labels
     are ICRF for Brouwer/DSST and TEME for SGP4, but this test does not prove
     that coordinates were transformed into those frames.
3. **OPM(2B) → OMM(2B/BROUWER/DSST/SGP4)**
   - Identity, source comments, theory labels, generated context, and fit-report
     target model are verified for Brouwer, DSST, and SGP4.
   - Continue separately with semantic frame validation: serialized labels are
     ICRF for Brouwer/DSST and TEME for SGP4, but tests do not prove that the
     fitted coordinates were transformed into those frames.
4. **OMM → OEM by theory**
   - Exercise two-body/fallback, DSST, and SGP4 propagation. Verify identity,
     source comments, frame/time labels, generated coverage and provenance,
     and optional OMM data that does not have an OEM representation.
   - Identity, source comments, generated coverage/provenance, and serialized
     SGP4 metadata are covered; comments are retained on all three branches.
   - Treat Earth-centered EME2000/J2000/ICRF/GCRF as equivalent per the stated
     assumption. TudatPy's TEME-to-J2000 conversion and installed runtime frame
     are verified; composed OMM→OPM comment carry-through is also verified.
5. **OMM/TLE → OPM(NUM)**
   - DSST OMM, SGP4 OMM, and TLE wrappers are verified for identity, generated
     context/header, and fit report; OMM comments carry through, while TLE has
     generated provenance only.
   - TudatPy converts the SGP4 TEME solution to J2000 before fitting; the
     generated OPM `EME2000` label is accepted under the stated assumption.
6. **OMM(2B/BROUWER/DSST) → TLE refit**
   - Check the `propagate-omm` → OEM → `oem-to-tle` composition, including
     object identity, generated TLE fields, fit-report provenance, and loss of
     CCSDS-only metadata at the final TLE boundary.
7. **OEM → OMM/OPM/TLE fit variants**
   - Add serialized field-level checks across each fit model. Verify comments,
     source metadata, frame/time semantics, optional covariance/physical
     fields, and the companion report where the target cannot carry data.
8. **Direct TLE ↔ OMM metadata coverage**
   - Extend existing orbital round-trip tests with assertions for all
     TLE-representable metadata and serialized OMM output. Verify expected
     losses separately: TLE cannot carry CCSDS headers, comments, covariance,
     spacecraft parameters, or user-defined fields.

## Evidence Log

Use this table as the audit proceeds. Record references to focused tests or fixtures alongside the observed behavior.

| Route | Metadata categories checked | Outcome | Evidence / follow-up |
|---|---|---|---|
| TLE → OMM | Identity, context, orbital/TLE parameters, generated header | Source trace and existing conversion tests | 25 conversion tests pass; add serialized metadata assertions if broad coverage is required |
| OMM → TLE | TLE-representable identity and parameters; CCSDS-only fields | Source trace and existing conversion tests | 25 conversion tests pass; losses are target-format limitations |
| OPM → OEM (`propagate-kepler`) | Identity, comments, frame/time, derived coverage, generated header | Focused parser/output tests and composed integration | `OBJECT_ID` and OPM header comments carry through; OEM header and propagation provenance are generated |
| OPM → OEM (`propagate-orbit`) | Identity, comments, frame/time, covariance, maneuvers, physical parameters | Focused behavior tests and serialized composition integration | Name/ID/comments carry through; incompatible context is rejected; covariance serialization and OPM physical-parameter use are capability gaps |
| TLE/OMM → OEM propagation | Identity, frame/time, comments, generated header | DSST/Kepler/SGP4 serialized tests plus SGP4 runtime-frame test | Comments and identity verified; TudatPy converts TEME to J2000, accepted as EME2000 under the stated assumption |
| OMM/TLE → OPM | Identity, frame/time, comments/provenance, generated header/report | DSST OMM, SGP4 OMM, and TLE serialized wrapper tests | Identity/context/report verified; OMM comments and TLE-generated provenance verified; TudatPy TEME-to-J2000 supports EME2000 under the stated assumption |
| OEM → OMM | Identity, comments, context, coverage, covariance | Source trace | Fresh OMM defaults to ICRF/EARTH/UTC; verify frame semantics and document omissions |
| OEM → OPM | Identity, comments, context, covariance, maneuvers, physical parameters | Source trace | Selected identity/context and comments survive; optional blocks are not copied |
| OEM → TLE | Identity and TLE-representable fields through intermediate OMM | Wrapper/source trace | CCSDS and OEM-only metadata are discarded by final TLE format |
| OPM(NUM) → OEM | Identity, comments, frame/time, covariance, maneuvers, physical parameters | Focused behavior tests and serialized composition test | Name/ID/comments carry through; unsupported context is rejected; covariance and physical-input gaps documented |
| OPM(NUM) → OMM | Identity, comments, frame/time, theory, fit report | Brouwer/DSST/SGP4 composition integration tests | Name/ID/comments and target theory verified for all supported fit models; frame labels differ by model; semantic frame validation remains |
| OPM(2B) → OMM | Identity, comments, frame/time, theory, fit report | Brouwer/DSST/SGP4 composition integration tests | Name/ID/comments and target theory verified for all supported fits; frame labels differ by model; semantic frame validation remains |
| OMM → OEM theory variants | Identity, comments, generated frame/time, coverage, provenance | DSST/Kepler/SGP4 serialized tests and SGP4 runtime-frame test | Identity/comments/coverage/provenance verified; TudatPy converts TEME to J2000 and EME2000 is accepted under the stated assumption |
| OMM(DSST) → OPM(NUM) | Identity, frame/time, comments, generated header/report | Serialized wrapper integration test | Identity, EARTH/EME2000/UTC, comments, originator, and report provenance verified |
| OMM(SGP4)/TLE → OPM(NUM) | Identity, frame/time, comments/provenance, generated header/report | Serialized wrapper integration tests and SGP4 runtime-frame test | Identity/context/comments or generated provenance verified; TudatPy converts TEME to J2000, EME2000 accepted under the stated assumption |
| OMM non-SGP4 → TLE refit | Identity, fit provenance, TLE fields | Route identified | Verify composed propagation/refit and final format losses |
| OEM fit model variants | Comments, context, optional fields, reports | Partial source trace | Verify serialized OMM/OPM/TLE for each model |
| Direct TLE ↔ OMM | TLE-representable metadata and serialized headers | Partial tests | Expand beyond orbital-value round trips; classify CCSDS-only losses |

## Completion Criteria

- Every supported directed route is covered, including relevant model variants and composed steps.
- Every applicable metadata category has a recorded outcome, with unsupported target fields distinguished from unexpected loss.
- Focused tests verify the key preservation and omission claims against serialized output where practical.
- The metadata comparison and conversion documentation agree with the verified behavior, and unresolved limitations are explicit.
