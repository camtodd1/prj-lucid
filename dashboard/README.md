# AeroSense runtime explorer

This is a small local dashboard for answering practical development questions:

- Which airports and test cases are slowest?
- Do single, parallel, intersecting, or mixed-runway tests behave differently?
- Which primary/comparison OLS selections cost the most time?
- Which standard test-case/OLS/runner trends are getting faster or slower?

From the repository folder, run:

```bash
python3 dashboard/runtime_dashboard.py --serve
```

Then open <http://127.0.0.1:8765>. Refresh the page after more tests finish.
Stop the server with `Ctrl+C`.

The page is self-contained and uses no external service or JavaScript library.
Running the command without `--serve` simply rebuilds `dashboard/index.html`.

Chart lines use the same colour and line-style markers as the pivot table.
The pivot defaults to **Chart series**, where each row maps directly to one
test-case, OLS-selection, and runner line. Regrouped pivot rows show every chart
series marker included in that aggregate.

For a User-versus-Codex comparison, load an unchanged JSON from
`tests/fixtures/ols/` in QGIS and have Codex run that same fixture headlessly.
The dashboard shows **Exact · User + Codex** only when the recorded input
fingerprint matches across both runners.

## Run ownership

Runtime rows are normalized to two owner labels:

- **User** for interactive QGIS runs; and
- **Codex** for headless, Codex, or CI runs.

The top-level slicers cover **Scenario**, **Airport**, and **Run by**. The
second level covers **Design Standard**, **Baseline OLS**, and **Comparison
OLS**. Each slicer responds to the others: options with no matching runs are
removed as selections are made.

The scenario slicer groups layouts as **Single**, **Dual Parallel**, **Dual
Intersecting**, **Multiple Parallel**, or **Multiple Intersecting**. Multiple
Parallel means three or more runways with no intersections; Multiple
Intersecting means three or more runways where any number may intersect.

The **Run by** slicer filters the KPIs, last-five cards, chart, and pivot table.
Each last-five card repeats its owner as plain bold muted text beside the run
time. When the slicer is active, the card's change indicator compares with the
previous matching run from the same filtered owner; it does not silently compare
a User run with a Codex run.

Comparison quality remains fingerprint-based. **Exact · User + Codex** means
that both owners have recorded the identical input fingerprint, even when the
current view is temporarily filtered to one owner.

## Data quality

Runtime schema 4 records the test case, input filename, runway count, runway
scenario, and a short exact-input fingerprint. Scenarios are limited to
`single` (one runway), `parallel` or `intersecting` (two or more), and `mixed`
(three or more). The standard regression runner and
saved-input workflow supply that information automatically.

Older rows did not contain those fields. They remain useful for filtering by
airport, OLS selection, commit, and run time, but the dashboard marks their
speed comparisons as **rough** instead of guessing which scenario was used.
