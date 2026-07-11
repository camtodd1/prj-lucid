# TODO

## Aircraft Characteristics Registry

- [ ] Integrate an aircraft characteristics registry for design-aircraft nomination.

  Notes:
  - Allow the user to nominate a design aircraft and look up planning parameters from a registry-backed data source.
  - Import or maintain aircraft characteristics data outside the main dialog input JSON.
  - Use the selected aircraft record to populate runway planning and safeguarding parameters where applicable.

## EASA CS-ADR-DSN Issue 7 Ruleset

- [ ] Complete operational-grade source verification for the current EASA ruleset.

  Notes:
  - Authority target is EASA CS-ADR-DSN Issue 7.
  - Use case is both safeguarding/planning envelopes and aerodrome design compliance support.
  - Completed verification tranches: physical runway dimensions; taxiway/separation; OLS Tables J-1/J-2; runway markings; airfield ground lighting; declared distances/clearway/stopway.
  - Remaining verification work is consolidation-focused rather than a missing core tranche.
  - Add table/clause traceability and regression tests for promoted values.
  - Park interpretation policy for follow-up: decide whether conditional/guidance provisions are applied "as is", exposed as designer-selected options, or used to identify variance from a compliant standard.

## UK CAA CAP 168 Ruleset

- [ ] Continue CAP 168 source-loading beyond the initial physical-data tranche.

  Notes:
  - Registered ruleset id is `uk_caa_cap168_edition_13`.
  - Initial tranches cover reference code, runway minimum width, runway strips, runway markings, runway lighting, declared distances, clearway, stopway, parallel runway separation, and taxiway separation tables.
  - Remaining tranches: RESA and OLS.
  - Keep CAP 168 modules parameter-first, matching the MOS139 style rather than prose summaries.

## Placeholder Guidelines

- [ ] Implement Guideline A aircraft noise generation.

  Notes:
  - `guidelines/simple.py` currently logs Guideline A as not implemented.
  - Top-level Guideline A groups are treated as expected empty placeholders.
  - `README.md` documents Guideline A as placeholder-only.

- [ ] Implement Guideline H generation.

  Notes:
  - Top-level Guideline H groups are treated as expected empty placeholders.
  - `README.md` documents Guideline H as placeholder-only.

## Declared Distances And Stopways

- [x] Add stopway geometry generation.

  Notes:
  - `surfaces/physical.py` generates `Stopway` features when stopway length
    and runway width are present.
  - Generated stopway layers use the normal physical geometry
    output/grouping/style workflow.
  - Representative QGIS smoke-test evidence is recorded in
    `docs/mos139_smoke_test_2026-07-07.md`.
  - Broader declared-distance scenario validation remains tracked separately.

- [x] Add validation warnings for inconsistent declared-distance results.

  Notes:
  - `reports/declared_distances.py` validates inconsistent or impossible
    generated declared-distance values before output.
  - Warnings are stored on runway summaries and per-direction declared-distance
    records so they can appear in summary reports and generated layer notes.
  - Synthetic fixture-backed regression validation is covered by
    `tests/test_declared_distance_fixtures.py`.
  - Real/sample-airport validation remains tracked in
    `docs/development_milestones.md`.

- [x] Add optional declared-distance override fields.

  Notes:
  - Per-direction optional overrides for `TORA`, `TODA`, `ASDA`, and `LDA`
    are captured on each runway.
  - Override values are used as effective declared distances while calculated
    values are retained on the records as `calc_*` fields.
  - Inconsistent override relationships are surfaced as declared-distance
    warnings.

- [x] Feed declared-distance outputs into the runway summary report.

  Notes:
  - `reports/runway_summary.py` renders calculated `TORA`, `TODA`, `ASDA`,
    and `LDA` values plus captured warnings in generated runway summaries.
  - Published-distance source/notes are included in the summary assumptions.

## CNS Safeguarding

- [ ] Replace CNS `HeightRule = "TBD"` values with implemented height logic.

  Notes:
  - `dimensions/cns_dimensions.py` still has `TBD` height rules across CNS facility definitions.
  - `guidelines/simple.py` currently skips or warns for unimplemented CNS slope height rules.

- [ ] Implement specialised CNS geometry for GP and LOC facilities.

  Notes:
  - `dimensions/cns_dimensions.py` leaves Glide Path and Localiser definitions empty because they need different geometry logic.

## Airfield Ground Lighting

- [ ] Add explicit inputs for closed pre-threshold area AGL behaviour.

  Notes:
  - Closed pre-threshold areas are not inferred automatically.
  - `docs/airfield_ground_lighting_rules.md` records this as an explicit future input requirement.

- [ ] Add starter-extension, pad, and bypass geometry support for AGL.

  Notes:
  - Some AGL rules require starter-extension context not presently captured in the core runway input model.

- [ ] Add LAHSO lighting support.

  Notes:
  - Requires LAHSO-specific input, hold-short line location, and intersecting runway context.

## Controlling OLS

- [x] Validate and adopt the global cell-solver region construction for the
      current regression baseline.

  Notes:
  - See `docs/controlling_ols_global_cell_solver_plan.md`.
  - The global solver is active, with the pairwise subtract solver retained as
    a fallback when global linework cannot produce a usable partition.
  - QGIS 4 end-to-end fixtures cover YBBN single, YSSY intersecting, YSWS
    parallel, and a three-runway YSSY stress configuration.
  - The regression runner compares candidate/controlling coverage, region and
    class overlap, common-domain coverage, validity, IDs, and performance stages.
  - YMEN remains a useful additional targeted case for historical same-surface
    split-plane artefacts; it is no longer the only gate for the adopted solver.

- [x] Stabilise the OLS modernisation comparison geometry contract.

  Notes:
  - Baseline and future solved engines are reused rather than solved again for
    each comparison family.
  - Affine comparisons split exactly at the zero-height line. The 0.01 m
    tolerance identifies a wholly equivalent region but does not create a
    polygonal no-change strip between gain and loss.
  - Gain, loss, and no-change outputs are partitioned to be mutually exclusive,
    with final common-domain residual repair and stable comparison IDs.
  - Signed contours retain parent IDs; affine contours are exact and curved
    contours use the existing clipped triangulated approximation.
  - The 2026-07-11 suite passed 110 unit tests and all four end-to-end fixtures.

- [x] Complete the first OLS performance hardening pass.

  Notes:
  - Reuse solved lower envelopes and cached transition records.
  - Use lazy candidate spatial indexing as an exact-query prefilter.
  - Reuse shared/owned boundary probes without changing controller evaluation.
  - Use prepared-geometry containment before exact contour intersection and
    cache compatible affine lines and curved elevation samples.
  - The three-runway stress workflow reduced from approximately 56.6 seconds at
    the start of profiling to approximately 27–29 seconds on the current local
    QGIS 4.0.2 environment.

- [x] Improve the OLS tab workflow selection and validation.

  Completed:
  - Baseline, future Annex 14, and modernisation-comparison modes are explicit
    on the OLS tab while retaining the existing persisted policy identifiers.
  - OFS versus OES meaning is explained in future/comparison modes.
  - Mode-specific contour rows replace the previous always-expanded table.
  - OLS readiness and ADG requirements are shown inline beside the workflow.
  - Workload guidance reflects the selected mode and runway count.

- [x] Add long-running OLS workflow feedback and cancellation.

  Completed:
  - The footer reports determinate major-phase progress and elapsed time.
  - Users can request cancellation while a phase is active; processing stops at
    the next safe phase boundary and retains completed layers.
  - Partial output groups are repaired and empty groups removed before control
    returns to the dialog.

- [x] Consolidate OLS output controls and guidance.

  Completed:
  - Output selection is grouped under a stable Generated Outputs heading.
  - Mode, runway count, and workload are presented in one concise summary.
  - OFS/OES guidance is retained in a compact note, while ready-state and
    repeated warning text are suppressed from the inline validation area.

- [ ] Add release-oriented OLS performance regression thresholds.

  Notes:
  - Use the four committed fixtures as the benchmark matrix.
  - A QGIS 4.0.2 reference checkpoint is stored in
    `tests/fixtures/ols/performance_baseline_qgis4_2026-07-11.json`.
  - Geometry validity, coverage, and class exclusivity remain hard gates.
  - Runtime thresholds should detect material regression while allowing normal
    machine and GEOS variability.

- [ ] Root-cause remaining controlling-region geometry cleanup safeguards.

  Notes:
  - Reduce reliance on ring despiking and `buffer(0)` fallback by preventing invalid or out-and-back rings during subtraction.
  - Identify why any coverage gaps are produced by the primary lower-envelope solve.
  - Make the primary solve complete enough that local gap repair is not required for normal cases.
  - Decide whether same-candidate dissolves are permanent output normalisation or a workaround for region fragmentation.

- [ ] Harden controlling OLS comparison constructors.

  Notes:
  - Keep lower-region comparison constructors domain-limited so `_clip_lower_region_to_overlap(...)` remains a safety check.
  - Extend source-backed axis/conical validation beyond the current fixture
    matrix and reduce any remaining unresolved comparisons.
  - Add tests around the `None` versus empty-`QgsGeometry()` comparison contract.

- [ ] Rationalise controlling OLS geometry tolerances and topology keys.

  Notes:
  - Reduce geometry collections created by upstream overlay operations where practical.
  - Decide whether minimum-area thresholds should be fixed numerical tolerances or configurable QA parameters.
  - Replace coordinate-key transition de-duplication with adjacency-derived
    topology if transition diagnostics become promoted outputs.
  - Preserve the explicit OFS/OES and Inner Approach/Approach tie priorities;
    define the fallback policy for otherwise equivalent candidates.

## Runway Markings

- [ ] Add runway suitability inputs where marking applicability depends on unavailable pre-threshold areas.

  Notes:
  - Pre-threshold area markings still need suitability and starter-extension classification inputs to fully match MOS applicability.

- [ ] Extend runway holding position markings to cover the remaining MOS edge cases.

  Notes:
  - Pattern B still needs to be added for the multi-holding-position precision runway cases.
  - Note a from Table 6.56 still needs a geometry-aware elevation adjustment.

- [ ] Confirm touchdown zone marking defaults and runway-length basis.

  Open questions:
  - Should sealed runways below 30 m width or 1500 m length generate recommended touchdown zone markings by default, or only when an override is selected?
  - Does MOS 8.23(1) "runway length" mean threshold-to-threshold length, physical pavement length, or declared LDA/TORA for the runway end?
