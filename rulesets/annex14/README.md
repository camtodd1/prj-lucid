# ICAO Annex 14 Volume I Rulesets

**Status:** Current

This package contains two separate protected-airspace profiles:

| Profile | Status | Applicability |
| --- | --- | --- |
| `icao_annex14_vol1_current_ols` | Stable | Conventional OLS through 20 November 2030 |
| `icao_annex14_vol1_modernised_ofs_oes` | Stable | Future OFS/OES model from 21 November 2030 |

## Current OLS Profile

The current profile production-supports conventional airport-wide, approach,
take-off climb, transitional, precision obstacle free zone, inner horizontal,
conical, outer horizontal, and controlling-envelope construction from Annex 14
Volume I, Ninth Edition, Amendment 18. Chapter 3 runway strip, clearway, and
stopway dependencies used by that construction are also supported.

The profile is selectable as a design standard for its supported OLS scope. It
does not claim Annex 14 runway, RESA, shoulder, taxiway, marking, or lighting
coverage outside those dependencies.

## Modernised OFS/OES Profile

The modernised protected-airspace profile supports Aeroplane Design Group
classification, runway OFS, controlling lower envelopes, the five standard OES
families, contours, and cross-ruleset comparisons. The automatic workflow uses
the design-ruleset strip, derives operations from runway type and take-off
availability, assumes straight-in approaches, applies the conservative heavy
take-off and Code F cases, and retains unadjusted standard slope/OCH table
dimensions. These assumptions and the corresponding exclusions are declared
authoritatively in `metadata.py`. It is a future model applicable from
21 November 2030 and is not currently enforceable.

Physical design, declared-distance design, markings, lighting, and
specific/curved OES geometry remain unsupported.

The baseline/comparison behavior is described in
[`docs/ols_modernisation_comparison.md`](../../docs/ols_modernisation_comparison.md).
Open promotion work is listed in [`docs/roadmap.md`](../../docs/roadmap.md).

## Source and Ownership

[`source_matrix.md`](source_matrix.md) records source coverage and
interpretations. `metadata.py` is authoritative for capability status.
`current_ols.py` owns current conventional OLS policy; the remaining OLS, OFS,
OES, and requirement modules own the modernised model. Accepted regression
contracts live under [`tests/fixtures/ols`](../../tests/fixtures/ols/README.md).
