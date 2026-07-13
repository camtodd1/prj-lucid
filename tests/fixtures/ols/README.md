# OLS workflow fixtures

These inputs exercise the complete MOS139-to-future-Annex-14 modernisation
comparison workflow under QGIS 4.

- `ybbn_single.json`: single runway.
- `yssy_dual_intersecting.json`: intersecting runways.
- `ysws_dual_parallel.json`: parallel runways.
- `ymml_intersecting.json`: intersecting YMML runways with prominent
  Approach/TOCS-to-Conical equality arcs in EPSG:32755.
- `yssy_multiple_stress.json`: three-runway stress case.

The files are normalized copies of the test inputs supplied for regression use.
They use memory output and enable controlling OLS generation. Run them explicitly
with `tests/run_ols_workflow_regression.py`; they are intentionally excluded from
normal unit-test discovery because a full run is computationally expensive.

The runner treats spatial indexes and other future optimizations only as filters.
Exact geometry containment, elevation evaluation, tie-breaking, common-domain
coverage, and mutually exclusive gain/loss/no-change outputs remain mandatory.

## YMML axis/conical benchmark

`ymml_axis_conical_benchmark_qgis4_2026-07-13.json` records three-run timing,
geometry, equality-residual, and line-smoothness metrics for both the supplied
sampled output and the adopted projected zero-contour refinement. The exact
supplied transition layer is preserved in
`baselines/ymml_controlling_transition_boundaries_sampled_2026-07-13.geojson`.

The benchmark deliberately treats two concepts separately:

- `elev_min`/`elev_max` describe the range of shared AMSL elevation along a
  sloping transition line and can legitimately differ; and
- `eq_res_max` describes how closely the two surfaces agree at corresponding
  points and should be near zero for projected axis/conical transitions.

Run the focused three-run benchmark with:

```bash
QT_QPA_PLATFORM=offscreen \
PROJ_DATA=/Applications/QGIS-4.0.app/Contents/Resources/qgis/proj \
GDAL_DATA=/Applications/QGIS-4.0.app/Contents/Resources/gdal \
/Applications/QGIS-4.0.app/Contents/MacOS/python \
tests/run_ols_workflow_regression.py \
  --fixture ymml_intersecting.json \
  --repeat 3 \
  --output /private/tmp/ymml_axis_conical_report.json
```

## Performance baseline

`performance_baseline_qgis4_2026-07-11.json` records the current QGIS 4.0.2
wall-clock and key nested-stage timings, output counts, and comparison accuracy
metrics for all five fixtures. It is a reference checkpoint, not a hard timing
gate: compare medians from at least three runs on the same machine/runtime and
investigate changes above 20%. Geometry validity, coverage, exclusivity, and ID
checks remain hard failures.

Generate a fresh raw report with:

```bash
QT_QPA_PLATFORM=offscreen \
PROJ_DATA=/Applications/QGIS-4.0.app/Contents/Resources/qgis/proj \
GDAL_DATA=/Applications/QGIS-4.0.app/Contents/Resources/gdal \
/Applications/QGIS-4.0.app/Contents/MacOS/python \
tests/run_ols_workflow_regression.py --output /private/tmp/ols_regression.json
```

Run the production non-regression gate (three-run medians, deterministic output,
exact baseline counts, and a maximum 20% runtime regression) with:

```bash
QT_QPA_PLATFORM=offscreen \
PROJ_DATA=/Applications/QGIS-4.0.app/Contents/Resources/qgis/proj \
GDAL_DATA=/Applications/QGIS-4.0.app/Contents/Resources/gdal \
/Applications/QGIS-4.0.app/Contents/MacOS/python \
tests/run_ols_workflow_regression.py \
  --repeat 3 \
  --baseline tests/fixtures/ols/performance_baseline_qgis4_2026-07-11.json \
  --output /private/tmp/ols_production_readiness.json
```

Add `--production-gates` for promotion evidence. This intentionally fails while
any solver or comparison activates an exceptional recovery repair or leaves an
unresolved comparison; ordinary benchmark runs continue to record those
diagnostics without changing generated geometry.
