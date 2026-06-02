# TODO

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

- [ ] Add stopway geometry generation.

  Notes:
  - Runway summaries currently warn when stopway length contributes to ASDA but no `Stopway` features are generated.
  - Keep generated stopway layers in the normal physical geometry output/grouping/style workflow.

- [ ] Add validation warnings for inconsistent declared-distance results.

  Notes:
  - Validate inconsistent or impossible generated declared-distance values before output.

- [ ] Add optional declared-distance override fields.

  Notes:
  - Add per-direction optional overrides for `TORA`, `TODA`, `ASDA`, and `LDA`.
  - Add source/notes fields for published data provenance.

- [ ] Feed declared-distance outputs into the runway summary report.

  Notes:
  - Include calculated declared distances and relevant warnings in generated runway summaries.

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

- [ ] Confirm touchdown zone marking defaults and runway-length basis.

  Open questions:
  - Should sealed runways below 30 m width or 1500 m length generate recommended touchdown zone markings by default, or only when an override is selected?
  - Does MOS 8.23(1) "runway length" mean threshold-to-threshold length, physical pavement length, or declared LDA/TORA for the runway end?

- [ ] Add polygon glyph geometry for runway designation markings.

  Notes:
