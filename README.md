# Safeguarding Builder

Safeguarding Builder is a QGIS plugin for generating aerodrome safeguarding
layers from runway, aerodrome reference point, meteorological, and CNS facility
inputs.

The plugin is intended to support airport planning and safeguarding review work
by producing a consistent set of spatial layers for NASF-style assessment areas,
OLS surfaces, physical runway protection geometry, and supporting reference
features. It uses the active QGIS project CRS for input coordinates and output
geometry, so the project should use a projected CRS with metre units.

## Plugin Objective

Safeguarding Builder turns structured aerodrome inputs into grouped QGIS layers
that can be inspected, styled, exported, and overlaid with planning or obstacle
data. The main workflow is:

1. Enter airport, ARP, runway, MET, and CNS facility details in the plugin dialog.
2. Select which safeguarding surfaces and guideline layers to build.
3. Generate memory layers or write outputs to a selected file format.
4. Review the generated layer tree and styled map outputs in QGIS.

The generated outputs are grouped under an airport-specific Safeguarding Builder
group in the QGIS layer tree.

## Main Functions

The plugin can generate:

- Airport reference point, runway centreline, and CNS source facility reference
  layers.
- Physical runway geometry, including runway pavement, shoulders, strips,
  runway-end safety areas, stopways, pre-threshold runway areas, and displaced
  threshold marking references.
- Optional Airfield Ground Lighting (AGL) layers, including runway edge,
  threshold, runway end, stopway, centreline, touchdown zone, and approach
  lighting features.
- MOS-informed AGL approach lighting for precision approach CAT II/III runway
  ends, including centreline barrettes, side-row barrettes, crossbars, and
  distance-coded centreline light positions.
- Building-induced windshear assessment zones.
- Wildlife management zones.
- Wind turbine assessment zones.
- Lighting control zones and airport-wide lighting areas.
- Obstacle limitation surfaces, including approach, take-off climb,
  transitional, inner horizontal, conical, outer horizontal, and related inner
  surfaces where applicable.
- CNS building restricted areas based on selected CNS facilities.
- Public safety areas.
- Specialised surfaces, including runway airspace object assessment areas and
  taxiway separation offsets.
- MET station safeguarding surfaces where MET inputs are supplied.

Guideline A and Guideline H detailed generation logic is not yet implemented,
so placeholder layer groups are not generated for them.

## Inputs

Typical inputs include:

- ICAO airport code and airport name.
- Aerodrome reference point coordinates and elevation.
- Runway designators, threshold coordinates, threshold elevations, runway width,
  aircraft reference code, runway type, instrument classification, and runway
  status details.
- Optional displaced threshold and pre-threshold runway values.
- Optional Lighting tab inputs for AGL generation, including per-runway-end
  approach lighting parameters, low-visibility/RVR options, and optional CAT I
  lighting enhancements where supported.
- Optional MET station coordinates and elevation.
- Optional CNS facility rows, including type, coordinates, elevation, antenna
  height, and related configuration values.
- Output options, including memory layers or file output.

All coordinate inputs are interpreted in the current QGIS project CRS.

## Output and Styling

Generated layers can be added directly to the QGIS project as memory layers or
written to file-based outputs such as GeoPackage, Shapefile, or GeoJSON,
depending on the selected dialog options.

QGIS style files in `styles/` are applied automatically where a matching style
key is available. The mapping between logical layer categories and QML files is
defined in `core/styles.py`.

AGL layers use point symbols to represent light fittings. The generated
attributes distinguish omnidirectional, unidirectional, bidirectional, and
split-colour light displays, and `styles/agl_lights.qml` draws the corresponding
circle, split-circle, flashing, and direction-prong markers. Coincident AGL
lights are resolved before output where a combined marker or priority rule is
needed.

## Project Structure

The central plugin file now focuses on QGIS lifecycle handling, dialog
coordination, common geometry helpers, and orchestration. Guideline and surface
generation logic is split into smaller modules:

```text
safeguarding_builder.py          Plugin lifecycle, orchestration, common
                                 geometry helpers, ARP/runway layers, and MET
                                 surfaces.
safeguarding_builder_dialog.py   QGIS dialog orchestration, global inputs,
                                 runway calculations, and validation.
dialog/runway_group.py           Dynamic runway input group widget.
dialog/cns_table.py              CNS facility table setup, row handling, and
                                 CNS input validation.
dialog/output_options.py         Memory/file output option setup and state.
dialog/agl_options.py            Lighting tab setup, validation, and AGL input
                                 persistence.
dialog/persistence.py            Clear, save, and load behaviour for dialog
                                 input JSON.
dialog/dialog_constants.py       Shared dialog labels, placeholders, logging
                                 tag, and output format definitions.
core/layers.py                   Layer creation, feature writing, output file
                                 handling, grouping, and style application.
core/run_log.py                  Structured operational events, diagnostic
                                 routing, aggregation, and QGIS severity mapping.
core/run_history.py              Append-only GUI/headless runtime test ledger.
core/styles.py                   Mapping between layer style keys and QML files.
guidelines/guideline_constants.py
                                 Shared constants for guideline dimensions,
                                 references, contour intervals, and offsets.
guidelines/simple.py             Compatibility shim for NASF-backed
                                 safeguarding generators.
guidelines/ols_guideline.py      Runway and airport-wide OLS generation.
surfaces/physical.py             Physical runway and runway protection geometry.
surfaces/airfield_ground_lighting.py
                                 Airfield Ground Lighting generation and
                                 coincident-light resolution.
surfaces/specialised.py          Specialised surfaces such as RAOA and taxiway
                                 separation offsets.
dimensions/cns_dimensions.py     CNS building restricted area dimensions.
dimensions/ols_dimensions.py     Legacy compatibility shim for MOS139 OLS
                                 dimensions.
dimensions/agl_dimensions.py     Legacy compatibility shim for MOS139 AGL
                                 dimensions.
rulesets/                       Aerodrome-standard profiles and policy modules
                                 for MOS139, EASA, CAP 168, and ICAO Annex 14.
frameworks/nasf/                Australian NASF safeguarding framework profile,
                                 policy parameters, and compatibility aliases.
reports/                        Declared-distance and runway-summary reports.
tests/                          Unit, QGIS integration, and OLS fixture tests.
docs/                            Maintained implementation references, project
                                 roadmap, conventions, and field-name mapping.
styles/*.qml                     QGIS layer styling files.
metadata.txt                     QGIS plugin metadata.
resources.qrc                    Qt resource manifest.
```

## Logging Contract

The QGIS **SafeguardingBuilder** log is a concise operational trace intended for
a quick scan. A run emits one `START`, numbered `PHASE` events, material `SKIP`,
`OUTPUT`, `WARN`, or `ERROR` outcomes, and exactly one terminal `DONE`,
`CANCELLED`, or `FAILED` event. Fields use a stable `key=value` format on one
line. Skips state why an output was omitted; warnings state the consequence and,
where useful, the corrective action. Repeated equivalent skips and warnings are
aggregated rather than emitted once per feature or layer.

Severity is semantic rather than numeric: routine progress, skips, and
cancellation are QGIS Info; recoverable degradation is Warning; failed output is
Critical; and only a successfully completed run is Success. User notifications
remain in the message bar, so message-log events do not request duplicate QGIS
pop-ups.

Detailed solver, geometry, and legacy implementation messages use the separate
**SafeguardingBuilder.Diagnostics** tag and are disabled by default. Set
`SAFEGUARDING_BUILDER_DIAGNOSTICS=1` before starting QGIS to enable them. New
code should use `RunLog` outcomes instead of calling QGIS logging directly. The
workflow regression runner checks the event schema, exact severity mapping,
single-line rendering, one start/terminal pair, and a volume ceiling of
`32 + 3 × runway count`, with additional allowance for warnings and errors.

## Runtime Test History

Every safeguarding generation run appends one tab-separated row beneath stable
column headers in `runtime_test_runs.txt` in the plugin directory. This includes
QGIS runs and headless workflow runs. The columns record the actor (`qgis user`,
`codex headless`, or an explicit override), airport, selected rulesets,
completion status, total and key phase/module elapsed times, plugin/QGIS
versions, Git commit, and whether the working tree was dirty. The final
scenario columns also record the test case, input filename, runway count and
layout, plus a short exact-input fingerprint. `module_timings_json` retains all
module timings and call counts, including diagnostic modules that do not have
dedicated columns.

Set `SAFEGUARDING_BUILDER_RUN_AGENT` to override the actor,
`SAFEGUARDING_BUILDER_COMMIT` for packaged builds without `.git`, or
`SAFEGUARDING_BUILDER_RUN_HISTORY` to select another text-file path. The file
uses a versioned TSV schema. Existing version 1 JSON Lines ledgers are converted
automatically on the next write, preserving their original schema version and
timing data.

For a filterable, plain-English view of runtime by test case, airport, runway
setup, and OLS selection, run `python3 dashboard/runtime_dashboard.py --serve`
from this repository folder and open <http://127.0.0.1:8765>. It also compares
the last five matching runs with the previous five. See `dashboard/README.md`.

## Development

Run the QGIS-independent test suite from the plugin directory:

```bash
python3 -m unittest \
  tests.test_ols_construction_policy \
  tests.test_ols_source_validation \
  tests.test_run_history \
  tests.test_runtime_dashboard
```

Run full discovery from a QGIS-configured Python environment; QGIS-dependent
modules cannot be imported by a normal system Python. For QGIS workflow fixtures
and release-gate commands, see [`tests/README.md`](tests/README.md) and
[`tests/fixtures/ols/README.md`](tests/fixtures/ols/README.md).

For AGL rule changes, also review
[`docs/airfield_ground_lighting_rules.md`](docs/airfield_ground_lighting_rules.md).
That file records the MOS sections, builder assumptions, and concessions that
are documented but not generated.

When adding new guideline logic, prefer placing it in the relevant
`guidelines/` or `surfaces/` module and keeping `safeguarding_builder.py`
focused on orchestration. This keeps the central processing code easier to
review and reduces the chance of accidental regressions across unrelated
guidelines.

If icons or Qt resources are changed, regenerate `resources_rc.py` with the
QGIS-compatible Qt resource compiler used by your local QGIS/PyQt installation.

Documentation conventions and the active backlog are in
[`docs/README.md`](docs/README.md) and [`docs/roadmap.md`](docs/roadmap.md).

## Current Limitations

- The plugin expects the QGIS project CRS to be projected and metre-based.
- Guideline A and Guideline H detailed generation are not fully implemented.
- Some specialised CNS and OLS cases depend on the available parameter tables in
  `dimensions/cns_dimensions.py` and `rulesets/mos139/ols_dimensions.py`.
- AGL generation models plan-view light locations and display characteristics.
  It does not validate photometric intensity, vertical beam distribution,
  circuiting, power supply, monitoring, serviceability, or obstacle screening.
- Some AGL concessions are documented rather than generated, including shortened
  CAT II approach lighting assessments and alternative CAT II/III continuing
  barrette layouts with sequenced flashing lights.
- Runtime validation should be performed in QGIS after code changes because many
  behaviours depend on QGIS APIs and live project state.
