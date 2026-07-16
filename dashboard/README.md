# AeroSense runtime explorer

This is a small local dashboard for answering practical development questions:

- Which airports and test cases are slowest?
- Do single, parallel, intersecting, or mixed-runway tests behave differently?
- Which primary/comparison OLS selections cost the most time?
- For the same filtered setup, are the last five runs faster or slower than the previous five?

From the repository folder, run:

```bash
python3 dashboard/runtime_dashboard.py --serve
```

Then open <http://127.0.0.1:8765>. Refresh the page after more tests finish.
Stop the server with `Ctrl+C`.

The page is self-contained and uses no external service or JavaScript library.
Running the command without `--serve` simply rebuilds `dashboard/index.html`.

For a User-versus-Codex comparison, load an unchanged JSON from
`tests/fixtures/ols/` in QGIS and have Codex run that same fixture headlessly.
The dashboard shows **Exact · User + Codex** only when the recorded input
fingerprint matches across both runners.

## Data quality

Runtime schema 4 records the test case, input filename, runway count, runway
scenario, and a short exact-input fingerprint. Scenarios are limited to
`single` (one runway), `parallel` or `intersecting` (two or more), and `mixed`
(three or more). The standard regression runner and
saved-input workflow supply that information automatically.

Older rows did not contain those fields. They remain useful for filtering by
airport, OLS selection, commit, and run time, but the dashboard marks their
speed comparisons as **rough** instead of guessing which scenario was used.
