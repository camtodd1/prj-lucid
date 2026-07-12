# Testing scope

The committed test suite is intentionally focused on components that are still
under active development or troubleshooting:

- controlling OLS and modernisation comparison geometry;
- the OLS dialog workflow and cancellation checkpoints; and
- explicit end-to-end QGIS workflow runners.

Stable ruleset tables, source citations, framework registry adapters, and
declared-distance calculations are not duplicated in the routine test suite.
Their authoritative source notes remain beside the implementation and in
`docs/`. Review and validate those components when their implementation or
source edition changes.

The expensive QGIS workflow regression runner is opt-in and is excluded from
normal unit-test discovery. Run a single relevant fixture while troubleshooting:

```bash
tests/run_ols_workflow_regression.py --fixture ybbn_single.json
```

Run the complete fixture matrix and production gates only for release evidence
or when shared OLS geometry code changes. See `tests/fixtures/ols/README.md` for
the QGIS environment and baseline commands.
