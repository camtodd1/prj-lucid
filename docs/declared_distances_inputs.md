# Declared Distances Input Assessment

This note captures the first implementation step for declared distances: confirm
which inputs are already available, which values can be calculated from existing
data, and which values need new dialog inputs.

## Declared Distances To Support

- `TORA`: Take-off Run Available
- `TODA`: Take-off Distance Available
- `ASDA`: Accelerate-stop Distance Available
- `LDA`: Landing Distance Available

The intended data model is one declared-distance record per runway direction,
for example `07` and `25` for runway `07/25`.

## Already Available In Validated Runway Data

These values are already collected by the dialog and passed into
`runway_data`:

- `designator_num`: primary runway designator number.
- `suffix`: optional runway suffix, one of blank, `L`, `C`, `R`.
- `short_name`: calculated runway name, for example `07/25`.
- `thr_point`: primary threshold coordinate.
- `rec_thr_point`: reciprocal threshold coordinate.
- `runway_end_elev_1`: primary physical runway-end elevation.
- `runway_end_elev_2`: reciprocal physical runway-end elevation.
- `threshold_elev_1`: primary landing-threshold elevation, defaulting to `runway_end_elev_1` when blank.
- `threshold_elev_2`: reciprocal landing-threshold elevation, defaulting to `runway_end_elev_2` when blank.
- `thr_displaced_1`: displaced threshold length at the primary end.
- `thr_displaced_2`: displaced threshold length at the reciprocal end.
- `thr_pre_area_1`: pre-threshold area length at the primary end.
- `thr_pre_area_2`: pre-threshold area length at the reciprocal end.
- `width`: runway width.
- `arc_num`: ARC number.
- `arc_let`: ARC letter.
- `type1`: primary end runway type.
- `type2`: reciprocal end runway type.

The centreline layer already has placeholder attributes for `TODA`, `TORA`,
`LDA`, and `ASDA`, but they are currently written as `None`.

## Already Calculable From Existing Data

These values do not need new UI inputs:

- Primary end designator.
- Reciprocal end designator.
- Threshold-to-threshold landing length.
- Runway azimuth in both directions.
- Physical pavement end near the primary threshold.
- Physical pavement end near the reciprocal threshold.
- Physical runway length, using threshold points plus displaced-threshold
  lengths.
- LDA for each landing direction, assuming the existing threshold coordinates
  are landing thresholds.

Baseline calculated values:

- `LDA primary direction = threshold-to-threshold length + reciprocal displaced threshold`
- `LDA reciprocal direction = threshold-to-threshold length + primary displaced threshold`
- `Physical length = threshold-to-threshold length + primary displaced threshold + reciprocal displaced threshold`

For the common case with no operational restrictions:

- `TORA = physical runway length`
- `TODA = TORA + clearway at departure end`
- `ASDA = TORA + stopway at departure end`

## Clearway Defaults And Dialog Overrides

Clearways are generated per MOS 6.27-6.29. By default, each clearway extends
from the physical runway end to the calculated runway strip end. A
user-supplied clearway length:

- overrides the default when it is longer than the runway-to-strip-end distance;
- is ignored with a warning when it is shorter than that default;
- is capped at half the TORA.

## Missing Inputs Needed For Correct Declared Distances

Add these per runway end:

- `clearway1_len`: clearway length beyond the primary physical runway end.
- `clearway2_len`: clearway length beyond the reciprocal physical runway end.
- `stopway1_len`: stopway length beyond the primary physical runway end.
- `stopway2_len`: stopway length beyond the reciprocal physical runway end.

Add these per runway direction:

- `takeoff_available_1`: whether takeoff is available from the primary end.
- `takeoff_available_2`: whether takeoff is available from the reciprocal end.
- `landing_available_1`: whether landing is available toward the primary end.
- `landing_available_2`: whether landing is available toward the reciprocal end.

Optional, but recommended for real airport data:

- `tora_override_1`, `tora_override_2`
- `toda_override_1`, `toda_override_2`
- `asda_override_1`, `asda_override_2`
- `lda_override_1`, `lda_override_2`
- `declared_distance_source`
- `declared_distance_notes`

Overrides are needed because published declared distances can be reduced by
operational constraints that are not inferable from geometry alone.

## Proposed Dialog UI Additions

Add a collapsible section to each runway group named `Declared Distances`.

Recommended first-pass controls:

- Primary end clearway length `(m)`.
- Reciprocal end clearway length `(m)`.
- Primary end stopway length `(m)`.
- Reciprocal end stopway length `(m)`.
- Primary direction takeoff available checkbox.
- Reciprocal direction takeoff available checkbox.
- Primary direction landing available checkbox.
- Reciprocal direction landing available checkbox.

Default behavior:

- Clearway and stopway blank values validate as zero.
- Takeoff and landing availability default to checked.
- Overrides can be deferred to a second pass.

Recommended second-pass controls:

- Optional declared-distance override fields for `TORA`, `TODA`, `ASDA`, and
  `LDA` in both directions.
- Source/notes text field.

## Validation Rules

Add validation for:

- Clearway and stopway lengths must be non-negative.
- Displaced threshold lengths must not exceed physical runway length.
- `TODA` must be greater than or equal to `TORA`.
- `ASDA` must be greater than or equal to `TORA`.
- `LDA` must be positive when landing is available.
- Declared distances should be blank or zero when the relevant operation is not
  available.
- Override values should be positive when supplied.

## Recommended Implementation Sequence

1. Add clearway and stopway inputs to `RunwayWidgetGroup`. (Done)
2. Persist and restore the new inputs in `dialog/persistence.py`. (Done)
3. Validate the new inputs in `SafeguardingBuilderDialog._validate_runway_data`. (Done)
4. Reuse `clearway1_len` and `clearway2_len` in existing TOCS logic.
5. Add a pure calculation helper for declared distances. (Done)
6. Add a generated point layer or table with two records per runway. (Done)
7. Populate the centreline placeholder fields where practical. (Done)
8. Add validation warnings for inconsistent declared-distance results.
9. Add optional override fields.
10. Feed declared-distance outputs into the future runway summary report.
