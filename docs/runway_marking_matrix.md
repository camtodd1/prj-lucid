# MOS139 Runway Marking Matrix

**Status:** Working reference

**Last reviewed:** 16 July 2026

This matrix is the interpretation layer between MOS139 runway marking
requirements and the generator implementation. Each marking family should be
completed here before coding so the geometry, styling, applicability, and MOS
references are traceable.

## Implementation Principles

- Prefer real generated geometry for runway markings that must export reliably
  to qgis2web and other GIS formats.
- Use QML marker-line styling only where repeated symbolic markings are simpler
  and have already proven reliable.
- Store MOS references beside the generated features where practical.
- Keep applicability rules data-driven so marking behavior can be audited and
  extended without rewriting geometry logic.

## Existing Inputs Available

- Runway designators and reciprocal designators.
- Threshold coordinates.
- Reciprocal threshold coordinates.
- Runway width.
- Runway length between landing thresholds.
- Physical runway ends, calculated from displaced thresholds.
- Displaced threshold distances.
- Pre-threshold area lengths.
- ARC number and ARC letter.
- Approach type per runway end.

## Potential Additional Inputs

These should be added only if MOS139 requirements cannot be inferred from
existing data:

- Whether runway is sealed/paved.
- Whether a marking family is intentionally omitted.
- Published/airport-specific marking overrides.
- Marking standard/profile override.
- Manual applicability overrides per runway end.

## Confirmed Defaults And Decisions

- Assume runways are sealed concrete/asphalt until a later runway surface type
  enhancement is added to the input dialog.
- Generate markings by default when the rule is mandatory or recommended, and
  add a feature attribute indicating whether the marking is mandatory.
- For threshold piano keys, edge spaces between the outermost stripes and runway
  edge must be at least the Table 8.17(2) stripe-space value `a`; use residual
  distance after fitting complete stripes to distribute larger edge spaces where
  needed.
- Threshold piano key stripes start 6 m after the 1.2 m transverse threshold
  line.
- Initial runway designation marking implementation may use controlled text/SVG;
  polygon glyph geometry is tracked in [`roadmap.md`](roadmap.md).
- The 12 m runway designation offset is measured from the threshold marking to
  the nearest edge of the runway designation number.
- Default runway centreline pattern is 30 m stripe length and 20 m gap.
- Do not implement the take-off RVR less than 550 m centreline-width trigger in
  the current enhancement.
- Generate one centreline stripe set for the entire runway. The reciprocal-end
  final stripe may be truncated to preserve the 12 m offset from the reciprocal
  runway designation marking.
- Precision approach aiming point ranges use the higher permitted values by
  default, including 23 m lateral spacing where 18-23 m is permitted.
- Non-precision and non-instrument aiming point markings default to the MOS
  8.22(8) alternate standard.
- Non-precision and non-instrument touchdown zone markings default to the simple
  pattern.
- Touchdown zone marking locations are measured to the threshold-side edge of
  each rectangle.
- The 550 m midpoint exclusion zone is tested against the full touchdown-zone
  rectangle footprint.
- Simple touchdown-zone stripe length defaults to exactly 22.5 m.
- Do not apply the optional 450 m simple touchdown-zone pair omission by
  default on runways under 1500 m.
- Side-stripe outer edges must be separated by the runway width.
- Do not add a MOS 8.21(7) side-stripe omission option in the current
  enhancement; generate side stripes by default under the sealed-runway
  assumption.
- Taxiway intersections do not need to break side stripes in the current
  enhancement. Intersecting runways do affect side stripes and need a later
  rule.
- Side-stripe longitudinal extent is the physical pavement between runway
  thresholds.

## Marking Family Status

| Marking family | Status | Implementation target |
| --- | --- | --- |
| Threshold markings / piano keys | Drafting requirements | Generated polygon geometry |
| Runway designation markings | Drafting requirements | Generated geometry or controlled text/SVG glyphs |
| Centreline markings | Drafting requirements | Generated polygon geometry |
| Aiming point markings | Drafting requirements | Generated polygon geometry |
| Touchdown zone markings | Drafting requirements in progress | Generated polygon geometry |
| Side stripe markings | Drafting requirements | Generated polygon geometry |
| Displaced threshold markings | Implemented | Generated white polygon geometry |
| Pre-threshold area chevrons | Implemented | Generated yellow polygon geometry |
| Marking QA report | Implemented as compact point/table layer | One feature per runway end |

## Promotion And Legacy Layer Policy

- The `Detailed Runway Markings` group is the primary output for generated
  MOS139 runway markings.
- Displaced-threshold arrows and pre-threshold area chevrons are generated as
  detailed polygon markings.
- Legacy symbolic runway marking layers are no longer generated in the normal
  runway marking path.
- A compact `Runway Marking QA` layer should be generated with one threshold
  point feature per runway end. Its attribute table lists generated mandatory
  marking families, generated optional/recommended marking families,
  assumptions used, and skipped markings with reasons where the generator can
  determine them.

## Cross-Cutting Rule: Intersecting Runways

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.15 | At runway intersections, markings of the runway with the highest nominated code, or the highest aircraft movement rate, must take precedence over, or interrupt, markings of the other runway. | Applies to runway marking overlaps at runway intersections. |

### Implementation Interpretation

- When generated runway marking geometries overlap an intersecting runway,
  decide which runway has precedence.
- The higher-precedence runway markings remain continuous through the
  intersection.
- The lower-precedence runway markings are interrupted/clipped around the
  intersection area.
- Centreline markings remain continuous through crossing-runway overlaps.
- Side-stripe markings are removed where they cross intersecting runway
  pavement under MOS 8.21(6).
- Precedence is determined by highest full nominated code number/letter first.
  If full nominated codes are tied, the longest runway distance takes
  precedence.

### Additional Inputs Needed

| Input | Scope | Reason |
| --- | --- | --- |
| Full nominated runway code number/letter | Per runway | Existing ARC/code number and letter inputs should be sufficient. |
| Runway distance for tie-break | Per runway/calculated | Use longest runway distance when full nominated codes are tied. |
| Runway intersection geometry | Calculated | Can likely be derived from generated runway pavement polygons. |

### Open Questions

- For lower-precedence markings, should clipping remove the exact overlap with
  the higher-precedence runway pavement polygon, or include a small clearance
  buffer?

## 1. Threshold Markings / Piano Keys

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.17(1) | Runway threshold markings must be provided on sealed concrete/asphalt runways, and on unsealed runways with sealed concrete/asphalt thresholds. | Generated when runway surface category is `Sealed`; unsealed runways with separate sealed thresholds are not modelled yet. |
| MOS 8.17(2)(a) | A permanent threshold, or permanently displaced threshold, must be indicated by a white transverse line at the threshold location. | Line is 1.2 m wide and extends the full runway width at the threshold. |
| MOS 8.17(2)(b) | Beyond the transverse line, white piano key markings consist of adjacent, uniformly spaced, 30 m long stripes. | Stripe number and stripe-space width are from Table 8.17(2). |
| MOS 8.17(4) and Table 8.17(2) | For listed runway widths, stripe count and width of spaces between stripes are set by the table. | Table widths: 18, 23, 30, 45, 60 m. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Non-instrument runway | Yes, if runway/threshold surface condition in MOS 8.17(1) is met. | No approach-type exclusion provided in supplied text. |
| Non-precision approach runway | Yes, if runway/threshold surface condition in MOS 8.17(1) is met. | No approach-type exclusion provided in supplied text. |
| Precision approach CAT I runway | Yes, if runway/threshold surface condition in MOS 8.17(1) is met. | No approach-type exclusion provided in supplied text. |
| Precision approach CAT II/III runway | Yes, if runway/threshold surface condition in MOS 8.17(1) is met. | No approach-type exclusion provided in supplied text. |
| ARC/code number dependency | No dependency identified from supplied MOS 8.17 text. | Width controls stripe count/spacing. |
| Runway width dependency | Yes. | Table 8.17(2) controls stripe count and space width for listed runway widths. |
| Displaced threshold dependency | Yes. | A permanent or permanently displaced threshold receives the transverse threshold line and piano keys at the threshold location. |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Transverse threshold line width | 1.2 | m | Measured along runway direction. |
| Transverse threshold line length | Full runway width at threshold | m/rule | Extends across runway width at the threshold location. |
| Number of threshold stripes | Width 18 m: 4; 23 m: 6; 30 m: 8; 45 m: 12; 60 m: 16 | count | From Table 8.17(2). |
| Stripe length | 30 | m | Measured away from threshold into runway direction, beyond the transverse line. |
| Stripe width | Derived from runway width, stripe count, stripe-space width, residual edge space, and the widened centre gap. | m | Edge spaces must be at least `a`; distribute residual distance to edge spaces when needed. |
| Gap between stripes | Width 18/23/30 m: 1.5; width 45/60 m: 1.7 | m | Table 8.17(2), space denoted as `a` in Figure 8.17(2). The gap between the two middle stripes is `2 x stripe width`. |
| Overall marking width | Full threshold marking arrangement across runway width | m/rule | Edge gaps may be greater than `a` depending on residual width after fitting complete stripes. |
| Longitudinal offset from threshold | Transverse line starts at threshold; piano keys start 6 m after the 1.2 m transverse threshold line. | rule | Offset is measured into runway direction after the transverse line. |
| Lateral offset / centering rule | Uniformly spaced across runway width, with a widened centre gap between the two middle stripes. | rule | Edge spaces between outermost stripes and runway edge are equal to or greater than `a`; the centre gap is `2 x stripe width`. |
| Color | White | n/a | Applies to transverse line and piano key stripes. |
| Orientation | Aligned with runway centreline | rule | Rectangles should be generated in the local runway coordinate system. |

### Stripe Count And Spacing Table

| Runway width | Number of stripes | Width of stripe space |
| --- | ---: | ---: |
| 18 m | 4 | 1.5 m |
| 23 m | 6 | 1.5 m |
| 30 m | 8 | 1.5 m |
| 45 m | 12 | 1.7 m |
| 60 m | 16 | 1.7 m |

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Threshold Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per stripe |
| Group | Physical Geometry |
| Style | New QML style or existing white fill style |
| Attributes | `rwy`, `end_desig`, `mark_type`, `stripe_no`, `len_m`, `wid_m`, `mandatory`, `ref_mos`, `notes` |

### Open Questions

- Later surface type enhancement should replace the current sealed
  concrete/asphalt default assumption.
- Confirm exact piano-key stripe width formula once Figure 8.17(2) is available,
  using the confirmed rule that edge spaces are at least `a`.

## 2. Runway Designation Markings

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.18(6) | Location and orientation of runway designation markings must be as shown in Figure 8.18(6). | Markings are centred on the runway centreline and oriented for the approach direction. |
| MOS 8.18(7) | Distance from the threshold marking to the corresponding runway designation marking must be 12 m. | Figure 8.18(6) shows this from threshold marking to the nearest designation marking element. |
| MOS 8.18(8) | Shape and dimensions of numbers and letters must be as shown in Figure 8.18(8). | Requires encoded glyph geometry or controlled SVG/text templates. |
| MOS 8.18(9) | Each number or letter must be 9 m high. | General glyph height. |
| MOS 8.18(10) | Numbers `6` and `9` must be 9.5 m high, without affecting other spacing in Figure 8.18(8). | Special glyph height exception. |
| MOS 8.18(11) | On parallel runways, distance between runway designation number and letter `L`, `C`, or `R` must be 6 m. | Applies to suffix letters. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Runway with threshold markings | Yes | Designation is positioned relative to the corresponding threshold marking. |
| Non-instrument runway | Yes, if runway designation markings are required for the runway. | No approach-type exclusion provided in supplied text. |
| Non-precision approach runway | Yes, if runway designation markings are required for the runway. | No approach-type exclusion provided in supplied text. |
| Precision approach CAT I runway | Yes, if runway designation markings are required for the runway. | No approach-type exclusion provided in supplied text. |
| Precision approach CAT II/III runway | Yes, if runway designation markings are required for the runway. | No approach-type exclusion provided in supplied text. |
| Parallel runway suffix dependency | Yes | If designator includes `L`, `C`, or `R`, generate suffix letter with 6 m gap from number. |
| Displaced threshold dependency | Yes | Position from the corresponding permanent or permanently displaced threshold marking. |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Longitudinal offset from threshold marking | 12 | m | Measured from threshold marking to corresponding designation marking, per Figure 8.18(6). |
| Digit/letter height | 9 | m | Applies to all numbers/letters except `6` and `9`. |
| Digit height exception | 9.5 | m | Applies to numbers `6` and `9`; other spacing remains unchanged. |
| Gap between runway number and suffix letter | 6 | m | Applies to parallel runway designations with `L`, `C`, or `R`. |
| Color | White | n/a | Implied runway marking color; confirm if needed. |
| Orientation | Oriented for approach direction | rule | Marking should be readable from the approach end, aligned with runway centreline. |
| Lateral placement | Centred on runway centreline | rule | Figure 8.18(6). |
| Glyph shapes | As shown in Figure 8.18(8) | m | Polygon glyph templates are tracked in [`roadmap.md`](roadmap.md). |

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Runway Designation Markings` |
| Geometry type | Controlled text/SVG for initial implementation; polygon glyphs tracked in [`roadmap.md`](roadmap.md) |
| Feature granularity | One feature per glyph or one multipart feature per full designation |
| Group | Physical Geometry |
| Style | White fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `glyph`, `glyph_no`, `height_m`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- Initial implementation can use controlled text or SVG markings.
- Polygon glyph geometry is tracked in [`roadmap.md`](roadmap.md).
- Placement should be calculated in runway-local coordinates:
  - longitudinal axis: runway centreline direction from threshold into runway;
  - lateral axis: perpendicular to runway centreline;
  - origin: threshold marking reference point.
- For two-digit runway numbers, treat the number group as a centred block. Exact inter-digit spacing should be taken from Figure 8.18(8) or confirmed separately.

### Open Questions

- Confirm inter-digit spacing for two-digit runway numbers.
- Confirm whether the designation number and optional suffix letter should be generated as separate features or one multipart feature.

## 3. Centreline Markings

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.19(3) | Runway centreline markings must be uniformly spaced white stripes, each stripe equal length and each gap equal length. | See Figure 8.19(3). |
| MOS 8.19(4) | Combined stripe length `S` plus gap length `G` must be at least 50 m and not more than 75 m. | `50 m <= S + G <= 75 m`. |
| MOS 8.19(5) | Each stripe length must be at least the greater of each gap length or 30 m. | `S >= max(G, 30 m)`. |
| MOS 8.19(6) | First stripe must commence 12 m from the runway designation number. | Applies after runway designation marking placement. |
| MOS 8.19(7)(a) | Centreline marking width must be at least 0.3 m for non-instrument runways and code 1/2 instrument non-precision approach runways. | Requires runway type and ARC/code number. |
| MOS 8.19(7)(b) | Centreline marking width must be at least 0.45 m for code 3/4 instrument non-precision approach runways and CAT I precision approach runways. | Requires runway type and ARC/code number. |
| MOS 8.19(7)(c) | Centreline marking width must be at least 0.9 m for CAT II/III precision approach runways and runways with take-off RVR less than 550 m. | CAT II/III trigger retained; take-off RVR less than 550 m trigger is disregarded for current enhancement. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Runway with designation marking | Yes | First stripe location is relative to runway designation number. |
| Non-instrument runway | Yes | Width at least 0.3 m. |
| Code 1 or 2 instrument non-precision approach runway | Yes | Width at least 0.3 m. |
| Code 3 or 4 instrument non-precision approach runway | Yes | Width at least 0.45 m. |
| CAT I precision approach runway | Yes | Width at least 0.45 m. |
| CAT II/III precision approach runway | Yes | Width at least 0.9 m. |
| Take-off RVR less than 550 m | Not implemented in current enhancement | Requirement deliberately disregarded for now. |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Stripe color | White | n/a | MOS 8.19(3). |
| Stripe length `S` | At least max(`G`, 30) | m | Need selected design values satisfying MOS. |
| Gap length `G` | Equal length for each gap | m | Need selected design values satisfying MOS. |
| Stripe plus gap length | 50 to 75 inclusive | m | `50 <= S + G <= 75`. |
| First stripe offset | 12 | m | Measured from runway designation number, per Figure 8.19(3). |
| Width for non-instrument | At least 0.3 | m | Also code 1/2 instrument NPA. |
| Width for code 1/2 instrument NPA | At least 0.3 | m | Depends on ARC/code number and runway type. |
| Width for code 3/4 instrument NPA | At least 0.45 | m | Depends on ARC/code number and runway type. |
| Width for CAT I PA | At least 0.45 | m | Depends on runway type. |
| Width for CAT II/III PA | At least 0.9 | m | Depends on runway type. |
| Width for take-off RVR < 550 m | Not implemented in current enhancement | n/a | Requirement deliberately disregarded for now. |
| Orientation | Aligned with runway centreline | rule | Rectangles generated in runway-local coordinates. |
| Lateral placement | Centred on runway centreline | rule | Figure 8.19(3). |

### Proposed Default Design Values

These satisfy MOS 8.19(4) and 8.19(5), but should be confirmed before
implementation:

| Parameter | Proposed value | Reason |
| --- | ---: | --- |
| Stripe length `S` | 30 m | Confirmed default. |
| Gap length `G` | 20 m | Confirmed default; gives `S + G = 50 m`, within permitted range, and `S >= G`. |
| Pattern interval | 50 m | Confirmed default interval. |

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Runway Centreline Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per stripe |
| Group | Physical Geometry |
| Style | White fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `stripe_no`, `len_m`, `wid_m`, `gap_m`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- Generate actual stripe polygons instead of relying on QML dash patterns, so
  qgis2web/export output remains deterministic.
- Generate one centreline stripe set for the entire runway, not separate
  duplicate sets from each end.
- The first stripe depends on runway designation marking placement, so the
  marking rules should expose the designation group's up-runway/down-runway
  bounds.
- If runway designation markings are not generated yet, use a provisional
  offset based on MOS 8.18:
  `threshold marking + 12 m + designation glyph height/block + 12 m`.
- The reciprocal-end final stripe can be truncated if needed to preserve the
  12 m offset from the reciprocal runway designation marking.
- The centreline protected zone at each end should be derived from the nearest
  edge of the runway designation number, consistent with the confirmed MOS
  8.18 offset interpretation.

### Open Questions

No open centreline questions from the supplied MOS 8.19 text after current
decisions.

## 4. Aiming Point Markings

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.22(2) | Aiming point markings must comply with section 8.22 and sections 8.23, 8.24 and 8.25. | Sections 8.23-8.25 have been captured for touchdown zone dependencies. |
| MOS 8.22(3) | For a precision approach runway, the aiming point marking consists of 2 conspicuous stripes with location and dimensions from Table 8.22(3). | Controlled by LDA. |
| MOS 8.22(4) | For Table 8.22(3), the aiming point marking must be located not more than the Row A distance from threshold for the relevant LDA column. | Uses landing distance available. |
| MOS 8.22(5) | Length, width, and lateral spacing between inner sides are Row B, C and D values for the relevant LDA column. | Uses landing distance available. |
| MOS 8.22(6)(a) | Superscript `a` means the greater dimension of the specified range may be used if increased conspicuity is required. | Applies to stripe length ranges in Table 8.22(3). |
| MOS 8.22(6)(b) | Superscript `c` means lateral spacing may be varied within the stated limits to minimise rubber contamination. | Applies to 18-23 m spacing range. |
| MOS 8.22(8) | For NPA or NI runway, aiming point marking must comply with the relevant precision approach standard or the alternate Table 8.22(8) standard. | Alternate standard uses 45 m stripe length and width/spacing by runway width. |
| MOS 8.22(8)(b)(ii) | For the alternate NPA/NI standard, stripe ends nearest the threshold are located 300 m from runway threshold line. | Fixed location for alternate standard. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Precision approach runway | Yes | Use Table 8.22(3), selected by LDA. |
| Non-precision approach runway | Yes | May use relevant precision approach standard or alternate Table 8.22(8) standard. |
| Non-instrument runway | Yes | May use relevant precision approach standard or alternate Table 8.22(8) standard. |
| LDA dependency | Yes | Precision standard depends on landing distance available. |
| Landing available unchecked | No | Do not generate aiming point markings for that runway end. |
| Runway width dependency | Yes for alternate NPA/NI standard. | Table 8.22(8) covers 30 m and 45 m or more. |
| VASIS dependency | Possibly | Table 8.22(3) Row A note references subsection 8.22(7), not yet supplied. |

### Precision Approach Geometry Parameters

| LDA range | Distance from threshold to beginning | Stripe length | Stripe width | Inner-side lateral spacing |
| --- | ---: | ---: | ---: | ---: |
| Less than 800 m | 150 m | 30-45 m | 4 m | 6 m |
| 800 m up to, but not including, 1200 m | 250 m | 30-45 m | 6 m | 9 m |
| 1200 m up to, but not including, 2400 m | 300 m | 45-60 m | 9 m | 18-23 m |
| 2400 m and above | 400 m | 45-60 m | 9 m | 18-23 m |

### Non-Precision / Non-Instrument Alternate Geometry Parameters

| Runway width | Stripe length | Stripe width `W` | Inner-side spacing `D` | Location |
| --- | ---: | ---: | ---: | --- |
| 30 m | 45 m | 6 m | 17 m | Ends nearest threshold at 300 m from threshold line |
| 45 m or more | 45 m | 9 m | 23 m | Ends nearest threshold at 300 m from threshold line |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Number of stripes | 2 | count | One each side of runway centreline. |
| Color | White | n/a | Described as conspicuous stripes; runway marking color assumed white unless later text says otherwise. |
| Stripe orientation | Aligned with runway centreline | rule | Rectangles generated in runway-local coordinates. |
| Lateral placement | Symmetric about runway centreline | rule | Inner-side spacing controls gap between the two stripes. |
| Precision stripe length | Table 8.22(3), Row B | m | Use lower bound by default unless increased conspicuity is selected. |
| Precision stripe width | Table 8.22(3), Row C | m | Selected by LDA. |
| Precision inner-side spacing | Table 8.22(3), Row D | m | Use upper bound by default for 18-23 m range unless a lower spacing is selected for rubber contamination control. |
| Precision location | Table 8.22(3), Row A | m | Beginning of marking not more than listed threshold distance. |
| NPA/NI alternate stripe length | 45 | m | MOS 8.22(8)(b)(i). |
| NPA/NI alternate location | 300 | m | Ends nearest threshold at 300 m from threshold line. |

### Proposed Defaults

| Case | Proposed default | Reason |
| --- | --- | --- |
| Precision stripe length range 30-45 m | 30 m | Confirmed lower-end default. |
| Precision stripe length range 45-60 m | 45 m | Confirmed lower-end default. |
| Precision lateral spacing range 18-23 m | 23 m | Confirmed default. |
| NPA/NI standard choice | Use alternate Table 8.22(8) when runway width is 30 m or at least 45 m; otherwise flag unresolved. | Confirmed default for non-precision and non-instrument runways. |

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Aiming Point Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per stripe |
| Group | Physical Geometry |
| Style | White fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `side`, `len_m`, `wid_m`, `spacing_m`, `offset_m`, `lda_m`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- This marking should use declared `LDA` where available.
- For each runway end, generate the pair of stripes in the landing direction,
  measured from that end's threshold line into the runway.
- For precision approach runways, select Table 8.22(3) by `LDA`.
- For NPA/NI runways, either:
  - use the alternate Table 8.22(8) rule; or
  - optionally use the relevant precision approach standard if a user override
    requests that.
- If landing is not available for a runway end, skip aiming point markings for
  that end entirely.
- The phrase "not more than" in MOS 8.22(4) allows a marking closer than the
  Row A value; default should use the listed Row A value unless another section
  or VASIS rule requires otherwise.

### Open Questions

- Please provide MOS 8.22(7), especially the VASIS note referenced by Table 8.22(3) Row A.
- MOS 8.23, 8.24 and 8.25 have now been supplied; resolve the open
  interpretation questions before final implementation.
- Confirm whether a precision-standard aiming point override is still useful
  for non-precision/non-instrument runways.

## 5. Touchdown Zone Markings

Status: drafting requirements in progress. MOS 8.23, 8.24 and 8.25 received;
open interpretation questions remain before implementation.

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.23(1) | A touchdown zone marking must be provided at each end of a sealed concrete/asphalt runway at least 30 m wide and at least 1500 m long. | Generated when runway surface category is `Sealed`; mandatory flag also requires width >= 30 m and length >= 1500 m. |
| MOS 8.23(1) Note | CASA recommends touchdown zone markings at both ends of other sealed concrete/asphalt runways. | Recommendation, not mandatory based on supplied text. |
| MOS 8.23(2)(a) | On a precision approach runway, touchdown zone marking must use ICAO `A` basic pattern in accordance with section 8.24. | MOS 8.24 geometry captured below. |
| MOS 8.23(2)(b) | On other runways, touchdown zone marking may use ICAO `A` basic pattern or simple pattern. | Default is simple pattern for non-precision/non-instrument runways. |
| MOS 8.24(1) | ICAO `A` basic pattern consists of pairs of white rectangular markings symmetrically disposed about the runway centreline. | Generated as paired polygon rectangles. |
| MOS 8.24(2)(a) | Each ICAO `A` touchdown zone marking rectangle is 22.5 m long and 3 m wide. | See Figure 8.24(2)-1. |
| MOS 8.24(2)(b) | Lateral spacing between inner sides of the rectangles equals that of the aiming point markings. | Requires aiming-point spacing for the same runway end. |
| MOS 8.24(3) and Table 8.24(3) | Numbers and locations of pairs are set by LDA or distance between thresholds when markings are displayed at both approach directions. | Locations are distances from threshold. |
| MOS 8.24(4) | If the Table 8.24(3) number of pairs has superscript `a`, omit the touchdown zone marking within 50 m of the aiming point marking. | Affects rows 3, 4 and 5. |
| MOS 8.24(5) | A 550 m zone, symmetrical about the midpoint of runway length, must have no touchdown zone markings. | Prevents confusing markings from opposite ends. |
| MOS 8.24(6) | Any pair from either runway end that would otherwise fall within the 550 m midpoint zone must be omitted. | Requires runway midpoint and distance checks. |
| MOS 8.25(1) | Simple touchdown zone marking comprises 4 white stripes, each at least 22.5 m long and 3 m wide, located in pairs at 150 m and 450 m from the threshold line. | Lateral inner spacing equals aiming point marking spacing. |
| MOS 8.25(2) | If simple touchdown zone markings are provided on a runway less than 1500 m long, the 450 m markings may be omitted. | Optional omission for shorter runways. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Sealed concrete/asphalt runway, width >= 30 m and length >= 1500 m | Mandatory | Marking at each end. |
| Sealed concrete/asphalt runway below width/length thresholds | Recommended | CASA recommends at both ends, but supplied text does not make it mandatory. |
| Precision approach runway | Mandatory pattern: ICAO `A` basic pattern | Details in MOS 8.24. |
| Non-precision/non-instrument/other runway | Default simple pattern | ICAO `A` basic pattern can be retained as an override if required. |
| ICAO `A` basic pattern | Pairs by Table 8.24(3) | Uses LDA or distance between thresholds when displayed at both ends. |
| Landing available unchecked | No | Do not generate touchdown zone markings for that runway end. |
| Unsealed runway | Not specified in supplied MOS 8.23 text | Needs later confirmation if in scope. |

### Pattern Selection

| Runway category | Pattern |
| --- | --- |
| Precision approach runway | ICAO `A` basic pattern |
| Other runway | Simple pattern by default; ICAO `A` basic pattern as optional override |

### ICAO `A` Basic Pattern Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Marking pair layout | Pairs of rectangles symmetric about centreline | rule | MOS 8.24(1). |
| Rectangle length | 22.5 | m | Measured along runway direction. |
| Rectangle width | 3 | m | Measured laterally. |
| Inner-side lateral spacing | Same as aiming point markings | m | From the selected aiming point rule for the same runway end. |
| Color | White | n/a | MOS 8.24(1). |
| Locations | Table 8.24(3) distances from threshold | m | Measured to threshold-side edge of each rectangle. |
| Aiming point conflict omission | Omit marking within 50 m of aiming point marking when superscript `a` applies | rule | MOS 8.24(4). |
| Midpoint exclusion zone | 550 m zone symmetric about runway midpoint | m | Test against full rectangle footprint. |

### Simple Pattern Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Marking count | 4 stripes, arranged as 2 pairs | count | One pair at 150 m and one pair at 450 m. |
| Stripe length | 22.5 | m | Confirmed default; MOS minimum is not less than 22.5 m. |
| Stripe width | 3 | m | Measured laterally. |
| Pair locations | 150 m and 450 m from threshold line | m | Ends nearest threshold are at these distances. |
| Inner-side lateral spacing | Same as aiming point marking | m | From selected aiming point rule for same runway end. |
| Color | White | n/a | MOS 8.25(1). |
| Runway length under 1500 m | 450 m pair may be omitted, but do not omit by default | rule | MOS 8.25(2). |

### ICAO `A` Basic Pattern Table

| Item | LDA or threshold-to-threshold distance | Number of pairs | Pair locations from threshold |
| --- | --- | ---: | --- |
| 1 | Less than 900 m | 1 | 300 m |
| 2 | 900 m up to, but not including, 1200 m | 2 | 150 m, 450 m |
| 3 | 1200 m up to, but not including, 1500 m | 3 with superscript `a` | 150 m, 300 m, 450 m, 600 m |
| 4 | 1500 m up to, but not including, 2400 m | 4 with superscript `a` | 150 m, 300 m, 450 m, 600 m, 750 m |
| 5 | 2400 m or more | 5 with superscript `a` | 150 m, 300 m, 450 m, 600 m, 750 m, 900 m |

### ICAO `A` Basic Pattern Interpretation

- Table 8.24(3) column 3 appears to provide the target number of pairs after
  applying the superscript `a` aiming-point omission rule, while column 4 lists
  all candidate locations.
- For rows 3, 4 and 5, generate candidate pairs at the listed locations, then
  omit the pair within 50 m of the aiming point marking. This should leave the
  number of pairs shown in column 3.
- Apply the 550 m midpoint exclusion zone after aiming-point omission. This may
  further reduce the displayed number of pairs. Test the exclusion against the
  full rectangle footprint.
- When touchdown zone markings are displayed from both approach directions, the
  table selection should use distance between thresholds instead of LDA if that
  is the intended reading of column 2.

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Touchdown Zone Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per marking stripe/block |
| Group | Physical Geometry |
| Style | White fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `pattern`, `pair_no`, `side`, `len_m`, `wid_m`, `offset_m`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- Generate markings independently for each runway end, measured from the
  corresponding threshold into the runway.
- Use runway width and physical/landing runway length for mandatory
  applicability checks.
- Use approach type per runway end to choose ICAO `A` basic for precision
  approach runways and simple pattern for non-precision/non-instrument runways.
- If landing is not available for a runway end, skip touchdown zone markings for
  that end entirely.

### Open Questions

- Surface category/material is now collected in the runway dialog. Current
  marking gates treat `Sealed` as the applicable MOS sealed concrete/asphalt
  trigger.
- For sealed runways below 30 m width or 1500 m length, should the builder
  generate recommended touchdown zone markings by default, or only when an
  override is selected?
- Does "runway length" in MOS 8.23(1) mean threshold-to-threshold length,
  physical pavement length, or declared LDA/TORA for the runway end?
- Confirm whether Table 8.24(3) column 3 is the count after applying the
  superscript `a` omission rule, as inferred above.
- Confirm when to use LDA versus threshold-to-threshold distance for Table
  8.24(3) selection.

## 6. Side Stripe Markings

Status: drafting requirements. MOS 8.21 received; open interpretation questions
remain before implementation.

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.21(1) | Subject to MOS 8.21(7), runway side-stripe markings must be provided along each side edge of a sealed concrete/asphalt runway to delineate runway width. | Generated when runway surface category is `Sealed`. |
| MOS 8.21(2) | Except where broken for taxiways and other runways, side-stripe markings consist of one continuous white line whose width is at least the runway centreline marking width. | Requires centreline marking width rule. |
| MOS 8.21(3) | For an 18 m wide runway with no runway centreline marking, side-stripe width must be at least 0.3 m. | Special minimum width case. |
| MOS 8.21(4) | Distance between the outer edges of side-stripe markings must equal runway width. | Places stripe outer edges on the runway side edges. |
| MOS 8.21(5) | Side-stripe markings must be parallel to runway centreline and extend full runway length between runway end markings. | Longitudinal extent depends on runway end markings. |
| MOS 8.21(6) | Side-stripe markings must not extend across intersecting runways or taxiways. | Taxiways out of scope for current enhancement; intersecting runway rule to be expanded. |
| MOS 8.21(7) | Side-stripe markings may be omitted if the runway has no sealed shoulders and there is distinct contrast between runway edges and surrounding terrain. | No omission option in current enhancement; generate side stripes by default. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Sealed concrete/asphalt runway | Yes | Default is to generate side stripes. |
| Unsealed runway | Not specified in supplied text. | Do not generate by default unless later MOS text requires it. |
| No sealed shoulders and distinct edge contrast | Not modelled in current enhancement. | No omission option; generate side stripes by default. |
| Intersecting taxiway | No break in current enhancement. | Taxiways are out of scope. |
| Intersecting runway | Side stripe impact required. | Exact clipping/breaking rule to be expanded. |
| 18 m runway with no centreline marking | Special width minimum applies. | Minimum side-stripe width is 0.3 m. |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Number of side stripes | 2 | count | One along each runway side edge. |
| Color | White | n/a | MOS 8.21(2). |
| Stripe width | At least centreline marking width | m | Use generated/selected centreline width. |
| Special stripe width | At least 0.3 | m | Applies to 18 m runway with no centreline marking. |
| Lateral placement | Outer edges separated by runway width | rule | Confirmed: distance between the outer edges of side stripes equals runway width. |
| Orientation | Parallel to runway centreline | rule | Generate in runway-local coordinates. |
| Longitudinal extent | Physical pavement between runway thresholds | m/rule | Confirmed v1 interpretation for this builder. |
| Breaks | Side stripes are interrupted at intersecting runways | rule | Clip using intersecting runway pavement inset by one stripe width so truncated stripes form a point. Taxiway intersections are out of scope. |

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Runway Side-Stripe Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per continuous stripe segment |
| Group | Physical Geometry |
| Style | White fill with no outline |
| Attributes | `rwy`, `side`, `mark_type`, `len_m`, `wid_m`, `break_reason`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- Generate side stripes as polygons rather than QML line styles so the outer
  edge placement and qgis2web export are deterministic.
- Place stripes with their outer edge on the runway pavement side edge, giving
  an outer-edge-to-outer-edge separation equal to runway width.
- Taxiway intersections do not need to break side stripes in the current
  enhancement.
- Intersecting runway handling follows MOS 8.15 for general marking precedence.
  Centreline markings remain continuous, and side stripes are clipped wherever
  they cross intersecting runway pavement under MOS 8.21(6), with a one
  stripe-width extension into the crossing pavement to avoid blunt clipped ends.
- No MOS 8.21(7) omission checkbox is needed for v1; generate side stripes by
  default under the sealed-runway assumption.

### Open Questions

- Resolve whether the longest runway distance tie-break should use
  threshold-to-threshold length, physical pavement length, or declared TORA.
- Confirm whether clipping should use exact intersecting runway pavement overlap
  or include a clearance buffer.

## 7. Displaced Threshold Markings

Status: implemented as detailed generated polygon geometry.

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.26(1) | If a runway threshold is permanently displaced, displaced threshold markings must be provided as shown in Figures 8.26(1)-1 and 8.26(1)-2. | Applies when `thr_displaced_1` or `thr_displaced_2` is greater than zero. |
| MOS 8.26(2)(a) | The first arrow must point in the direction of the displaced threshold. | All generated arrows point from physical runway end toward the displaced threshold. |
| MOS 8.26(2)(b) | The tip of the first arrow head must end 20 m from the commencement of the displaced threshold's white piano key markings. | Current implementation uses piano-key commencement at threshold + 7.2 m, matching MOS 8.17 threshold-line plus piano-key offset. |
| MOS 8.26(2)(c) | Preceding complete arrows, pointing toward the displaced threshold, must be provided at 20 m intervals until the reciprocal runway end is reached. | Figure and MOS 8.26(2)(f) imply a 50 m arrow cycle; implementation places complete preceding arrows at 50 m tip-to-tip intervals. |
| MOS 8.26(2)(c) Note | A partial arrow must not be used if there is insufficient space at the reciprocal runway end for a complete arrow. | Generator only emits complete arrows. |
| MOS 8.26(2)(d) | Each arrow head is 10 m long, has 0.9-1 m line thickness, arms 3.5 m apart at widest dimension, and points toward the displaced threshold. | Implemented as two 0.9 m wide polygon arms. |
| MOS 8.26(2)(e) | The arrow stem must be the same width as the centreline marking. | Figure 8.26(1)-1 is interpreted as a 30 m total arrow length, including 10 m head and 20 m stem. |
| MOS 8.26(2)(f) | The combined length of arrow head, arrow stem and the gap between arrows must be 50 m. | With 30 m total arrow length, this leaves a 20 m gap in each 50 m cycle. |

### Current Implementation Interpretation

- Generate one white polygon arrow per displaced-threshold arrow position.
- The first arrow tip is 20 m before the commencement of the displaced
  threshold piano-key markings.
- Complete preceding arrows are placed back toward the runway end at 50 m
  tip-to-tip intervals. Partial arrows are not generated.
- Arrows are aligned on the runway centreline and point toward the displaced
  threshold.
- Arrow geometry is one generated feature with a 30 m total length: a 20 m
  centreline-width stem and two 10 m long, 0.9 m wide head arms, with the arms
  3.5 m apart at their widest dimension.

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Displaced Threshold Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per arrow |
| Group | Detailed Runway Markings |
| Style | White fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `sub_type`, `stripe_no`, `len_m`, `wid_m`, `offset_m`, `spacing_m`, `mandatory`, `ref_mos`, `notes` |

## 8. Pre-Threshold Area Chevrons

Status: implemented as detailed generated polygon geometry.

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.16(1) | If an area before the non-displaced threshold, or the runway end in the reciprocal direction, is sealed concrete/asphalt, is 30 m or more in length, and is not suitable for normal aircraft usage, pre-threshold area markings must be used. | Current dialog has pre-threshold area length but does not yet collect surface/suitability. |
| MOS 8.16(1) Note | This does not apply to runway starter extensions. | Starter extension classification is not modelled in the current dialog. |
| MOS 8.16(2)(a) | Markings consist of yellow chevrons with 0.9 m wide lines angled 45 degrees to the runway centreline. | Generated as yellow polygon legs. |
| MOS 8.16(2)(b) | Chevrons are spaced 30 m apart, apex to apex. | Stored as `spacing_m = 30`. |
| MOS 8.16(2)(c) | Chevrons are 15 m tall from apex to base. | Extended where needed so line ends target the runway-edge clearance rule. |
| MOS 8.16(2)(d) | Chevrons point towards the non-displaced threshold, or runway end in the reciprocal direction. | Apex is placed toward the runway end/threshold side. |
| MOS 8.16(2)(e) | Except near the threshold/runway end, line ends must be long enough to end not more than 7.5 m from the respective runway edges. | Current implementation targets this by extending the 45-degree legs for wider runways. |
| MOS 8.16(2)(f) | Markings terminate at the runway end marking. | First chevron apex starts near the runway end marking; partial-chevron clipping is tracked in [`roadmap.md`](roadmap.md). |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Pre-threshold area length >= 30 m | Yes | Uses dialog `thr_pre_area_1` / `thr_pre_area_2`. |
| Sealed concrete/asphalt surface | Uses runway surface category | Current implementation generates when category is `Sealed`. |
| Not suitable for normal aircraft usage | Assumed yes when pre-threshold area length is entered | Suitability input does not exist yet. |
| Runway starter extension | Not modelled | Add explicit input before suppressing markings for starter extensions. |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Marking shape | Chevron | n/a | Two legs per chevron. |
| Line width | 0.9 | m | MOS 8.16(2)(a). |
| Line angle | 45 | degrees | Angled to runway centreline. |
| Apex spacing | 30 | m | Apex to apex. |
| Nominal chevron height | 15 | m | Apex to base. |
| Edge clearance | Not more than 7.5 | m | Targeted where runway width requires longer legs. |
| Color | Yellow | n/a | MOS 8.16(2). |
| Direction | Points toward runway end/non-displaced threshold | rule | Apex is runway-end side, legs extend outward into the pre-threshold area. |

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Pre-Threshold Area Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per chevron |
| Group | Detailed Runway Markings |
| Style | Yellow fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `sub_type`, `side`, `stripe_no`, `len_m`, `wid_m`, `offset_m`, `spacing_m`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- Generate independently for each runway end with entered pre-threshold area
  length of 30 m or more.
- Use one mitered polygon per chevron to avoid extra apex-cap features and
  rendering artifacts at the apex.
- Place the first theoretical chevron apex 7.5 m on the runway side of the
  runway end marking, then clip to the pre-threshold area so only the outward
  half is visible, matching Figure 8.16(2).
- Use the physical runway end as the runway-end marking reference and project
  chevrons outward into the pre-threshold area.
- Legacy symbolic pre-threshold area line markings are no longer generated in
  the normal physical geometry pass.

## 9. Runway Holding Position Markings

Status: drafting requirements. MOS 8.39 received; the supplied extract now includes Table 6.56(1) minimum-distance geometry. Note b is disregarded for this builder; note a is recorded for later use but is not yet applied in geometry.

Although these markings are placed on taxiways, they are relevant to runway
modelling where LAHSO applies or where runway/runway taxi routing introduces a
runway holding position.

### MOS References

| Reference | Requirement summary | Notes |
| --- | --- | --- |
| MOS 8.39(1) | Runway holding position markings must be provided where an asphalt, sealed or concrete taxiway joins or intersects with a runway. | Applies at runway/taxiway interfaces. |
| MOS 8.39(2) | Subject to subsection (9), runway holding positions must be marked using Pattern A or Pattern B as shown in Figure 8.39(2). | Subsection (9) was not supplied. |
| MOS 8.39(3) | Pattern A must be used at a taxiway intersection with a non-instrument runway, a non-precision approach runway, a precision approach CAT I runway, a precision approach CAT II/III runway if only one runway holding position is marked, or a runway/runway intersection where one runway is used as part of a standard taxi route. | Captures the non-precision and single-position cases. |
| MOS 8.39(4) | Pattern A and Pattern B must be used where 2 or 3 runway holding positions are provided at an intersection of a taxiway with a precision approach runway. | Multiple holding positions require both patterns. |
| MOS 8.39(5)(a) | The runway holding position marking closest to the runway must be Pattern A. | Pattern ordering rule. |
| MOS 8.39(5)(b) | The other runway holding position marking or markings must be Pattern B. | Pattern ordering rule. |
| MOS 8.39(6) | Runway holding position markings must extend at least across the full width of the sealed taxiway surface. | Full sealed taxiway width minimum. |
| MOS 8.39(6) Note | If sealed shoulders are provided beyond the width of the taxiway, CASA recommends marking the full width of the sealed surface beyond the taxiway. | Recommendation, not mandatory from the supplied text. |
| MOS 8.39(7) | The position of a runway holding position marking must ensure that when the nose of an aircraft reaches the marking, the nose will not infringe the relevant minimum distance specified in section 6.56. | Offset uses Table 6.56(1); note b is disregarded. |

### Applicability

| Condition | Applies? | Notes |
| --- | --- | --- |
| Taxiway joins or intersects runway | Yes | Applies when the taxiway surface is asphalt, sealed or concrete. |
| Non-instrument runway | Yes | Pattern A. |
| Non-precision approach runway | Yes | Pattern A. |
| Precision approach CAT I runway | Yes | Pattern A. |
| Precision approach CAT II/III runway, one holding position | Yes | Pattern A. |
| Precision approach runway, two or three holding positions | Yes | Pattern A nearest runway, Pattern B for the other position(s). |
| Runway/runway intersection with standard taxi route | Yes | Pattern A. |
| Unsealed taxiway | Not specified in supplied text | Needs later confirmation. |
| LAHSO runway treatment | Yes, where a landing hold-short requirement is modelled | Relevant as a runway-side holding position control. |

### Geometry Parameters

| Parameter | Value / rule | Unit | Notes |
| --- | --- | --- | --- |
| Color | Yellow | n/a | Depicted in Figure 8.39(2). |
| Pattern A line width | 0.3 | m | Figure 8.39(2) shows four 0.3 m lines and three 0.3 m spaces. |
| Pattern A space width | 0.3 | m | Figure 8.39(2). |
| Pattern A count | 4 lines / 3 spaces | n/a | Figure 8.39(2). |
| Pattern A dashed segment length | 0.9 to 1.0 | m | The two lines closest to the intersecting runway use dashed segments of 0.9-1.0 m length. |
| Pattern A dashed gap length | 0.9 to 1.0 | m | The dashed segments are separated by 0.9-1.0 m gaps. |
| Pattern B line width | 0.3 | m | Figure 8.39(2). |
| Pattern B separation | 1.5 | m | Figure 8.39(2) depicts 1.5 m separation between the paired lines. |
| Pattern B overall width | 3.0 | m | Figure 8.39(2) shows 3.0 m between the outer limits of the paired elements. |
| Orientation | As shown in Figure 8.39(2) | rule | Oriented across the taxiway/runway interface. |
| Minimum extent | Full sealed taxiway width | rule | Marking must span the taxiway pavement width at minimum. |
| Offset from runway centreline | Table 6.56(1) minimum distance | rule | Determine by runway code number and runway type; note b is disregarded. |

### Table 6.56(1) Minimum Distance From Runway Centreline

| Runway code number | Non-instrument | Non-precision approach | Precision CAT I | Precision CAT II or CAT III | Take-off |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 30 m | 40 m | 60 m | n/a | 30 m |
| 2 | 40 m | 40 m | 60 m | n/a | 40 m |
| 3 | 75 m | 75 m | 90 m | 90 m | 75 m |
| 4 | 75 m | 75 m | 90 m | 90 m | 75 m |

### Table 6.56(1) Interpretation

- Use the table distance as the minimum offset from the associated runway
  centreline.
- For code numbers 1 and 2, the precision CAT II/CAT III column is not
  applicable in the supplied table extract.
- Note a allows the distance to be decreased by 5 m for every metre the holding
  position is below the threshold elevation, but only when the inner
  transitional surface is not infringed.
- Note b is disregarded for this builder.

### Generated Feature Model

| Field | Proposed value |
| --- | --- |
| Layer name | `{ICAO} Runway Holding Position Markings` |
| Geometry type | Polygon |
| Feature granularity | One polygon per Pattern A bar |
| Group | Specialised Runway Safeguarding or Physical Geometry |
| Style | Yellow fill with no outline |
| Attributes | `rwy`, `end_desig`, `mark_type`, `sub_type`, `side`, `stripe_no`, `len_m`, `wid_m`, `offset_m`, `spacing_m`, `mandatory`, `ref_mos`, `notes` |

### Implementation Notes

- Treat this as an interface-control marking family for LAHSO and runway/taxiway
  interaction modelling.
- Pattern selection is driven by the runway type and the number of runway
  holding positions required at the intersection.
- Placement uses Table 6.56(1) and the runway code/type pairing; the elevation
  modifier from note a is deferred for a later pass.
- The current builder implements Pattern A as four 0.3 m bars; the two bars
  closest to the intersecting runway are dashed using 0.9-1.0 m dash and gap
  lengths.
- LAHSO is modelled as a runway-end checkbox in the advanced runway data area.
- Pattern B remains a future enhancement.

### Open Questions

- Please provide MOS subsection 8.39(9).
- Confirm whether note a should be applied automatically from elevation data.
- Confirm whether Pattern B should be added for precision runway intersections
  in a later pass.
