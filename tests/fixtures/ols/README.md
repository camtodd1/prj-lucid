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
