# EASA CS-ADR-DSN source verification register

This document records the source-by-source verification status of the draft
EASA ruleset package in `rulesets/easa/`.

## Source baseline

| Item | Status |
| --- | --- |
| Implemented ruleset label | `EASA CS-ADR-DSN (Issue 7)` / `easa_cs_adr_dsn_issue_7` |
| Current EASA online source checked | Easy Access Rules for Aerodromes, revision from March 2026 |
| Version finding | The current EASA page states that the March 2026 revision incorporates ED Decision 2025/004/R, `CS-ADR-DSN Issue 7`, applicable since 24 May 2025. |
| Audit implication | The project has selected current EASA as the target, so the canonical ruleset is Issue 7. The old Issue 6 id is retained only as a compatibility alias. |

Primary online source:
https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-aerodromes

Current online publication:
https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-aerodromes-regulation-eu

## Verification summary

| Family | Module | Source basis | Status | Notes / actions |
| --- | --- | --- | --- | --- |
| Ruleset metadata | `rulesets/easa/metadata.py` | EASA Easy Access Rules publication status | Current target selected | Canonical id is `easa_cs_adr_dsn_issue_7`; `easa_cs_adr_dsn_issue_6` remains a compatibility alias. Status remains `draft` until table-level verification is complete. |
| Runway type classification | `rulesets/easa/classification.py` | Internal UI mapping to NI/NPA/PA categories | Accepted as adapter | This is mostly a plugin adapter, not a numeric CS table. Keep tests focused on stable UI-to-policy classification. |
| Runway strips | `rulesets/easa/physical_data.py` | CS ADR-DSN.B.155, B.160, B.175 | Source-matched spot check | Overall strip widths and strip extensions match the checked current Issue 7 online text. Graded widths match the CS and GM interpretation currently encoded, but should receive a full paragraph-by-paragraph Issue 7 comparison before promotion from draft. |
| RESA | `rulesets/easa/physical_data.py` | CS ADR-DSN.C.210, C.215 | Source-matched spot check | Applicability, 90 m minimum, 240 m code 3/4 recommendation, 120 m code 1/2 instrument recommendation, and width as at least twice runway width match checked source text. |
| Pavement / shoulders | `rulesets/easa/physical_data.py` | CS ADR-DSN.B.090, B.125, B.135 | Partial | References exist, but the plugin does not yet implement a complete EASA-specific pavement/shoulder sizing decision tree. |
| Taxiway/runway separations | `rulesets/easa/taxiway.py` | CS ADR-DSN.D.260 Table D-1 | Source-matched spot check | Sampled Table D-1 rows match implemented values, including code letter A values and the A/B/C runway-to-taxiway and taxiway/object separation pattern. Needs full automated table transcription check before marking fully verified. |
| Taxiway/taxiway and object separations | `rulesets/easa/taxiway.py` | CS ADR-DSN.D.260 Table D-1 | Source-matched spot check | The encoded per-code-letter values match sampled table values. Same action: complete row-by-row transcription audit. |
| Parallel runway separations | `rulesets/easa/taxiway.py` | CS ADR-DSN.B.050, B.055 | Review required | Values are EASA-referenced and plausible, but not yet independently checked during this audit. Needs full B.050/B.055 verification, including threshold stagger rules and operation-type assumptions. |
| OLS approach, transitional, IHS, conical, OFZ, TOCS | `rulesets/easa/ols_surfaces.py` | CS ADR-DSN Chapters H/J, Tables J-1/J-2 | Review required | Values are not just MOS copies, but the table is too consequential to rely on spot checks. Need full Table J-1/J-2 transcription verification. Specific review items: PA_I inner approach/inner transitional/balked landing inclusion, variable second/horizontal approach lengths, OHS guidance-only handling, and reduced TOCS slope guidance. |
| Outer horizontal surface | `rulesets/easa/ols_surfaces.py` | GM1 ADR-DSN.H.410 | Interpretive / guidance-only | Code correctly marks OHS as guidance-only, but generator behaviour should make that status visible in output layers if used. |
| Threshold markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.535 | Source-matched spot check | Runway width to stripe count values match the checked online table: 18/23/30/45/60 m map to 4/6/8/12/16 stripes. Stripe width of 1.8 m is an adopted representative value and should remain marked as interpretive. |
| Aiming point markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.540 Table L-1 | Source-matched with caveat | Offsets and dimensions match the checked Table L-1 bands where minimum range values are intentionally selected. Need explicit tests documenting the minimum-value choice. |
| Touchdown-zone markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.545 | Review required | Pair counts align with the checked source text, but generated offset lists are derived implementation choices. Confirm exact placement and omission rules against figures/tables before treating as source-verified. |
| Runway-holding position markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.575, D.335 | Accepted unsupported | Returning `None` is acceptable for now because the fixed-distance decision belongs to design/clearance criteria rather than the markings chapter alone. |
| Runway edge lighting | `rulesets/easa/lighting.py` | CS ADR-DSN.M.675 | Source-matched spot check | Instrument spacing 60 m and non-instrument spacing 100 m match checked source text. |
| Simple approach lighting | `rulesets/easa/lighting.py` | CS ADR-DSN.M.626 | Source-matched spot check | 420 m preferred length, 300 m crossbar, and 18/30 m crossbar length match checked source text. |
| Precision approach lighting | `rulesets/easa/lighting.py` | CS ADR-DSN.M.630, M.635 | Review required | Values are EASA-referenced, but full geometry/crossbar/side-row rules need detailed source verification. |
| Threshold/end/temporary displaced threshold lights | `rulesets/easa/lighting.py` | CS ADR-DSN.M.680, M.685 plus legacy fallback | Mixed | Threshold and end-light references exist, but `RUNWAY_LIGHTING_MIN_WIDTH_M` and temporary displaced threshold light counts explicitly retain MOS-derived pragmatic defaults. These are not EASA-source-verified values. |
| Runway centreline lights | `rulesets/easa/lighting.py` | CS ADR-DSN.M.690 | Mixed | Spacing values are EASA-referenced, but requirement/recommendation helpers currently use MOS-like heuristics. Needs EASA-specific applicability logic. |
| Touchdown-zone lights | `rulesets/easa/lighting.py` | CS ADR-DSN.M.695 | Source-matched spot check with caveat | TDZ length, 30/60 m row spacing, and at least three lights per barrette match checked source text. Nominal inner offset remains a selected design assumption. |

## High-confidence findings

1. The EASA package is not an empty scaffold. It contains EASA-specific numeric tables and EASA references in physical, taxiway, marking, lighting, and OLS modules.
2. The safest currently source-supported areas are runway strips, RESA, sampled taxiway separations, threshold markings, aiming point markings, runway edge lights, simple approach lighting, and TDZ-light base dimensions.
3. The riskiest areas are OLS Table J-1/J-2 completeness, parallel runway separations, precision approach lighting geometry, and lighting helpers that explicitly retain MOS-derived assumptions.
4. The edition decision is now settled: the code targets Issue 7/current EASA, while remaining marked draft until full table-level verification is complete.

## Recommended consolidation todo list

1. Add a machine-readable traceability table for EASA constants:
   - policy family
   - code key
   - implemented value
   - source clause/table
   - verification status
   - notes
2. Fully transcribe and test CS ADR-DSN.D.260 Table D-1 against `rulesets/easa/taxiway.py`.
3. Fully transcribe and test CS ADR-DSN Tables J-1 and J-2 against `rulesets/easa/ols_surfaces.py`.
4. Replace or explicitly label all MOS-derived fallbacks in `rulesets/easa/lighting.py`.
5. Promote only verified capability keys in `rulesets/easa/metadata.py`; downgrade anything that remains interpretive or only spot-checked.
6. Add regression tests that assert exact source references as well as numeric values for each verified family.

## Working conclusion

Treat the current EASA Issue 7 ruleset as a useful partial implementation, not
yet a dependable planning-standard authority. It contains real EASA-specific
values, but it needs table-level traceability before it should be used as a
high-confidence ruleset.
