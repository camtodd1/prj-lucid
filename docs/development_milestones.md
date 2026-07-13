# Development Milestones And Working TODO

This checklist consolidates the current development state from the README,
ruleset metadata, implementation notes, tests, and TODO ledger. It is intended
as a practical working list for deciding what to validate, consolidate, and
build next.

Last reviewed: 2026-07-12.

## High Confidence Delivery

- [x] Core plugin structure is modularised.

  Notes:
  - `safeguarding_builder.py` is primarily lifecycle, orchestration, shared
    geometry helpers, and Guideline E logic.
  - Dialog, output handling, physical surfaces, AGL, specialised surfaces,
    rulesets, and frameworks are split into focused modules.

- [x] MOS139 is the default and strongest ruleset.

  Notes:
  - Registered as `mos139_2019` with `stable` status.
  - Capabilities marked supported include runway type classification, pavement,
    shoulders, strips, RESA, clearway, parallel runway separation, OLS, runway
    markings, AGL, approach lighting, and calculated declared distances.

- [x] NASF Australia is the active external safeguarding framework.

  Notes:
  - Registered as `nasf_aus` with `stable` status.
  - Supported guideline families include windshear, wildlife, wind turbine,
    lighting control, OLS planning, and public safety areas.

- [x] Ruleset and framework registries have lightweight automated coverage.

  Notes:
  - Registry aliases, structured payload normalisation, capability metadata,
    and service contracts are covered by unit tests.
  - The local test run on 2026-07-06 passed: 62 tests, 1 QGIS-runtime skip.

- [x] Declared-distance first pass is implemented.

  Notes:
  - Clearway and stopway inputs, persistence, validation, calculated distance
    records, centreline field population, runway summary report integration,
    and TOCS clearway reuse are documented as complete.
  - Stopway geometry generation is implemented when stopway length and runway
    width are present, with QGIS smoke-test evidence recorded in
    `docs/mos139_smoke_test_2026-07-07.md`.
  - Stronger consistency warnings and published-distance overrides are
    implemented as the declared-distance second pass.
  - Synthetic fixture-backed regression scenarios cover representative
    declared-distance calculations, overrides, and warnings.
  - Real/sample-airport validation scenarios remain future consolidation work.

- [x] AGL has a documented MOS-backed implementation surface.

  Notes:
  - The builder models plan-view light locations and display characteristics.
  - Limitations around photometrics, circuiting, serviceability, object
    screening, and operational intent are documented.

## Needs Testing And Consolidation

- [x] Validate the modernised Annex 14 OFS/OES workflow in QGIS 4.

  Current implementation:
  - OFS and OES are generated as separate, styled layer families with runway
    and aerodrome-wide grouping.
  - Planar surface components are registered as 3D lower-envelope candidates.
  - OFS and OES are solved independently into controlling regions, transition
    diagnostics, and clipped controlling contours.
  - The integration audit checks layer structure, styles, labels, geometry
    validity, candidate coverage, region overlap, contour containment, and
    small interior rings.
  - Committed regression fixtures cover YBBN single-runway, YSSY intersecting
    dual-runway, YSWS parallel dual-runway, and a three-runway YSSY stress case.
  - `tests/run_ols_workflow_regression.py` exercises the complete dialog-to-layer
    workflow under QGIS 4 and checks candidate coverage, controlling-region
    overlap, comparison-domain coverage, class overlap, geometry validity,
    duplicate IDs, and performance stages.
  - The 2026-07-11 QGIS 4.0.2 run passed all four cases with no invalid or empty
    geometry and no duplicate comparison IDs.
  - Modernisation comparison gain/loss regions now meet directly at the
    zero-height line. The comparison tolerance is retained only for controller
    pairs that are wholly equivalent, preventing narrow no-change border strips.

  Remaining promotion work:
  - Confirm whether candidate and transition layers remain diagnostic-only in
    the promoted output contract.
  - Reconcile `ols.controlling_lower_envelope` capability metadata after that
    output-contract decision.
  - Retain JSON benchmark evidence for release candidates rather than committing
    every local profiling run.

- [x] Run a QGIS smoke-test pass for MOS139 default generation.

  Test checklist:
  - Basic single-runway airport with memory layers.
  - File output to GeoPackage.
  - Physical runway geometry, strips, RESA, clearways, markings, AGL, OLS,
    MET, and NASF outputs.
  - Save/load dialog JSON round trip.
  - Evidence recorded in `docs/mos139_smoke_test_2026-07-07.md`.

- [ ] Validate declared-distance outputs against real or known sample airports.

  Test checklist:
  - Synthetic regression fixtures now cover no displaced thresholds,
    displaced-threshold/clearway/stopway combinations, unavailable operations,
    published overrides, and invalid distance relationships.
  - Add source-backed sample-airport fixtures with authoritative published
    values.
  - Compare calculated and override values against known sample inputs.
  - Retain fixture outputs as review evidence when promoting behaviour.

- [ ] Consolidate stopway handling.

  Notes:
  - Stopway inputs currently contribute to ASDA.
  - Stopway geometry generation is implemented in the physical runway
    protection layer workflow.
  - QGIS memory and GeoPackage output smoke-test evidence is recorded.
  - Synthetic declared-distance fixtures now cover clearway/stopway and
    unavailable-takeoff warning behaviour.
  - Remaining consolidation work is source-backed sample-airport validation
    for representative runway configurations.

- [x] Consolidate Controlling OLS outputs and remove proof-of-concept notation.

  Completed:
  - The lower-envelope engine now has repeatable QGIS 4 regression coverage for
    planar, transitional, conical, transition-edge, clipped-contour, OFS/OES,
    and modernisation-comparison outputs.
  - Solved regions and clipped contours are user-facing outputs under
    `Controlling Surfaces`; candidate surfaces and transition boundaries remain
    diagnostics under `99 Debug / Development`.
  - Legacy POC-labelled layers are still migrated into diagnostics when an old
    project tree is repaired. New output names contain no POC notation.
  - The MOS139 and modernised Annex 14 lower-envelope capabilities are marked
    `partial`, reflecting defined generated coverage rather than regulatory
    completion. Remaining topology hardening stays tracked below.

- [x] Add automated tests around Controlling OLS geometry contracts.

  Focus:
  - Unit coverage distinguishes unresolved `None` from resolved empty geometry.
  - Comparison tests cover affine equality splitting, curved fallback contours,
    common-domain repair, class exclusivity, solved-engine reuse, spatial
    prefiltering, transition-boundary caching, and contour cache reuse.
  - Explicit family and nested-surface priorities exist for relevant ties;
    registration order remains the fallback for otherwise equivalent candidates.

- [ ] Review runway marking assumptions in QGIS.

  Focus:
  - Threshold piano keys for supported widths.
  - Aiming point and touchdown-zone defaults.
  - Pre-threshold area markings.
  - Holding-position markings, especially unsupported Table 6.56 edge cases.

- [ ] Review AGL output with representative runway configurations.

  Focus:
  - Non-instrument, non-precision, precision CAT I, and precision CAT II/III.
  - Displaced thresholds.
  - Stopway lights.
  - RVR below 350 m option.
  - Coincident light resolution and QML styling.

- [ ] Validate EASA draft behaviour in the plugin UI.

  Notes:
  - EASA targets current CS-ADR-DSN Issue 7.
  - The completion target is operational-grade verification: table/clause
    traceability, tests for key numeric lookups, and documented interpretation
    choices.
  - EASA has policy-table coverage for several domains, but its profile status
    remains draft and many capabilities are partial until table-level
    verification is complete.
  - Declared distances, clearway, and stopway policy lookups are implemented
    and covered by unit tests; plugin UI/runtime behaviour still needs review.
  - Controlling OLS remains explicitly unsupported.
  - Open interpretation question: whether conditional/guidance provisions are
    applied "as is", exposed as designer-selected options, or used to identify
    variance from a compliant standard.

## In Development

- [x] Consolidate modernised Annex 14 OFS/OES controlling output.

  Work items:
  - [x] Complete the QGIS 4 integration pass for single- and multi-runway cases.
  - [x] Confirm candidate coverage with no material controlling or comparison
    class overlap for each OFS/OES family.
  - [x] Reuse solved baseline/future envelopes in the comparison workflow.
  - [x] Add exact affine gain/loss splitting and retain no-change only for wholly
    equivalent regions.
  - [x] Add stable, layer-qualified comparison IDs and parent-linked contours.
  - [ ] Document which complex transitional and inner-transitional components
    are complete, approximated, or still pending.
  - [ ] Align capability metadata and `rulesets/annex14/README.md` with the
    verified implementation and promotion boundary.
  - Keep the ruleset gated as a draft future standard and retain the
    21 November 2030 applicability warning.

- [x] Stabilise and lock the MOS139 Controlling OLS engine.

  Completed:
  - MOS139 axis/conical equality uses one sampled zero contour as authoritative
    construction linework; no independent TIN boundary is introduced afterward.
  - Sub-metre polygonized cells are retained at the curve, eliminating the
    detached Approach/TOCS wedges and visible Conical gaps seen during YBBN
    troubleshooting.
  - Shared region edges are merged by controller pair for continuous diagnostic
    transitions, while controlling polygons remain the authoritative product.
  - YBBN, YSSY intersecting, YSWS parallel, and YSSY stress fixtures have zero
    unassigned/ambiguous cells and zero MOS139 recovery activation. Manual
    visual validation passed YMML in projected metre CRS EPSG:32755.
  - Final controller IDs, region counts, areas, and geometry digests are frozen
    by the 12 July 2026 MOS139 compatibility lock.

- [ ] Continue production hardening for modernised Annex 14 OFS/OES.

  Remaining work is isolated from the locked MOS139 geometry and includes
  source-backed validation, complex transitional components, release timing,
  and removal of Annex-specific final partition recovery.

- [x] Finish MOS139 stopway geometry.

  Work items:
  - Stopway features are generated when stopway length is entered and runway
    width is available.
  - Output grouping and styling are aligned with physical runway protection
    geometry.
  - Runway summaries include declared-distance values and generated feature
    counts; representative QGIS smoke testing remains tracked under
    consolidation.

- [x] Complete declared-distance second pass.

  Work items:
  - [x] Optional `TORA`, `TODA`, `ASDA`, and `LDA` override fields.
  - [x] Stronger validation for impossible or inconsistent declared distances.
  - [x] Unit tests for calculated distances, override application, warning
    annotations, and synthetic fixture-backed regression scenarios.

- [ ] Resolve CNS partial implementation.

  Work items:
  - Replace `HeightRule = "TBD"` entries with implemented height logic.
  - Implement specialised Glide Path and Localiser geometry.

- [ ] Complete remaining AGL context inputs.

  Work items:
  - Closed pre-threshold area behaviour.
  - Starter-extension, pad, and bypass geometry support.
  - LAHSO lighting support.

- [ ] Extend runway marking coverage.

  Work items:
  - Alternate marking rulesets such as Annex 14.
  - Suitability and starter-extension inputs for pre-threshold area markings.
  - Remaining holding-position edge cases.
  - Polygon glyph geometry for runway designators.
  - Touchdown-zone default policy decision.

- [ ] Complete safeguarding generator terminology refactor.

  Work items:
  - Keep generic generator entrypoints such as wildlife, lighting control, CNS
    building restricted areas, public safety areas, windshear, and runway OLS.
  - Retain NASF guideline references only as source/provenance metadata.
  - Decide whether layer-tree group keys should remain framework guideline
    letters or move to output-family keys with framework-specific labels.
  - Remove legacy `process_guideline_*` aliases once downstream call sites and
    saved expectations no longer need them.

- [ ] Complete EASA CS-ADR-DSN Issue 7 operational-grade ruleset verification.

  Work order:
  - [x] Physical runway dimensions.
  - [x] Taxiway and separation standards.
  - [x] OLS tables and geometry applicability.
  - [x] Runway markings.
  - [x] Airfield ground lighting.
  - [x] Declared distances, clearway, and stopway.

  Work items:
  - Continue building machine-readable traceability for each implemented EASA value.
  - Continue adding regression tests asserting source references and numeric values.
  - Remove, replace, or explicitly label MOS-derived fallbacks.
  - Keep interpretation-policy decisions parked until conditional/guidance
    provisions need to be applied in output logic.
  - Preserve the dual use case: safeguarding/planning envelopes and aerodrome
    design compliance support.

- [ ] Close remaining ruleset/framework architecture decisions.

  Work items:
  - Decide whether NASF outputs remain enabled by default when a non-MOS
    aerodrome standard is selected.
  - Decide whether the UI should split `Aerodrome Standard` and
    `Supplementary Frameworks` before the next ruleset is promoted.
  - Decide whether generated layers need a generic regulatory reference field
    alongside legacy fields such as `ref_mos` and `ref_nasf`.
  - Confirm that the selected aerodrome standard remains airport-wide unless a
    future mixed-standard workflow is explicitly designed.
  - Define the first golden airport/runway scenario set for MOS139 regression.

## Scaffolded Or Future Enhancements

- [ ] Annex 14 current OLS.

  Status:
  - Registered as a selectable profile.
  - Current enforceable OLS dimensions and geometry are still scaffolded.

- [ ] Annex 14 modernised OFS/OES.

  Status:
  - Future OFS/OES ruleset is registered as draft and not enforceable until
    2030-11-21.
  - ADG and reference-code classification and OFS/OES lookup tables exist.
  - Styled OFS/OES plan-view surfaces and elevation contours are generated in
    separate output families.
  - Planar components participate in independent OFS and OES controlling
    lower-envelope solves, including controlling regions, transition
    diagnostics, and clipped contours.
  - The modernisation comparison produces mutually exclusive gain, loss, and
    genuinely unchanged polygons over the common baseline/future domain, plus
    parent-linked signed change contours and equal-height transitions.
  - Four committed end-to-end fixtures now cover single, intersecting, parallel,
    and stress configurations under QGIS 4.
  - The workflow is mostly stable computationally; it remains a draft future
    standard and is not promoted as enforceable before 2030-11-21.
  - Full complex transitional and inner-transitional geometry, plus
    TODA/clearway-aware departure starts, remain incomplete.
  - Physical, taxiway, markings, lighting, declared-distance, and current OLS
    source tables remain incomplete or unsupported.

- [ ] Aircraft characteristics registry.

  Status:
  - CSV size reviewed as realistic for an in-plugin registry.
  - Future work is to import or maintain aircraft data outside the main dialog
    JSON and let users nominate a design aircraft for planning-parameter lookup.

- [ ] Guideline A aircraft noise generation.

  Status:
  - Currently logged as not implemented.

- [ ] Guideline H generation.

  Status:
  - Currently documented as placeholder-only.

## Suggested Working Order

- [x] 1. QGIS smoke-test the current MOS139 workflow and record any runtime
      issues before adding new capability.
- [x] 2. Consolidate declared distances around warning/override behaviour,
      because the first and second passes are implemented and user-facing.
- [x] 3. Establish a reproducible Annex 14 baseline with representative fixtures
      and a headless QGIS 4 end-to-end regression runner.
- [ ] 4. Close the modernised Annex 14 branch by reconciling capability metadata,
      regulatory-scope documentation, and the promoted/diagnostic layer contract.
- [ ] 5. Decide whether the established MOS/NASF Controlling OLS remains
      diagnostic-only or moves toward promoted output; then harden accordingly.
- [ ] 6. Close the highest-value AGL and marking gaps that depend on missing UI
      context.
- [ ] 7. Add the aircraft characteristics registry as a new, isolated data
      service and wire it into design-aircraft nomination.
- [ ] 8. Continue EASA and Annex 14 expansion only with clear capability gating
      so draft/scaffolded outputs cannot be mistaken for complete coverage.

Immediate OLS working order after the 2026-07-11 stability checkpoint:

- [x] Improve the OLS dialog mode selection, OFS/OES explanation, validation
      placement, and workload explanation.
- [x] Add phase-based progress and safe cancellation between candidate creation,
      envelope solving, transition generation, comparison, and contours.
- [ ] Turn the saved QGIS 4.0.2 performance checkpoint into release-oriented
      regression thresholds; retain geometry and coverage gates as hard failures.
- [x] Consolidate the user-facing versus diagnostic layer contract and remove
      proof-of-concept nomenclature.

  - Solved controlling regions and clipped contours are published under
    `Controlling Surfaces`; solver candidates and transition boundaries stay in
    `99 Debug / Development`.
  - Capability metadata now records lower-envelope coverage as `partial`; it
    does not imply complete regulatory or topology coverage.

## Verification Snapshot

- [x] 2026-07-06: `python3 -m unittest tests.test_rulesets tests.test_frameworks`
      passed 62 tests with 1 expected QGIS-runtime skip.
- [x] 2026-07-06: `python3 -m compileall -q .`
- [x] 2026-07-07: `python3 -m unittest tests.test_rulesets tests.test_frameworks`
      passed 62 tests with 1 expected QGIS-runtime skip.
- [x] 2026-07-07: headless QGIS 4 MOS139 smoke test passed for memory and
      GeoPackage output; evidence recorded in
      `docs/mos139_smoke_test_2026-07-07.md`.
- [x] 2026-07-07: `python3 -m unittest tests.test_declared_distances
      tests.test_rulesets tests.test_frameworks` passed 72 tests with 1
      expected QGIS-runtime skip.
- [x] 2026-07-07: recorded that the broader unittest command including
      `tests.test_ols_modernisation_comparison` requires the QGIS Python runtime;
      the limitation is superseded by the successful QGIS 4 runs below.
- [x] 2026-07-11: QGIS 4.0.2 unittest discovery passed 110 tests.
- [x] 2026-07-11: `tests/run_ols_workflow_regression.py` passed YBBN single,
      YSSY intersecting, YSWS parallel, and YSSY three-runway stress fixtures.
      The run reported zero invalid/empty geometries, zero duplicate comparison
      IDs, and no material unclassified or overlapping comparison area.
- [x] 2026-07-11: YBBN no-change regression confirmed OFS has no unchanged
      polygons and OES retains only four broad, exactly equal regions. Across
      the four fixtures the narrowest legitimate unchanged region had a
      74.5 m area/perimeter width proxy.
- [x] 2026-07-12: MOS139 curved Approach/TOCS-to-Conical boundaries were
      stabilised and accepted after visual checks at YBBN, YSSY, YSWS, and YMML.
      YMML passed in EPSG:32755; the committed YBBN/YSSY/YSWS matrix completed
      with zero MOS139 gaps, refinements, fallbacks, or repairs. The accepted
      signatures are enforced by the MOS139 compatibility lock.
- [x] 2026-07-13: adopted bounded endpoint-clamped smoothing for MOS139
      Approach/TOCS-to-Conical equality curves before polygonization. Interior
      vertices are projected back to equality and accepted only when curvature,
      endpoint, displacement, residual, domain, and topology gates pass. The
      five-fixture regression and 55 focused unit tests passed. Vertex-density
      reduction remains a separately gated future performance experiment.
- [ ] 2026-07-13 visual trial: endpoint-constrained regularised least-squares
      B-spline fitting now approximates all ordered intersection observations
      without interpolating their local jitter. The stronger inspection profile
      retains 75% of the fitted position and blends 25% towards equality because
      full reprojection removed most visible smoothing. On YMML, peak and RMS
      curvature change improved by about 65% and 68% respectively versus the
      first fitted trial, with zero endpoint shift and a maximum 0.0328 m
      elevation-equality residual. Export and diagnostics are ready for review;
      the accepted MOS139 geometry lock is intentionally unchanged.
