# Development Milestones And Working TODO

This checklist consolidates the current development state from the README,
ruleset metadata, implementation notes, tests, and TODO ledger. It is intended
as a practical working list for deciding what to validate, consolidate, and
build next.

Last reviewed: 2026-07-07.

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
  - Stronger consistency warnings, published-distance overrides, and provenance
    fields are implemented as the declared-distance second pass.
  - Real/sample-airport validation scenarios remain future consolidation work.

- [x] AGL has a documented MOS-backed implementation surface.

  Notes:
  - The builder models plan-view light locations and display characteristics.
  - Limitations around photometrics, circuiting, serviceability, object
    screening, and operational intent are documented.

## Needs Testing And Consolidation

- [ ] Validate the modernised Annex 14 OFS/OES workflow in QGIS 4.

  Current implementation:
  - OFS and OES are generated as separate, styled layer families with runway
    and aerodrome-wide grouping.
  - Planar surface components are registered as 3D lower-envelope candidates.
  - OFS and OES are solved independently into controlling regions, transition
    diagnostics, and clipped controlling contours.
  - The integration audit checks layer structure, styles, labels, geometry
    validity, candidate coverage, region overlap, contour containment, and
    small interior rings.
  - Recent corrections cover contour clipping and dual-runway competition.

  Validation work:
  - Recover or create committed single-runway and dual-runway input fixtures
    for `tests/run_annex14_integration.py`.
  - Run the audit under QGIS 4 and retain its JSON audit and preview image as
    review evidence.
  - Add intersecting, parallel, and converging runway regression scenarios.
  - Confirm that candidate and transition layers remain diagnostic-only.
  - Reconcile `ols.controlling_lower_envelope` capability metadata, which still
    reports `unsupported`, after runtime validation establishes the appropriate
    promoted status.

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
  - No displaced thresholds.
  - One displaced threshold.
  - Reciprocal displaced thresholds.
  - Clearway and stopway entered by the user.
  - Takeoff or landing unavailable in one direction.
  - Confirm warnings for inconsistent results across representative scenarios.

- [ ] Consolidate stopway handling.

  Notes:
  - Stopway inputs currently contribute to ASDA.
  - Stopway geometry generation is implemented in the physical runway
    protection layer workflow.
  - QGIS memory and GeoPackage output smoke-test evidence is recorded.
  - Remaining consolidation work is broader declared-distance scenario
    validation for representative runway configurations.

- [ ] Promote or contain Controlling OLS POC outputs.

  Notes:
  - The lower-envelope engine has proof-of-concept coverage for planar,
    transitional, conical, transition-edge, and clipped-contour diagnostics.
  - It remains marked experimental and should stay in the debug/development
    output group until QGIS geometry validation is complete.
  - Treat the established MOS/NASF controlling OLS POC separately from the new
    modernised Annex 14 OFS/OES lower-envelope workflow.

- [ ] Add tests around Controlling OLS geometry contracts where possible outside
      QGIS.

  Focus:
  - `None` means unresolved/unknown.
  - Empty `QgsGeometry()` means resolved and losing the overlap.
  - Equal-elevation ties are currently deterministic by candidate registration
    order, not by an explicit policy.

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

- [ ] Consolidate modernised Annex 14 OFS/OES controlling output.

  Work items:
  - Complete the QGIS 4 integration pass for single- and multi-runway cases.
  - Confirm complete candidate coverage with no material overlap or contour
    leakage for each OFS/OES family.
  - Document which complex transitional and inner-transitional components are
    complete, approximated, or still pending.
  - Align ruleset capability metadata and `rulesets/annex14/README.md` with the
    verified implementation state.
  - Keep the ruleset gated as a draft future standard and retain the
    21 November 2030 applicability warning.

- [ ] Harden the Controlling OLS engine.

  Work items:
  - Reduce reliance on ring despiking, `buffer(0)`, and local coverage repair.
  - Complete axis/conical comparison handling.
  - Replace WKT-based transition de-duplication with a topology-aware key if
    transition diagnostics are promoted.
  - Define an explicit equal-elevation tie-break policy.

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
  - [x] Source and notes fields for published data provenance.
  - [x] Stronger validation for impossible or inconsistent declared distances.
  - [x] Unit tests for calculated distances, override application, provenance,
    and summary warnings.

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
  - Layer grouping and dual-runway controlling behaviour received targeted
    corrections in the latest development branch.
  - The headless QGIS integration audit exists but still needs reproducible
    input fixtures and a recorded QGIS 4 validation run before promotion.
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
- [ ] 3. Re-establish a reproducible Annex 14 baseline when advanced-module
      work resumes: add representative fixtures and run the headless QGIS 4
      integration audit.
- [ ] 4. Close the modernised Annex 14 branch by addressing audit findings,
      reconciling capability metadata and documentation, and preserving the
      results as regression evidence.
- [ ] 5. Decide whether the established MOS/NASF Controlling OLS remains
      diagnostic-only or moves toward promoted output; then harden accordingly.
- [ ] 6. Close the highest-value AGL and marking gaps that depend on missing UI
      context.
- [ ] 7. Add the aircraft characteristics registry as a new, isolated data
      service and wire it into design-aircraft nomination.
- [ ] 8. Continue EASA and Annex 14 expansion only with clear capability gating
      so draft/scaffolded outputs cannot be mistaken for complete coverage.

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
- [ ] 2026-07-07: the broader unittest command including
      `tests.test_ols_modernisation_comparison` could not complete outside the
      QGIS runtime because `qgis` Python bindings were unavailable.
- [ ] Run `tests/run_annex14_integration.py` under QGIS 4 with committed
      single-runway and dual-runway fixtures; record audit JSON and previews.
