# CAP 168 OLS Release Evidence — 14 July 2026

CAP 168 Edition 13 conventional OLS is promoted to `stable` and
production-supported for airport-wide, approach, take-off climb, OFZ and
controlling lower-envelope construction.

## Production gate

QGIS 4.0.2 headless production gates passed three deterministic runs of every
CAP 168 fixture. All runs had valid output geometry, complete controlling
coverage, unique deterministic IDs and no exceptional recovery activation.

| Fixture | Configuration | Median runtime | Determinism digest |
| --- | --- | ---: | --- |
| `cap168_curved_single.json` | Curved/offset tracks, displaced threshold, clearway and stopway | 8.011 s | `33d80c36ca7d5730bd72e16563856ec6c33775d97e3b7cec76cfb8d77447225b` |
| `cap168_short_single.json` | Short NI runway and circular IHS | 1.082 s | `75ecc5ca8ace6d67db2e15225cedba9250b609b578fa044b2d915eb013f620ac` |
| `cap168_parallel_main_subsidiary.json` | Longest-runway main selection and parallel subsidiary join | 4.807 s | `1fb4e4d4ce0a407c1cfc5d739b6529867361f38a20073b6493563c52c0f5eab7` |
| `cap168_intersecting.json` | Intersecting main/subsidiary runways and mixed operations | 4.251 s | `37e6c434d17e0ed33ac8c94b274e9a2ba5ee51f7c0565cee2971e708edea9782` |

The pure construction/source suite passed 20 tests. The combined QGIS
construction, source-oracle, dialog and comparison suite passed 90 tests.

## Compatibility lock

The three MOS139 stress fixtures affected during development were rerun after
ruleset-scoping CAP-specific refinement. Their region counts, areas, controller
IDs and geometry digests match the existing locked MOS139 contract exactly:

- `ymml_intersecting.json`
- `yssy_dual_intersecting.json`
- `yssy_multiple_stress.json`

Modernised Annex 14 OFS/OES construction is unchanged. Current Annex 14
conventional OLS was subsequently source-loaded and promoted through its own
release evidence; EASA remains a preview.

Runtime details for each headless run are appended to `runtime_test_runs.txt`
with the agent, airport, rulesets, QGIS/plugin version, Git reference, dirty
state and module timings.
