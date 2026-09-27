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

- Mapped the supported routes into direct, fitting, and composed workflows.
- **TLE↔OMM:** serialized checks verify identity, orbital elements, TLE parameters, and generated OMM context. CCSDS-only fields are omitted from TLE; CLI-generated OMM header values are covered separately.
- **OPM routes:** fixed identity/comment loss and enforce numerical input context. OPM→OMM model variants preserve identity/comments. For OPM(NUM)→OEM, CLI values override OPM physical parameters, omitted options use OPM values then defaults, and covariance is confirmed absent from the config and serialized OEM.
- **OMM/TLE routes:** verified identity, comments/provenance, generated context, and reports across propagation and wrappers. DSST consumes complete OMM drag/SRP parameter groups; Kepler ignores spacecraft parameters and SGP4 uses TLE parameters. Optional blocks not represented by the OEM model are omitted; covariance is an OEM-standard capability gap in `CcsdsOem`. OMM→OPM composition tests verify optional source blocks do not reach the final OPM. Non-SGP4 OMM→TLE fallback provenance is recorded; TudatPy converts SGP4 TEME states to J2000.
- **OEM fits:** serialized checks cover OMM Brouwer/DSST/SGP4, OPM two-body/numerical, and SGP4 TLE output. Non-equivalent frames are rejected instead of relabeled; identity, comments, selected context, and representative omissions are verified.
- Combined focused route suites passed: 406 tests; the two accuracy cases and all eight direct SGP4 tests also pass. The SGP4 test module loads `naif0012.tls` through the shared SPICE helper. Existing LibreSSL warnings remain.

**Working conclusion:**

Conversion paths often rebuild metadata from a selected subset of source fields. Serialized checks now distinguish target-format limitations from fields omitted by the current implementation, including companion-report behavior where applicable.

**Remaining scope and known limitations:**

- The checks are representative, not an exhaustive assertion of every field across every route and model combination.
- `CcsdsOem` does not read or write covariance. OPM/OMM covariance therefore does not reach OEM output; adding support requires covariance-frame-aware propagation and serialization.

## Next Routes to Examine

The routes below summarize verified behavior and remaining gaps. For each
optional field, distinguish target-format limitations from toolkit capability
gaps, and record unresolved behavior explicitly.

1. **OPM(NUM) → OEM (`propagate-orbit`)**
   - `OBJECT_NAME` and `OBJECT_ID` now reach the generated OEM; explicit
     `--name` overrides the source name.
   - OPM header comments are carried into OEM metadata comments; the OEM
     header itself is regenerated.
   - Unsupported or missing center/frame/time metadata is rejected. OPM
     maneuvers and Keplerian elements have no OEM equivalent. A serialized
     input test confirms explicit CLI values override OPM spacecraft
     parameters; otherwise OPM values, then defaults, configure the force
     model. Covariance is parsed but not forwarded to the numerical config or
     OEM output.
2. **OPM(NUM) → OMM(2B/BROUWER/DSST/SGP4)**
   - Identity, numerical-source comments, generated context, theory label, and
     fit-report target model are verified for Brouwer, DSST, and SGP4.
   - The input OPM fixture is J2000; Brouwer/DSST output ICRF under the stated
     inertial-frame equivalence. SGP4 OMM uses its native `TEME` mean-element
     frame, while TudatPy returns propagated states in J2000 for fit scoring.
3. **OPM(2B) → OMM(2B/BROUWER/DSST/SGP4)**
   - Identity, source comments, theory labels, generated context, and fit-report
     target model are verified for Brouwer, DSST, and SGP4.
   - The input OPM fixture is J2000; Brouwer/DSST output ICRF under the stated
     inertial-frame equivalence. SGP4 OMM uses `TEME` for its mean elements;
     TudatPy converts the propagated solution to J2000 for fit scoring.
4. **OMM → OEM by theory**
   - Exercise two-body/fallback, DSST, and SGP4 propagation. Verify identity,
     source comments, frame/time labels, generated coverage and provenance,
  and whether optional OMM data is consumed, represented, or omitted.
   - Identity, source comments, generated coverage/provenance, and serialized
     SGP4 metadata are covered; comments are retained on all three branches.
   - Serialized branch tests verify optional OMM spacecraft/covariance,
     reference-frame epoch, user-defined fields, and TLE parameters are not
     copied into OEM. DSST uses complete drag and SRP parameter groups;
     Kepler ignores spacecraft parameters and SGP4 uses embedded TLE parameters.
     Covariance is representable by the OEM standard but not by `CcsdsOem`.
   - Treat Earth-centered EME2000/J2000/ICRF/GCRF as equivalent per the stated
     assumption. TudatPy's TEME-to-J2000 conversion and installed runtime frame
     are verified; composed OMM→OPM comment carry-through is also verified.
5. **OMM/TLE → OPM(NUM)**
   - DSST OMM, SGP4 OMM, and TLE wrappers are verified for identity, generated
     context/header, and fit report; OMM comments carry through, while TLE has
     generated provenance only.
   - Serialized DSST and SGP4 OMM wrapper tests confirm covariance,
     spacecraft parameters, reference-frame epoch, user-defined values, and
     source TLE parameters are absent from the final OPM. DSST spacecraft
     parameters affect the intermediate propagation, not the OPM metadata.
   - TudatPy converts the SGP4 TEME solution to J2000 before fitting; the
     generated OPM `EME2000` label is accepted under the stated assumption.
6. **OMM(2B/BROUWER/DSST) → TLE refit**
   - DSST propagation and 2B/Brouwer-Lyddane Kepler fallback → OEM →
     `oem-to-tle` are verified for parsed TLE identity, checksums, and
     report-only source comments/provenance.
   - TLE cannot retain CCSDS comments or source theory; the report and
     intermediate OEM comments record those losses and the fallback model.
7. **OEM → OMM/OPM/TLE fit variants**
   - Serialized CLI checks now cover OMM Brouwer/DSST/SGP4, OPM two-body and
     numerical fitting, and the direct SGP4 TLE fit. They verify identity,
     comments, generated context/theory, representative state/element fields,
     and expected omissions; the TLE companion report retains source comments.
   - `oem-to-omm` now accepts only `J2000`, `EME2000`, `ICRF`, and `GCRF` input
     frames and rejects other labels before fitting; transform other inputs
     with a verified conversion supported for their source frame.
     OEM covariance cannot yet be seeded through `CcsdsOem`, whose parser/model
     does not expose covariance, so that input path remains unverified.
8. **Direct TLE ↔ OMM metadata coverage**
   - Serialized checks now re-read both directions. TLE identity, orbital and
     TLE-specific parameters survive; TLE→OMM generates Earth/TEME/UTC context,
     while OMM→TLE omits CCSDS headers/comments, covariance, spacecraft
     parameters, and user-defined fields.

## Evidence Log

Use this table as the audit proceeds. Record references to focused tests or fixtures alongside the observed behavior.

| Route | Metadata categories checked | Outcome | Evidence / follow-up |
|---|---|---|---|
| TLE → OMM | Identity, context, orbital/TLE parameters, generated/default header | `test_tle_to_omm_matches_reference_file` serialized parser round-trip | TLE identity, orbital/TLE parameters, and Earth/TEME/UTC + SGP/SGP4 context verified; core-library header/comment defaults are empty |
| OMM → TLE | TLE-representable identity and parameters; CCSDS-only fields | `test_omm_to_tle_matches_reference_file` serialized parser round-trip | Identity, TLE parameters, elements, and checksums verified; comments, header fields, covariance, spacecraft parameters, and user-defined key are absent from TLE |
| OPM → OEM (`propagate-kepler`) | Identity, comments, frame/time, derived coverage, generated header | Focused parser/output tests and composed integration | `OBJECT_ID` and OPM header comments carry through; OEM header and propagation provenance are generated |
| OPM → OEM (`propagate-orbit`) | Identity, comments, frame/time, covariance, maneuvers, physical parameters | `test_opm_physical_parameters_are_used_unless_cli_overrides` plus serialized composition tests | Name/ID/comments carry through; incompatible context is rejected; CLI overrides OPM values, then defaults apply; covariance is parsed but absent from config and serialized OEM |
| TLE/OMM → OEM propagation | Identity, frame/time, comments, generated header | DSST/Kepler/SGP4 serialized tests plus SGP4 runtime-frame test | Comments and identity verified; TudatPy converts TEME to J2000, accepted as EME2000 under the stated assumption |
| OMM/TLE → OPM | Identity, frame/time, comments/provenance, generated header/report | DSST OMM, SGP4 OMM, and TLE serialized wrapper tests | Identity/context/report verified; OMM comments and TLE-generated provenance verified; TudatPy TEME-to-J2000 supports EME2000 under the stated assumption |
| OEM → OMM | Identity, comments, context, theory, coverage/interpolation, optional blocks | `test_main_serializes_oem_metadata_for_each_fit_model`; `test_main_rejects_non_equivalent_input_frame_before_fitting` | Identity/comments/context/theory verified; non-equivalent source frames rejected; reference-frame epoch and coverage/interpolation omitted; covariance input unavailable |
| OEM → OPM | Identity, comments, context, state/elements, coverage/interpolation, optional blocks | `test_main_writes_initial_state_and_osculating_elements_to_opm`; `test_numerical_fit_model_dispatches_to_shared_fitter` | Parsed identity/context/state/comments verified; two-body elements emitted, numerical elements omitted; OEM coverage/interpolation omitted; covariance source unavailable in current OEM model |
| OEM → TLE | Identity, TLE fields/checksums, source comments/provenance | `test_oem_to_tle_report_file_and_unknown_provenance` plus composed refit tests | TLE name/designator/checksums verified; CCSDS comments are absent from TLE and retained in the fit report |
| OPM(NUM) → OEM | Identity, comments, frame/time, covariance, maneuvers, physical parameters | `test_opm_physical_parameters_are_used_unless_cli_overrides`; serialized composition test | Name/ID/comments carry through; unsupported context is rejected; physical inputs use CLI-over-OPM-over-default precedence; covariance is parsed, omitted from config, and absent from the re-read OEM |
| OPM(NUM) → OMM | Identity, comments, frame/time, theory, fit report | Brouwer/DSST/SGP4 composition integration tests; TudatPy SGP4 runtime-frame test | Name/ID/comments and target theory verified; J2000 input is equivalent to ICRF for Brouwer/DSST; SGP4 OMM is TEME while TudatPy propagates in J2000 |
| OPM(2B) → OMM | Identity, comments, frame/time, theory, fit report | Brouwer/DSST/SGP4 composition integration tests; TudatPy SGP4 runtime-frame test | Name/ID/comments and target theory verified; J2000 input is equivalent to ICRF for Brouwer/DSST; SGP4 OMM is TEME while TudatPy propagates in J2000 |
| OMM → OEM theory variants | Identity, comments, generated frame/time, coverage, provenance, optional OMM blocks | `test_propagate_omm_kepler_preserves_source_comments`; `test_propagate_omm_dsst_uses_spacecraft_parameters`; `test_propagate_omm_sgp4_writes_metadata_and_source_comments` | Comments/context/coverage verified; DSST consumes complete drag/SRP groups; Kepler ignores spacecraft parameters; SGP4 uses TLE parameters; OMM-only blocks are absent from OEM; covariance remains unsupported by `CcsdsOem` |
| OMM(DSST) → OPM(NUM) | Identity, frame/time, comments, optional blocks, generated header/report | `test_omm_to_opm_preserves_source_comments_in_serialized_header` | Identity/context/comments/report verified; optional OMM blocks are absent from final OPM; DSST spacecraft parameters are used by intermediate propagation |
| OMM(SGP4)/TLE → OPM(NUM) | Identity, frame/time, comments/provenance, optional blocks, generated header/report | `test_sgp4_omm_to_opm_preserves_source_comments_in_serialized_header`; TLE wrapper integration tests | Identity/context/provenance verified; SGP4 TLE parameters and other OMM optional blocks are absent from final OPM; TudatPy converts TEME to J2000 |
| OMM non-SGP4 → TLE refit | Identity, fit provenance, TLE fields, fallback labeling | DSST plus 2B/Brouwer-Lyddane fallback serialized tests | TLE identity/checksum verified; source comment and actual Kepler fallback retained in intermediate OEM/report |
| OEM fit model variants | Comments, context, selected state/elements, representative omissions, report provenance | Targeted serialized tests across OMM/OPM/TLE models | Fit algorithms stubbed for OMM/OPM serialization checks; TLE direct fit uses a real OEM fixture; semantic frame and covariance input coverage remain |
| Direct TLE ↔ OMM | Identity, context, all TLE parameters/elements, optional CCSDS metadata loss | `test_tle_to_omm_matches_reference_file`; `test_omm_to_tle_matches_reference_file` | Both directions are re-read after serialization; expected TLE target-format losses are verified |

## Completion Criteria

- Every supported directed route is covered, including relevant model variants and composed steps.
- Every applicable metadata category has a recorded outcome, with unsupported target fields distinguished from unexpected loss.
- Focused tests verify the key preservation and omission claims against serialized output where practical.
- The metadata comparison and conversion documentation agree with the verified behavior, and unresolved limitations are explicit.
