# Testing

Run the QGIS-independent suite from the repository root:

```bash
python3 -m unittest \
  tests.test_ols_construction_policy \
  tests.test_ols_source_validation \
  tests.test_run_history \
  tests.test_runtime_dashboard
```

Run full discovery with the Python interpreter supplied by a configured QGIS
installation:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

QGIS-dependent modules do not import under a normal system Python. The committed
suite covers:

- controlling OLS and modernisation comparison geometry;
- the OLS dialog workflow and cancellation checkpoints; and
- explicit end-to-end QGIS workflow runners.

Ruleset source notes remain beside their implementations. Review the relevant
source matrix whenever a source edition or policy value changes.

The expensive QGIS workflow regression runner is opt-in and is excluded from
normal unit-test discovery. Run a single relevant fixture while troubleshooting:

```bash
tests/run_ols_workflow_regression.py --fixture ybbn_single.json
```

Run the complete fixture matrix and production gates only for release evidence
or when shared OLS geometry code changes. See
[`fixtures/ols/README.md`](fixtures/ols/README.md) for
the QGIS environment and baseline commands. Multi-fixture runs automatically
use a fresh QGIS process per fixture so native geometry and project state cannot
accumulate across the matrix.
