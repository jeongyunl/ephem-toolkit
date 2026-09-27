# Orbit-File Metadata Preservation Investigation

**Status:** Complete (representative audit; follow-ups listed below)
**Scope:** Representative route audit; known capability gaps documented.
**Last updated:** 2026-09-27

## Purpose

Determine, for each supported orbit-file conversion route, which metadata values are preserved, transformed, regenerated, intentionally omitted, or unexpectedly lost. Use the results to validate and correct the claims in [Metadata Comparison](ORBIT_FILE_METADATA_COMPARISON.md) and the route-specific guidance in [Orbit-File Conversion Matrix](ORBIT_FILE_CONVERSION_MATRIX.md).

## Investigation Plan

Apply these steps to every route and model variant in [Route Status](#route-status), using the route matrix as the complete scope.

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

- Header: format-specific version, creation date, originator, classification,
  message ID, and comments. Treat each target format version as generated
  schema metadata, not as a source value to preserve across conversion.
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
- **OPM routes:** fixed identity/comment loss and enforce numerical input context. OPM→OMM model variants preserve identity/comments. Both OPM→OEM paths preserve covariance at the input epoch without evolving it; `propagate-orbit` accepts only J2000-equivalent covariance frames, while `propagate-kepler` retains its declared covariance frame. Numerical physical inputs use CLI-over-OPM-over-default precedence.
- **OMM/TLE routes:** verified identity, comments/provenance, generated context, and reports across propagation and wrappers. DSST consumes complete OMM drag/SRP parameter groups; Kepler ignores spacecraft parameters and SGP4 uses TLE parameters. `propagate-omm` preserves OMM covariance at its source epoch only when that epoch is within the emitted OEM state interval; it does not evolve covariance. OEM fitters still omit covariance. OMM→OPM composition tests verify optional source blocks do not reach the final OPM. Non-SGP4 OMM→TLE fallback provenance is recorded; TudatPy converts SGP4 TEME states to J2000.
- **OEM fits:** serialized checks cover OMM Brouwer/DSST/SGP4, OPM two-body/numerical, and SGP4 TLE output. Non-equivalent frames are rejected instead of relabeled; identity, comments, selected context, and representative omissions are verified.
- Combined focused route suites passed: 500 tests, with two accuracy tests deselected. Those two accuracy tests and all eight direct SGP4 tests pass separately. The SGP4 test module loads `naif0012.tls` through the shared SPICE helper. Existing LibreSSL warnings remain.

**Working conclusion:**

Conversion paths often rebuild metadata from a selected subset of source fields. Serialized checks now distinguish target-format limitations from fields omitted by the current implementation, including companion-report behavior where applicable.

**Scope and known limitations:**

- The audit uses representative fixtures; it is not an exhaustive assertion of every field combination across every route and model.
- `CcsdsOem` reads and writes covariance blocks. OPM propagation preserves covariance only at the input epoch; OMM propagation preserves it at the source epoch only when that epoch falls within OEM state coverage. Neither evolves covariance across the trajectory. OEM fitters omit source covariance. Covariance evolution and route-specific frame transforms remain outside this audit's scope.

## Deferred Follow-ups

- **Metadata fixture breadth:** Extend serialized checks beyond representative fixtures to cover more optional-field combinations and composed route/model variants.
- **Frame labels:** Add metadata-focused tests for frame-label preservation and regeneration across additional routes. Numerical validation of coordinate transformations is outside this metadata audit.
- **Covariance processing:** Deferred by request. This audit covers source-epoch preservation only; covariance evolution and route-specific covariance-frame transforms are not being investigated now.

## Route Status

The routes below summarize the verified behavior and known limitations. For
each optional field, target-format limitations are distinguished from toolkit
capability gaps.

1. **OPM(NUM) → OEM (`propagate-orbit`)**
   - `OBJECT_NAME` and `OBJECT_ID` now reach the generated OEM; explicit
     `--name` overrides the source name.
   - OPM header comments are carried into OEM metadata comments, and
     `CLASSIFICATION`/`MESSAGE_ID` are carried into the OEM header. OEM
     `ORIGINATOR` and `CREATION_DATE` are regenerated.
   - Unsupported or missing center/frame/time metadata is rejected. OPM
     maneuvers and Keplerian elements have no OEM equivalent; a serialized
     regression confirms those fields and OPM `MASS` are omitted while identity
     and comments survive. A separate input test confirms explicit CLI values
     override OPM spacecraft parameters; otherwise OPM values, then defaults,
     configure the force model. A J2000-equivalent covariance is written at the
     input epoch only; it is not evolved across the numerical state history.
2. **OPM(NUM) → OMM(2B/BROUWER/DSST/SGP4)**
   - Identity, comments, OPM `CLASSIFICATION`/`MESSAGE_ID`, generated context,
     theory label, and fit-report target model are verified for Brouwer, DSST,
     and SGP4. OMM `ORIGINATOR` and `CREATION_DATE` are regenerated.
   - The input OPM label is `J2000`; generated OMM labels are `ICRF` for
     Brouwer/DSST and `TEME` for SGP4. This records metadata labels only, not
     coordinate-transform accuracy.
3. **OPM(2B) → OMM(2B/BROUWER/DSST/SGP4)**
   - Identity, source comments, OPM `CLASSIFICATION`/`MESSAGE_ID`, theory
     labels, generated context, and fit-report target model are verified for
     Brouwer, DSST, and SGP4. OMM `ORIGINATOR` and `CREATION_DATE` are
     regenerated.
   - The input OPM label is `J2000`; generated OMM labels are `ICRF` for
     Brouwer/DSST and `TEME` for SGP4. This records metadata labels only, not
     coordinate-transform accuracy.
4. **OMM → OEM by theory**
   - Exercise two-body/fallback, DSST, and SGP4 propagation. Verify identity,
     source comments, frame/time labels, generated coverage and provenance,
      and whether optional OMM data is consumed, represented, or omitted.
   - Identity, source comments, generated coverage/provenance, and serialized
     SGP4 metadata are covered; comments plus OMM `CLASSIFICATION` and
     `MESSAGE_ID` are retained on all three branches. OEM `ORIGINATOR` and
     `CREATION_DATE` are regenerated rather than copied from the OMM header.
   - Serialized branch tests verify optional OMM spacecraft parameters,
     reference-frame epoch, user-defined fields, and TLE parameters are not
    copied into OEM. DSST uses drag only with complete `MASS`/`DRAG_AREA`/
    `DRAG_COEFF` and SRP only with complete `SOLAR_RAD_AREA`/`SOLAR_RAD_COEFF`
    groups; tests also verify incomplete groups are ignored. Kepler ignores
    spacecraft parameters and SGP4 uses embedded TLE parameters.
     OMM covariance is retained at its source epoch with its declared frame,
     but is not evolved across the propagated state history.
   - The source frame label is regenerated as `EME2000` in OEM metadata rather
     than copied. The SGP4 runtime reports Earth/J2000; this audit records the
     labels only, not independent coordinate-transform accuracy. Composed
     OMM→OPM comment carry-through is also verified.
5. **OMM/TLE → OPM(NUM)**
   - DSST OMM, SGP4 OMM, and TLE wrappers are verified for identity, generated
     context/header, and fit report; OMM comments carry through, while TLE has
     generated provenance only.
   - Serialized DSST and SGP4 OMM wrapper tests confirm covariance,
     spacecraft parameters, reference-frame epoch, user-defined values, and
     all SGP4 TLE parameters (`EPHEMERIS_TYPE`, `CLASSIFICATION_TYPE`,
     `NORAD_CAT_ID`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`, `BSTAR`,
     `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`, `BTERM`, and `AGOM`) are absent from
     the final OPM. The intermediate OEM
     retains covariance at the OMM epoch; the OPM fitter omits it. DSST
     spacecraft parameters affect intermediate propagation, not OPM metadata.
   - OMM `CLASSIFICATION` and `MESSAGE_ID` are carried through the intermediate
     OEM into the generated OPM header. OPM `ORIGINATOR` and `CREATION_DATE`
     are regenerated.
   - The generated OPM frame label is `EME2000`; the SGP4 runtime reports
     Earth/J2000. This audit records those labels only, not transform accuracy.
6. **OMM(2B/BROUWER/DSST) → TLE refit**
   - DSST propagation and 2B/Brouwer-Lyddane Kepler fallback → OEM →
     `oem-to-tle` are verified for parsed TLE identity, checksums, and
     report-only source comments/provenance.
   - TLE cannot retain CCSDS comments or source theory; the report and
     intermediate OEM comments record those losses and the fallback model.
7. **OEM → OMM/OPM/TLE fit variants**
   - Serialized CLI checks cover OMM Brouwer/DSST/SGP4 and OPM two-body and
  numerical fitting. OEM→OPM preserves source `CLASSIFICATION` and
  `MESSAGE_ID` while regenerating OPM `ORIGINATOR`/`CREATION_DATE`. The real
  SGP4 fit path also verifies generated OMM identity, header/context, TLE
  parameters, and provenance; the TLE companion report retains source
  comments.
   - `oem-to-omm` now accepts only `J2000`, `EME2000`, `ICRF`, and `GCRF` input
    frames and rejects other labels before fitting; transform other inputs
    with a verified conversion supported for their source frame. OEM
    covariance is parsed but is not copied into fitted OMM/OPM outputs by
    the current fitters.
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
| OPM → OEM (`propagate-kepler`) | Identity, comments, frame/time, covariance, derived coverage, generated header | `test_propagate_kepler_writes_cartesian_states_in_si_units`; composed integration | `OBJECT_ID` and comments carry through; covariance and its declared frame are retained at the input epoch only; OEM header and coverage are generated |
| OPM → OEM (`propagate-orbit`) | Identity, header comments/classification/message ID, frame/time, covariance, maneuvers, physical parameters | `test_opm_preserves_header_and_omits_opm_only_blocks`; `test_opm_physical_parameters_are_used_unless_cli_overrides`; `test_read_initial_state_rejects_non_equivalent_covariance_frame` | Serialized OPM confirms identity/comments and supported `CLASSIFICATION`/`MESSAGE_ID` survive; OEM `ORIGINATOR`/`CREATION_DATE` are regenerated; Keplerian elements, maneuver, and mass are omitted; covariance behavior is covered separately at the input epoch only |
| TLE/OMM → OEM propagation | Identity, frame/time, comments, generated header | DSST/Kepler/SGP4 serialized tests plus SGP4 runtime-frame test | Comments and identity verified; OEM metadata emits `EME2000`; TudatPy SGP4 ephemeris reports Earth/J2000; no coordinate-transform accuracy claim |
| OMM/TLE → OPM | Identity, frame/time, comments/provenance, generated header/report | DSST OMM, SGP4 OMM, and TLE serialized wrapper tests | Identity/context/report verified; OMM comments and TLE-generated provenance verified; output frame label is `EME2000`; no coordinate-transform accuracy claim |
| OEM → OMM | Identity, header comments/classification/message ID, context, theory, coverage/interpolation, optional blocks | `test_main_serializes_oem_metadata_for_each_fit_model`; real-fit `test_reconstructed_tle_preserves_elements`; `test_main_rejects_non_equivalent_input_frame_before_fitting` | Serialized Brouwer/DSST/SGP4 checks verify source `CLASSIFICATION`/`MESSAGE_ID` carry through while OMM originator/date are regenerated; real SGP4 fit verifies identity/context, TLE parameters, and provenance; non-equivalent source frames rejected; reference-frame epoch and coverage/interpolation omitted; parsed covariance is not copied by the fitter |
| OEM → OPM | Identity, header comments/classification/message ID, context, state/elements, coverage/interpolation, optional blocks | `test_main_writes_initial_state_and_osculating_elements_to_opm`; `test_numerical_fit_model_dispatches_to_shared_fitter`; accuracy-marked `test_oem_to_opm_roundtrip_accuracy` | Serialized test verifies source `CLASSIFICATION`/`MESSAGE_ID` survive while OPM `ORIGINATOR`/`CREATION_DATE` regenerate; real-fit integration checks identity/context/comments and expected omissions; two-body elements are emitted, numerical elements are omitted; OEM coverage/interpolation are not copied by the fitter |
| OEM → TLE | Identity, TLE fields/checksums, source comments/provenance | `test_oem_to_tle_report_file_and_unknown_provenance` plus composed refit tests | TLE name/designator/checksums verified; CCSDS comments are absent from TLE and retained in the fit report |
| OPM(NUM) → OEM | Identity, comments, frame/time, covariance, maneuvers, physical parameters | `test_opm_physical_parameters_are_used_unless_cli_overrides`; `test_read_initial_state_rejects_non_equivalent_covariance_frame`; serialized composition test | Name/ID/comments carry through; unsupported context and non-equivalent covariance frames are rejected; physical inputs use CLI-over-OPM-over-default precedence; covariance is preserved at input epoch only, not evolved |
| OPM(NUM) → OMM | Identity, comments, classification/message ID, frame/time, theory, fit report | `test_opm_numerical_fit_variants_preserve_metadata`; `test_opm_to_omm_composes_numerical_propagation_and_dsst_fit` | Name/ID/comments and `CLASSIFICATION`/`MESSAGE_ID` survive real fits; OMM `ORIGINATOR`/`CREATION_DATE` regenerate; context, theory, report target, and output frame labels verified |
| OPM(2B) → OMM | Identity, comments, classification/message ID, frame/time, theory, fit report | `test_opm_kepler_fit_variants_preserve_metadata`; `test_opm_to_omm_composes_kepler_propagation_and_dsst_fit` | Name/ID/comments and `CLASSIFICATION`/`MESSAGE_ID` survive real fits; OMM `ORIGINATOR`/`CREATION_DATE` regenerate; context, theory, report target, and output frame labels verified |
| OMM → OEM theory variants | Identity, comments, classification/message ID, generated header/context/coverage, provenance, optional OMM blocks | `test_propagate_omm_dsst_produces_states`; `test_propagate_omm_kepler_preserves_source_comments`; `test_propagate_omm_sgp4_writes_metadata_and_source_comments`; `test_propagate_omm_dsst_ignores_incomplete_spacecraft_parameter_groups` | Comments/context/coverage and `CLASSIFICATION`/`MESSAGE_ID` verified on DSST, Kepler, and SGP4; `ORIGINATOR`/`CREATION_DATE` regenerated; DSST consumes only complete drag/SRP groups and tests incomplete-group omission; Kepler ignores spacecraft parameters; SGP4 uses TLE parameters; other optional blocks are omitted; covariance is retained at source epoch only when within emitted state coverage |
| OMM(DSST) → OPM(NUM) | Identity, frame/time, classification/message ID, comments, optional blocks, generated header/report | `test_omm_to_opm_preserves_source_comments_in_serialized_header` | Identity/context/comments and source `CLASSIFICATION`/`MESSAGE_ID` verified; OPM `ORIGINATOR`/`CREATION_DATE` regenerated; optional OMM blocks and covariance are absent from final OPM; DSST spacecraft parameters are used by intermediate propagation, which retains only source-epoch covariance |
| OMM(SGP4)/TLE → OPM(NUM) | Identity, frame/time, classification/message ID, comments/provenance, optional blocks, generated header/report | `test_sgp4_omm_to_opm_preserves_source_comments_in_serialized_header`; TLE wrapper integration tests | Identity/context/provenance and source OMM `CLASSIFICATION`/`MESSAGE_ID` verified; OPM `ORIGINATOR`/`CREATION_DATE` regenerated; SGP4 TLE parameters and other OMM optional blocks are absent from final OPM; OMM covariance is retained in the intermediate OEM at source epoch but not copied by fitting; generated OPM frame label is `EME2000` |
| OMM non-SGP4 → TLE refit | Identity, fit provenance, TLE fields, fallback labeling | DSST plus 2B/Brouwer-Lyddane fallback serialized tests | TLE identity/checksum verified; source comment and actual Kepler fallback retained in intermediate OEM/report |
| OEM fit model variants | Comments, context, selected state/elements, representative omissions, report provenance | Targeted serialized tests across OMM/OPM/TLE models; OEM→OPM and OEM→OMM real-fit integrations | Stubbed checks cover detailed serialization; real OPM/OMM fit routes verify identity, comments, generated context, theory, TLE parameters, and provenance; broader metadata fixture coverage remains |
| Direct TLE ↔ OMM | Identity, context, all TLE parameters/elements, optional CCSDS metadata loss | `test_tle_to_omm_matches_reference_file`; `test_omm_to_tle_matches_reference_file` | Both directions are re-read after serialization; expected TLE target-format losses are verified |

## Completion Criteria

- Every supported directed route is covered, including relevant model variants and composed steps.
- Every applicable metadata category has a recorded outcome, with unsupported target fields distinguished from unexpected loss.
- Focused tests verify the key preservation and omission claims against serialized output where practical.
- The metadata comparison and conversion documentation agree with the verified behavior, and unresolved limitations are explicit.
