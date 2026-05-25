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

The generated outputs are grouped under an airport-specific safeguarding group
in the QGIS layer tree.

## Main Functions

The plugin can generate:

- Airport reference point and runway centreline layers.
- Physical runway geometry, including runway pavement, shoulders, strips,
  runway-end safety areas, stopways, pre-threshold runway areas, and displaced
  threshold marking references.
- Optional Airfield Ground Lighting (AGL) layers, including runway edge,
  threshold, runway end, stopway, centreline, touchdown zone, and approach
  lighting features.
- MOS-informed AGL approach lighting for precision approach CAT II/III runway
  ends, including centreline barrettes, side-row barrettes, crossbars, and
  distance-coded centreline light positions.
- Guideline B windshear assessment zones.
- Guideline C wildlife management zones.
- Guideline D wind turbine assessment zones.
- Guideline E lighting control zones and airport-wide lighting areas.
- Guideline F obstacle limitation surfaces, including approach, take-off climb,
  transitional, inner horizontal, conical, outer horizontal, and related inner
  surfaces where applicable.
- Guideline G CNS building restricted areas based on selected CNS facilities.
- Guideline I public safety areas.
- Specialised surfaces, including runway airspace object assessment areas and
  taxiway separation offsets.
- MET station safeguarding surfaces where MET inputs are supplied.

Guideline A and Guideline H are currently represented as placeholders or layer
groups where relevant; their detailed generation logic is not yet implemented.

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
                                 geometry helpers, ARP/runway layers, MET
                                 surfaces, and Guideline E logic.
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
core/styles.py                   Mapping between layer style keys and QML files.
guidelines/guideline_constants.py
                                 Shared constants for guideline dimensions,
                                 references, contour intervals, and offsets.
guidelines/simple.py             Guideline A/B/C/D/G/I and CNS helper logic.
guidelines/ols_guideline.py      Guideline F and airport-wide OLS generation.
surfaces/physical.py             Physical runway and runway protection geometry.
surfaces/airfield_ground_lighting.py
                                 Airfield Ground Lighting generation and
                                 coincident-light resolution.
surfaces/specialised.py          Specialised surfaces such as RAOA and taxiway
                                 separation offsets.
dimensions/ols_dimensions.py     CASA MOS-style physical and OLS dimensions.
dimensions/cns_dimensions.py     CNS building restricted area dimensions.
dimensions/agl_dimensions.py     MOS-derived AGL dimensions, trigger helpers,
                                 and approach lighting profiles.
docs/                            Planning notes, implementation matrices,
                                 TODOs, and reference mapping files.
styles/*.qml                     QGIS layer styling files.
metadata.txt                     QGIS plugin metadata.
resources.qrc                    Qt resource manifest.
```

## Development Notes

After editing Python modules, run a syntax check from the plugin directory:

```bash
python3 -m py_compile safeguarding_builder.py safeguarding_builder_dialog.py dialog/*.py core/styles.py surfaces/physical.py guidelines/ols_guideline.py surfaces/specialised.py core/layers.py guidelines/simple.py guidelines/guideline_constants.py dimensions/*.py
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
  `dimensions/cns_dimensions.py` and `dimensions/ols_dimensions.py`.
- AGL generation models plan-view light locations and display characteristics.
  It does not validate photometric intensity, vertical beam distribution,
  circuiting, power supply, monitoring, serviceability, or obstacle screening.
- Some AGL concessions are documented rather than generated, including shortened
  CAT II approach lighting assessments and alternative CAT II/III continuing
  barrette layouts with sequenced flashing lights.
- Runtime validation should be performed in QGIS after code changes because many
  behaviours depend on QGIS APIs and live project state.
