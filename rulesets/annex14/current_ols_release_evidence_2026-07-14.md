# Current Annex 14 OLS Release Evidence — 14 July 2026

ICAO Annex 14 Volume I, Ninth Edition, Amendment 18 conventional OLS is
promoted to `stable` and production-supported for its applicability period
ending 20 November 2030. The post-2030 OFS/OES model remains separate.

## Source gate

Current Table 4-1 and Table 4-2 were visually verified in the supplied
Chapter 4 extract. Chapter 3 strip, clearway and stopway dependencies were
verified in the supplied full standard and Amendment 18 State Letter. Source
filenames, SHA-256 hashes, clauses, pages and implementation interpretations
are recorded in `source_matrix.md` and
`tests/fixtures/ols/source_validation_v1.json`.

## Production gate

QGIS 4.0.2 headless production gates passed three deterministic runs per
fixture. The comparison cases were run in separate QGIS processes because the
test harness does not safely retain multiple large GEOS comparison graphs in a
single process; every isolated run exited successfully and produced identical
accuracy signatures.

| Fixture | Configuration | Median runtime | Determinism digest |
| --- | --- | ---: | --- |
| `annex14_current_short_single.json` | Current Annex 14 code 1 NI runway | 1.226 s | `5d322bad71efc3b98c63f9ef3a151eab15f48d8f2c87b669e2769912ad4bf47d` |
| `annex14_current_intersecting.json` | MOS139 baseline → current Annex 14 comparison | 8.629 s | `36129784b13dd4166a17ebc1ceb841817048c7c59afff0a13e77fd2de39b4404` |
| `annex14_current_intersecting_reverse.json` | Current Annex 14 baseline → MOS139 comparison | 8.778 s | `a84cdbb9f817ac3d02d69e550c24e68f43447a4f9a784a78771ca5a08f3f1ae7` |

All runs had valid output geometry, complete controlling coverage, unique
deterministic IDs, no unresolved controller comparisons, no unbounded
approximation and no exceptional recovery. The intersecting comparison leaves
less than 0.018 m² of audited sub-threshold numerical residue across a
187.7 km² common domain, below the 0.1 m² absolute release tolerance.

The pure construction/source suite passed 23 tests. The combined QGIS
construction, source-oracle, dialog, modernised-comparison and layer-grouping
suite passed 94 tests.

## Compatibility locks

The following MOS139 fixtures retain their exact accepted controller IDs,
areas and geometry digests:

- `ymml_intersecting.json`
- `yssy_dual_intersecting.json`
- `yssy_multiple_stress.json`

The current-Annex comparison partition is ruleset-scoped and does not alter
the standalone MOS139 engine. The unchanged modernised Annex 14 unit suite is
green. EASA remains a selectable preview.

Runtime records were appended to `runtime_test_runs.txt` with agent, airport,
rulesets, QGIS/plugin version, Git reference `da0f5bbaa05d`, dirty state and
module timings.
