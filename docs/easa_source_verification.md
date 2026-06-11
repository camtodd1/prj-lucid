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
| Verification target | Operational-grade: every promoted value should have table/clause traceability, tests for key numeric lookups, and documented interpretation choices. |
| Use case | Both safeguarding/planning envelopes and aerodrome design compliance support. Outputs must distinguish source-applied requirements from variance/compliance assessment assumptions where relevant. |

Primary online source:
https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-aerodromes

Current online publication:
https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-aerodromes-regulation-eu

## Verification summary

| Family | Module | Source basis | Status | Notes / actions |
| --- | --- | --- | --- | --- |
| Ruleset metadata | `rulesets/easa/metadata.py` | EASA Easy Access Rules publication status | Current target selected | Canonical id is `easa_cs_adr_dsn_issue_7`; `easa_cs_adr_dsn_issue_6` remains a compatibility alias. Status remains `draft` until table-level verification is complete. |
| Runway type classification | `rulesets/easa/classification.py` | Internal UI mapping to NI/NPA/PA categories | Accepted as adapter | This is mostly a plugin adapter, not a numeric CS table. Keep tests focused on stable UI-to-policy classification. |
| Runway strips | `rulesets/easa/physical_data.py` | CS ADR-DSN.B.155, B.160, B.175 | Operational verified | Overall strip widths, strip extensions, graded widths, and precision/NPA/non-instrument source references are implemented with traceability metadata and regression tests. |
| RESA | `rulesets/easa/physical_data.py` | CS ADR-DSN.C.210, C.215 | Operational verified | Applicability, 90 m minimum, 240 m code 3/4 recommendation, 120 m code 1/2 instrument recommendation, and width basis are implemented with traceability metadata and regression tests. |
| Pavement / shoulders | `rulesets/easa/physical_data.py` | CS ADR-DSN.B.090, B.125, B.135 | Partial | References exist, but the plugin does not yet implement a complete EASA-specific pavement/shoulder sizing decision tree. |
| Taxiway/runway separations | `rulesets/easa/taxiway.py` | CS ADR-DSN.D.260 Table D-1 | Operational verified | Table D-1 runway-to-taxiway centre line separations are implemented with traceability metadata and regression tests across encoded code number/code letter/runway-type combinations. |
| Taxiway/taxiway and object separations | `rulesets/easa/taxiway.py` | CS ADR-DSN.D.260 Table D-1 | Operational verified | Table D-1 taxiway-to-taxiway, taxiway-to-object, stand taxilane-to-stand taxilane, and stand taxilane-to-object separations are implemented with traceability metadata and regression tests. |
| Parallel runway separations | `rulesets/easa/taxiway.py` | CS ADR-DSN.B.050, B.055 | Operational verified | Non-instrument simultaneous-use minima, instrument operation-type minima, and segregated-operation threshold stagger adjustments are implemented with traceability metadata and regression tests. |
| OLS approach, transitional, IHS, conical, OFZ, TOCS | `rulesets/easa/ols_surfaces.py` | CS ADR-DSN Chapters H/J, Tables J-1/J-2 | Operational verified | Table J-1 and J-2 values are implemented with traceability metadata and regression tests covering approach sections, conical, IHS, transitional, precision OFZ-family dimensions, TOCS footnotes, variable approach sections, and reduced TOCS slope guidance. PA CAT I OFZ-family applicability remains explicitly marked interpretive. |
| Outer horizontal surface | `rulesets/easa/ols_surfaces.py` | GM1 ADR-DSN.H.410 | Guidance-only verified | GM1 broad-specification values are implemented and regression-covered as guidance-only, not as a Table J-1 certification surface. Generator behaviour should still make that status visible in output layers if used. |
| Runway centreline markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.530 | Operational verified | Minimum stripe widths are implemented with traceability metadata and regression tests, including CAT II/III, CAT I, NPA code 3/4, and lower-code/default cases. |
| Threshold markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.535 | Operational verified with caveat | Runway width to stripe count values are implemented with traceability metadata and regression tests. Stripe width of 1.8 m is retained as an interpretive representative value. |
| Aiming point markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.540 Table L-1 | Operational verified with caveat | LDA bands and representative minimum values from Table L-1 are implemented and regression-tested for instrument runways, including NPA. Non-instrument additional-conspicuity output remains marked interpretive. |
| Touchdown-zone markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.545 | Operational verified with derived offsets | LDA pair-count bands are source verified. Returned offset lists are derived at 150 m intervals with aiming-point conflict omissions and are marked `derived_verified`. |
| Runway-holding position markings | `rulesets/easa/markings.py` | CS ADR-DSN.L.575, D.335 | Accepted unsupported | Returning `None` is tested and documented because Chapter L defines marking patterns while fixed holding-position distance belongs to Chapter D location/design criteria. |
| Runway edge lighting | `rulesets/easa/lighting.py` | CS ADR-DSN.M.675 | Operational verified | Instrument spacing 60 m and non-instrument spacing 100 m are implemented with traceability metadata and regression tests. |
| Simple approach lighting | `rulesets/easa/lighting.py` | CS ADR-DSN.M.626 | Operational verified | Preferred 420 m length, 60/30 m spacing, 300 m crossbar, and 18/30 m crossbar lengths are implemented with traceability metadata and regression tests. |
| Precision approach lighting | `rulesets/easa/lighting.py` | CS ADR-DSN.M.630, M.635 | Operational verified | CAT I and CAT II/III approach profile geometry, crossbar stations, side-row values, and crossbar spacing limits are implemented with traceability metadata and regression tests. Applicability selection remains a simplified planning policy. |
| Threshold/end/temporary displaced threshold lights | `rulesets/easa/lighting.py` | CS ADR-DSN.M.680, M.685 plus compatibility fallback | Operational verified with caveats | Threshold and runway-end source values are implemented and tested. The 30 m minimum lit-width floor and temporary displaced threshold counts remain explicitly labelled as compatibility/MOS-derived fallback assumptions. |
| Runway centreline lights | `rulesets/easa/lighting.py` | CS ADR-DSN.M.690 | Operational verified with applicability policy | Spacing, lateral offset, colour zones, and simplified requirement/recommendation helpers are regression-tested. Applicability helpers remain policy-level simplifications. |
| Touchdown-zone lights | `rulesets/easa/lighting.py` | CS ADR-DSN.M.695 | Operational verified with nominal gauge | TDZ length, 30/60 m row spacing, at least three lights per barrette, barrette spacing/length, and nominal inner offset are implemented and regression-tested. The 9 m inner offset remains a selected 18 m gauge assumption. |

## High-confidence findings

1. The EASA package is not an empty scaffold. It contains EASA-specific numeric tables and EASA references in physical, taxiway, marking, lighting, and OLS modules.
2. Runway strips, RESA, taxiway separations, parallel runway separations, OLS Tables J-1/J-2, runway markings, and airfield ground lighting are now operational-grade verified EASA Issue 7 tranches.
3. The riskiest remaining area is declared distances, clearway, and stopway because those outputs are not yet implemented as a complete EASA-specific tranche.
4. The edition decision is now settled: the code targets Issue 7/current EASA, while remaining marked draft until full table-level verification is complete.

## Confirmed implementation decisions

| Decision | Outcome |
| --- | --- |
| Authority target | EASA CS-ADR-DSN Issue 7. |
| Verification standard | Operational-grade. |
| Interpretation policy | Parked for follow-up. The open question is whether conditional/guidance values should be applied "as is", exposed as designer-selected options, or used to identify variance from a compliant standard. |
| Completion order | Physical runway dimensions; taxiway/separation; OLS; markings; lighting; declared distances/clearway/stopway. |
| Use case | Both safeguarding/planning envelopes and aerodrome design compliance, with the interpretation policy still to determine how variance/compliance outputs are framed. |

## Recommended consolidation todo list

1. Add a machine-readable traceability table for EASA constants:
   - policy family
   - code key
   - implemented value
   - source clause/table
   - verification status
   - notes
2. Promote only verified capability keys in `rulesets/easa/metadata.py`; downgrade anything that remains interpretive or only spot-checked.
3. Add regression tests that assert exact source references as well as numeric values for each verified family.
4. Revisit the interpretation policy before promoting outputs that depend on conditional rules, ranges, guidance material, or designer judgement.

## Working conclusion

Treat the current EASA Issue 7 ruleset as a useful partial implementation, not
yet a dependable planning-standard authority. It contains real EASA-specific
values, but it needs table-level traceability before it should be used as a
high-confidence ruleset.
