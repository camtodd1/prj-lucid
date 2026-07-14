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

## Output And Styling

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
rulesets/mos139/                MOS139 C.07 2026 metadata, OLS, physical,
                                 marking, and lighting policy sources. See
                                 `rulesets/mos139/README.md`.
rulesets/mos139/classification.py
                                 MOS139 runway type mapping.
rulesets/mos139/physical_data.py
                                 MOS139 strip, RESA, pavement, and shoulder
                                 policy.
rulesets/mos139/taxiway.py      MOS139 taxiway separation policy.
rulesets/mos139/ols_surfaces.py MOS139 OLS surface dimensions and lookups.
frameworks/nasf/                Australian NASF safeguarding framework profile,
                                 policy parameters, and compatibility aliases.
docs/                            Planning notes, implementation matrices,
                                 TODOs, and reference mapping files.
styles/*.qml                     QGIS layer styling files.
metadata.txt                     QGIS plugin metadata.
resources.qrc                    Qt resource manifest.
```

## Runtime Test History

Every safeguarding generation run appends one compact JSON record to
`runtime_test_runs.txt` in the plugin directory. This includes QGIS runs and
headless workflow runs. Each line records the actor (`qgis user`, `codex
headless`, or an explicit override), airport, selected rulesets, completion
status, total and phase/module elapsed times, plugin/QGIS versions, Git commit,
and whether the working tree was dirty.

Set `SAFEGUARDING_BUILDER_RUN_AGENT` to override the actor,
`SAFEGUARDING_BUILDER_COMMIT` for packaged builds without `.git`, or
`SAFEGUARDING_BUILDER_RUN_HISTORY` to select another text-file path. The file
uses versioned JSON Lines so it remains append-only and can be reviewed or
parsed without migrating older records.

## Development Notes

After editing Python modules, run a syntax check from the plugin directory:

```bash
python3 -m py_compile safeguarding_builder.py safeguarding_builder_dialog.py dialog/*.py core/styles.py surfaces/physical.py guidelines/ols_guideline.py surfaces/specialised.py core/layers.py guidelines/simple.py guidelines/guideline_constants.py dimensions/*.py rulesets/*.py rulesets/mos139/*.py frameworks/*.py frameworks/nasf/*.py
```

For AGL rule changes, also review `docs/airfield_ground_lighting_rules.md`.
That file records the MOS sections, builder assumptions, and concessions that
are documented but not generated.

When adding new guideline logic, prefer placing it in the relevant
`guidelines/` or `surfaces/` module and keeping `safeguarding_builder.py`
focused on orchestration. This keeps the central processing code easier to
review and reduces the chance of accidental regressions across unrelated
guidelines.

If icons or Qt resources are changed, regenerate `resources_rc.py` with the
QGIS-compatible Qt resource compiler used by your local QGIS/PyQt installation.

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
