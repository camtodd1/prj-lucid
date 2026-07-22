# OLS workflow fixtures

These inputs exercise conventional OLS and the MOS139-to-future-Annex-14
modernisation comparison workflow under QGIS 4.

Input filenames follow `<icao>_<count>rwy_<scenario>[_<variant>].json`, where
scenario is limited to `single`, `parallel`, `intersecting`, or `mixed`.
The optional variant describes a genuine input variation; it is not a workload
or test-intensity label. A three-runway mixed layout is therefore simply
`yssy_3rwy_mixed.json`.

- `ybbn_1rwy_single.json`: single runway.
- `yssy_2rwy_intersecting.json`: intersecting runways.
- `ysws_2rwy_parallel.json`: parallel runways.
- `ymml_2rwy_intersecting.json`: intersecting YMML runways with prominent
  Approach/TOCS-to-Conical equality arcs in EPSG:32755.
- `yssy_3rwy_mixed.json`: three mixed runways.
- `ybas_1rwy_single.json`: current Annex 14 non-instrument code 1
  runway and airport-wide OLS.
- `ybai_2rwy_intersecting.json`: current Annex 14 intersecting mixed-code
  runways with precision OFZ, displaced thresholds, clearways and stopways.
- `ybai_2rwy_intersecting_reverse.json`: the same current Annex 14/MOS139
  comparison with the pair order reversed.
- `ybsc_1rwy_single_file_output.json`: a manifest-defined case based on the
  CAP168 short runway input. The runner substitutes a temporary GeoPackage
  directory and verifies generated-layer/file parity, concise log volume, and
  the absence of per-layer file-success debug messages.

The files are normalized copies of the test inputs supplied for regression use.
They use memory output and enable controlling OLS generation. Run them explicitly
with `tests/run_ols_workflow_regression.py`; they are intentionally excluded from
normal unit-test discovery because a full run is computationally expensive.
When more than one fixture is selected, the runner isolates each fixture in a
new QGIS process and combines the child reports into one matrix report.

## Shared User/Codex benchmark

For a fair performance comparison, User and Codex must run the **same JSON file
from this folder** without changing its runways, scenario, or OLS selections.

- User: in QGIS, choose **Load Inputs** and select the fixture JSON.
- Codex/headless: run `tests/run_ols_workflow_regression.py --fixture <same-file>`.
- In the dashboard, narrow to that test case. **Exact · User + Codex** confirms
  that both runners have recorded the identical input fingerprint.
- Use the **Run by** slicer to inspect User or Codex runs independently. The
  last-five change badges then compare only within the selected owner.

Changing any test parameter is valid, but creates a different setup and should
not be treated as a like-for-like speed comparison. Each fixture stores the same
`test_case_id` and plain-English name used by both routes.

The runner treats spatial indexes and other future optimizations only as filters.
Exact geometry containment, elevation evaluation, tie-breaking, common-domain
coverage, and mutually exclusive gain/loss/no-change outputs remain mandatory.

### YSSY mixed conical comparison coverage

`yssy_3rwy_mixed.json` also exercises conical/conical intersections in a
MOS139/CAP168 comparison. It guards against two coupled failure modes:

- a late coverage repair assigning a mixed-sign polygon to gain or loss from a
  single interior sample; and
- a triangulated conical isoline satisfying the requested height while retaining
  a visible saw-tooth path.

Promotion checks must confirm that material gain/loss ranges do not cross zero,
no opposite-sign contours are generated, the transition follows the shared
zero-height locus, and conical contours pass both residual and smoothness gates.
The fixture uses 0.5 m intermediate and 10 m primary modernisation change
contours so the workflow gate also detects missing material interior levels.

## Source-backed analytical fixture

`source_validation_v1.json` records authoritative MOS139, CAP168 and Annex 14
source provenance, cited
numeric facts, explicit assumptions, independent expected elevations, contour
locations, controller identities and a curved axis/conical intersection. It is
used by `tests/test_ols_source_validation.py` with the production-independent
math in `tests/ols_source_oracle.py`. A second QGIS-facing layer in
`tests/test_ols_source_validation_qgis.py` checks those independent values
against the actual production evaluators, affine transition builder and
controller selection.

This fixture is intentionally portable and runs without QGIS:

```bash
python3 -m unittest tests.test_ols_source_validation -v
```

The fixture itself is the machine-readable evidence record. Current scope gaps
are tracked in [`docs/roadmap.md`](../../../docs/roadmap.md).

## YMML axis/conical benchmark

`ymml_axis_conical_benchmark_qgis4_2026-07-13.json` records three-run timing,
geometry, equality-residual, and line-smoothness metrics for the supplied
sampled output, the projected zero-contour refinement, and the adopted bounded
C2 smoothing experiment. The exact supplied transition layer is preserved in
`baselines/ymml_controlling_transition_boundaries_sampled_2026-07-13.geojson`.

The smoother constructs an endpoint-clamped uniform cubic B-spline guide and
projects its interior vertices back onto the exact axis/conical equality locus
before the curve is used for polygonisation. A smoothed component is retained
only when peak and RMS curvature change improve, the curve remains within the
surface-overlap domain, symmetric densified Hausdorff displacement is no more
than 0.5 m, and equality error is no more than 0.01 m. Endpoints remain fixed;
components that fail any gate fall back to the projected unsmoothed curve.

The benchmark deliberately treats two concepts separately:

- `elev_min`/`elev_max` describe the range of shared AMSL elevation along a
  sloping transition line and can legitimately differ; and
- `eq_res_max` describes how closely the two surfaces agree at corresponding
  points and should be near zero for projected axis/conical transitions; and
- `reversal_count`, `duplicate_segment_count`, `short_component_count`, and
  `topology_excess_length_m` detect doubled-back paths, reverse duplicates,
  sub-resolution fragments, and sliver loops. Production gates require zero.
- `maximum_abs_curvature_change_per_m2` and its RMS counterpart measure
  curvature continuity. The smoother must improve both values locally before
  its guide is accepted.

Run the focused three-run benchmark with:

```bash
QT_QPA_PLATFORM=offscreen \
PROJ_DATA=/Applications/QGIS-4.0.app/Contents/Resources/qgis/proj \
GDAL_DATA=/Applications/QGIS-4.0.app/Contents/Resources/gdal \
/Applications/QGIS-4.0.app/Contents/MacOS/python \
tests/run_ols_workflow_regression.py \
  --fixture ymml_2rwy_intersecting.json \
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
