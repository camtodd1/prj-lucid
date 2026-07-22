# UK CAA CAP 168 Ruleset

**Status:** Current

**Profile:** `uk_caa_cap168_edition_13` (`stable`)

This package implements the UK CAA CAP 168 Edition 13 design-standard profile.
Its conventional obstacle limitation surface (OLS) construction and controlling
lower envelope are production-supported.

## Supported Scope

- Aerodrome reference code classification and runway-width policy.
- Runway strip, clearway, stopway, taxiway-separation, and parallel-runway
  policy.
- Declared-distance calculations.
- Runway marking and airfield ground lighting parameters.
- Airport-wide, approach, take-off climb, transitional, obstacle free zone,
  inner horizontal, conical, and outer horizontal OLS construction.
- CAP 168 main/subsidiary runway context, lowest-threshold datum, short-runway
  circles, long-runway racetracks, subsidiary tangent joins, length-dependent
  outer horizontal surfaces, and nominated offset or curved approach/take-off
  tracks.

Pavement and shoulder policy are partial. RESA is unsupported. Transitional
construction adjacent to curved approach tracks remains outside the supported
contract.

## Source and Compatibility

[`source_matrix.md`](source_matrix.md) records clause-level scope, confirmed
numeric corrections, and retained source interpretations. Regression fixtures
and accepted geometry evidence live under
[`tests/fixtures/ols`](../../tests/fixtures/ols/README.md); dated test results
and runtime evidence are preserved by Git history and the runtime ledger.

`profile.py` exposes the public facade. Policy values belong in the relevant
domain module (`classification.py`, `physical_data.py`, `taxiway.py`,
`ols_surfaces.py`, `markings.py`, or `lighting.py`), while `metadata.py` is the
authoritative capability declaration.
