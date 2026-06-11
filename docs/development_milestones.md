# Development Milestones And Working TODO

This checklist consolidates the current development state from the README,
ruleset metadata, implementation notes, tests, and TODO ledger. It is intended
as a practical working list for deciding what to validate, consolidate, and
build next.

Last reviewed: 2026-06-11.

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
  - The local test run on 2026-06-11 passed: 36 tests, 1 QGIS-runtime skip.

- [x] Declared-distance first pass is implemented.

  Notes:
  - Clearway and stopway inputs, persistence, validation, calculated distance
    records, centreline field population, and TOCS clearway reuse are documented
    as complete.
  - Published-distance overrides remain future work.

- [x] AGL has a documented MOS-backed implementation surface.

  Notes:
  - The builder models plan-view light locations and display characteristics.
  - Limitations around photometrics, circuiting, serviceability, object
    screening, and operational intent are documented.

## Needs Testing And Consolidation

- [ ] Run a QGIS smoke-test pass for MOS139 default generation.

  Test checklist:
  - Basic single-runway airport with memory layers.
  - File output to GeoPackage.
  - Physical runway geometry, strips, RESA, clearways, markings, AGL, OLS,
    MET, and NASF outputs.
  - Save/load dialog JSON round trip.

- [ ] Validate declared-distance outputs against real or known sample airports.

  Test checklist:
  - No displaced thresholds.
  - One displaced threshold.
  - Reciprocal displaced thresholds.
  - Clearway and stopway entered by the user.
  - Takeoff or landing unavailable in one direction.
  - Confirm warnings for inconsistent results.

- [ ] Consolidate stopway handling.

  Notes:
  - Stopway inputs currently contribute to ASDA.
  - Stopway geometry generation is still tracked as outstanding work.

- [ ] Promote or contain Controlling OLS POC outputs.

  Notes:
  - The lower-envelope engine has proof-of-concept coverage for planar,
    transitional, conical, transition-edge, and clipped-contour diagnostics.
  - It remains marked experimental and should stay in the debug/development
    output group until QGIS geometry validation is complete.

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
  - EASA has policy-table coverage for several domains, but its profile status
    is draft and many capabilities are partial.
  - Declared distances, clearway, stopway, and controlling OLS are explicitly
    unsupported.

## In Development

- [ ] Harden the Controlling OLS engine.

  Work items:
  - Reduce reliance on ring despiking, `buffer(0)`, and local coverage repair.
  - Complete axis/conical comparison handling.
  - Replace WKT-based transition de-duplication with a topology-aware key if
    transition diagnostics are promoted.
  - Define an explicit equal-elevation tie-break policy.

- [ ] Finish MOS139 stopway geometry.

  Work items:
  - Generate stopway features when stopway length is entered.
  - Keep output grouping and styling aligned with physical runway geometry.
  - Ensure runway summaries distinguish calculated ASDA from generated stopway
    geometry.

- [ ] Complete declared-distance second pass.

  Work items:
  - Optional `TORA`, `TODA`, `ASDA`, and `LDA` override fields.
  - Source and notes fields for published data provenance.
  - Stronger validation for impossible or inconsistent declared distances.
  - Runway summary report integration.

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

## Scaffolded Or Future Enhancements

- [ ] Annex 14 current OLS.

  Status:
  - Registered as a selectable profile.
  - Current enforceable OLS dimensions and geometry are still scaffolded.

- [ ] Annex 14 modernised OFS/OES.

  Status:
  - Future OFS/OES ruleset is registered as draft and not enforceable until
    2030-11-21.
  - ADG and reference-code classification, OFS/OES lookup tables, and first-pass
    geometry exist.
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

- [ ] 1. QGIS smoke-test the current MOS139 workflow and record any runtime
      issues before adding new capability.
- [ ] 2. Consolidate declared distances and stopway geometry, because this is
      already partially delivered and user-facing.
- [ ] 3. Decide whether Controlling OLS remains diagnostic-only or moves toward
      promoted output; then harden accordingly.
- [ ] 4. Close the highest-value AGL and marking gaps that depend on missing UI
      context.
- [ ] 5. Add the aircraft characteristics registry as a new, isolated data
      service and wire it into design-aircraft nomination.
- [ ] 6. Continue EASA and Annex 14 expansion only with clear capability gating
      so draft/scaffolded outputs cannot be mistaken for complete coverage.

## Verification Snapshot

- [x] `python3 -m unittest tests.test_rulesets tests.test_frameworks`
- [x] `python3 -m py_compile safeguarding_builder.py safeguarding_builder_dialog.py dialog/*.py core/styles.py surfaces/physical.py guidelines/ols_guideline.py surfaces/specialised.py core/layers.py guidelines/simple.py guidelines/guideline_constants.py dimensions/*.py rulesets/*.py rulesets/mos139/*.py frameworks/*.py frameworks/nasf/*.py`
