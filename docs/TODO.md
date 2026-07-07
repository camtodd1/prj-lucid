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

- [ ] Add validation warnings for inconsistent declared-distance results.

  Notes:
  - Validate inconsistent or impossible generated declared-distance values before output.

- [ ] Add optional declared-distance override fields.

  Notes:
  - Add per-direction optional overrides for `TORA`, `TODA`, `ASDA`, and `LDA`.
  - Add source/notes fields for published data provenance.

- [x] Feed declared-distance outputs into the runway summary report.

  Notes:
  - `reports/runway_summary.py` renders calculated `TORA`, `TODA`, `ASDA`,
    and `LDA` values plus captured warnings in generated runway summaries.
  - Published-distance overrides and provenance fields remain part of the
    declared-distance second pass.

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

- [ ] Validate and promote the global cell-solver region construction.

  Notes:
  - See `docs/controlling_ols_global_cell_solver_plan.md`.
  - Use YMEN as the first regression case for same-surface split-plane
    artefacts across OHS, Conical, TOCS, Approach, and Transitional outputs.
  - Compare candidate footprints, solved regions, transition diagnostics, and
    clipped contours before replacing the legacy pairwise subtract fallback.

- [ ] Root-cause remaining controlling-region geometry cleanup safeguards.

  Notes:
  - Reduce reliance on ring despiking and `buffer(0)` fallback by preventing invalid or out-and-back rings during subtraction.
  - Identify why any coverage gaps are produced by the primary lower-envelope solve.
  - Make the primary solve complete enough that local gap repair is not required for normal cases.
  - Decide whether same-candidate dissolves are permanent output normalisation or a workaround for region fragmentation.

- [ ] Harden controlling OLS comparison constructors.

  Notes:
  - Keep lower-region comparison constructors domain-limited so `_clip_lower_region_to_overlap(...)` remains a safety check.
  - Complete axis/conical comparison handling enough that unresolved axis-vs-conical overlaps no longer require candidate removal and coverage repair.
  - Add tests around the `None` versus empty-`QgsGeometry()` comparison contract.

- [ ] Rationalise controlling OLS geometry tolerances and topology keys.

  Notes:
  - Reduce geometry collections created by upstream overlay operations where practical.
  - Decide whether minimum-area thresholds should be fixed numerical tolerances or configurable QA parameters.
  - Replace WKT-based transition de-duplication with a topology/keying strategy if transition diagnostics become promoted outputs.
  - Define an explicit equal-elevation tie-break policy instead of relying on candidate registration order.

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
