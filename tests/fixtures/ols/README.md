# OLS workflow fixtures

These inputs exercise the complete MOS139-to-future-Annex-14 modernisation
comparison workflow under QGIS 4.

- `ybbn_single.json`: single runway.
- `yssy_dual_intersecting.json`: intersecting runways.
- `ysws_dual_parallel.json`: parallel runways.
- `yssy_multiple_stress.json`: three-runway stress case.

The files are normalized copies of the test inputs supplied for regression use.
They use memory output and enable controlling OLS generation. Run them explicitly
with `tests/run_ols_workflow_regression.py`; they are intentionally excluded from
normal unit-test discovery because a full run is computationally expensive.

The runner treats spatial indexes and other future optimizations only as filters.
Exact geometry containment, elevation evaluation, tie-breaking, common-domain
coverage, and mutually exclusive gain/loss/no-change outputs remain mandatory.

## Performance baseline

`performance_baseline_qgis4_2026-07-11.json` records the current QGIS 4.0.2
wall-clock and key nested-stage timings, output counts, and comparison accuracy
metrics for all four fixtures. It is a reference checkpoint, not a hard timing
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
