# Design Aircraft Registry

**Status:** Current

`aircraft.csv` contains 388 aircraft from the user-supplied `aircraft_data.xlsx`,
sheet `ACD_Data`, rows 2–389, read on 15 September 2026. The workbook's field
definitions and source references are retained in `aircraft_data_dictionary.csv`.
These are the supplied workbook's values, not an independent manufacturer-data
verification. `source_row` identifies each original record.

## Selection and Storage

Each runway has one editable **Design aircraft** dropdown at the top of
**Runway Characteristics**. Type a code,
manufacturer or model to find an aircraft, then select it. **No design aircraft**
is valid whenever the calculation does not need aircraft dimensions.

The workbook's ICAO codes are unique and serve as stable `id` values, saved in
runway inputs as `design_aircraft_id`. Changing the displayed model name does
not change its ID. Unknown saved IDs remain visible and require a replacement
selection before generation. Do not reuse IDs for different aircraft.

CAP 168 uses the selected aircraft's `outer_main_gear_wheel_span_m`. Selecting an
aircraft also suggests the ARC letter using the largest listed
wingspan (including winglets). The letter remains editable; loading saved inputs
preserves their saved letter. Missing or unsupported wingspans leave the current
letter unchanged.

Selection also suggests modernised Annex 14 ADG from that wingspan and the higher
of `approach_speed_knot` and `approach_speed_maximum_knot`, using the existing
Annex 14 classifier. Both dimensions are required. The workbook's approach speed
at maximum landing weight is used as a threshold-speed proxy for this editable
suggestion; confirm the applicable aircraft configuration and threshold speed.
Missing inputs or values outside the classifier's range leave ADG unchanged.
Saved ADG overrides are preserved on loading. Selection does not change ARC
number, approach classification, weights or operating assumptions. FAA `faa_adg`,
`faa_aac` and `faa_tdg` remain separate source classifications.

Legacy inputs containing only `outer_main_gear_wheel_span_m` appear as a
**Saved custom gear width** entry, without nominating an aircraft. Choosing an
aircraft supersedes that value; choosing **No design aircraft** clears it.

## Field Mapping

- `ICAO_Code` becomes `id`; `Model_FAA` becomes `model`.
- `Main_Gear_Width_ft` becomes `outer_main_gear_wheel_span_m`. The dictionary
  defines it as the distance between the outer main-gear tyres.
- Dimensional `_ft` fields become `_m`, multiplied by exactly 0.3048.
- `_ft2` fields become `_m2`, multiplied by exactly 0.09290304.
- `_lb` fields become `_kg`, multiplied by exactly 0.45359237.
- `ADG`, `TDG` and `AAC` fields receive the `faa_` prefix.
- Other column names are lowercased. Source remarks, update values, model
  alternatives, speed ranges and winglet/non-winglet dimensions are retained.
- Blank and `N/A` values become empty CSV fields, never zero. Values are not
  filled from another variant or rounded during unit conversion.

## Updating

Edit the CSV using its existing metric columns and keep IDs stable. Preserve
variant-specific fields and source information. New records require a unique
ID, manufacturer and model; unavailable dimensions must stay blank. Reload the
plugin after changing the bundled CSV. The plugin reads it with Python's standard
CSV library and does not require Excel at runtime.
