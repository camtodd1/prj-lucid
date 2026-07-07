# MOS139 QGIS Smoke Test - 2026-07-07

## Scope

Headless QGIS 4 smoke test for the default MOS139 workflow using a single
representative runway case.

Scenario inputs:

- Ruleset: `mos139_2019`.
- Framework: `nasf_aus`.
- Project CRS: `EPSG:28356`.
- One sealed asphalt runway, `05/23`, ARC `4E`, ADG `IV`.
- Primary end: Precision Approach CAT I.
- Reciprocal end: Non-Precision Approach.
- Displaced thresholds, pre-threshold areas, clearways, and stopways entered.
- MET station coordinates entered.
- AGL enabled, including stopway lights, displaced-threshold options, CAT I
  centreline/TDZ options, and one primary-end approach lighting row.
- Controlling OLS output enabled.

## Command

Run with the QGIS 4 runtime and bundled projection data:

```bash
QT_QPA_PLATFORM=offscreen \
PROJ_DATA=/Applications/QGIS-4.0.app/Contents/Resources/qgis/proj \
GDAL_DATA=/Applications/QGIS-4.0.app/Contents/Resources/gdal \
/Applications/QGIS-4.0.app/Contents/MacOS/python /private/tmp/mos139_smoke_test.py
```

The smoke runner was a temporary headless harness that loaded a saved-style
dialog payload, validated the dialog, exercised save/load JSON round-trip, ran
the plugin, and audited generated layers.

## Results

| Mode | Input valid | JSON round-trip | Layers | Features | Required layers missing | Empty/invalid generated geometry | File outputs | Summary report |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Memory | Yes | Yes | 67 | 1,802 | 0 | 0 | 0 | N/A |
| GeoPackage | Yes | Yes | 67 | 1,802 | 0 | 0 | 68 | Yes |

Required output coverage confirmed:

- ARP and runway centreline reference layers.
- MET station, enclosure, buffer, and obstacle buffer layers.
- Physical runway geometry, shoulders, pre-threshold runway/area, declared
  distances, stopways, clearways, strips, and RESA.
- Detailed runway markings and marking QA.
- Airfield Ground Lighting.
- MOS OLS, contours, airport-wide OLS, and controlling OLS POC layers.
- NASF windshear, wildlife, wind turbine, lighting/glare, and public safety
  area outputs.
- Specialised runway safeguarding and taxiway separation outputs.

## Observations

- No QGIS message-box validation failures were captured.
- No QGIS warning-level log entries were captured by the harness.
- GDAL emitted non-fatal GeoPackage warnings for writing `MULTIPOLYGON`
  geometries into polygon layers for displaced-threshold and pre-threshold-area
  marking outputs. The layers still wrote and reloaded successfully.
- QGIS emitted a non-fatal stylesheet parse warning for `lineEdit_airport_crs`
  in the headless dialog runtime.
- `resources_rc.py` was reported as not found/generated in the headless run;
  icons may be missing in that runtime, but layer generation was unaffected.

## Follow-Up

- Promote the temporary smoke harness into a committed regression script if this
  scenario should become repeatable CI or release evidence.
- Decide whether GeoPackage geometry-type warnings should be resolved by
  writing relevant marking layers as multipolygon-compatible outputs.
