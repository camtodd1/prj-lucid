# Airfield Ground Lighting Rules and Assumptions

Source: local extract `CASA Part 139 Aerodromes - Runway Lights Standards.pdf`, Part 139 (Aerodromes) Manual of Standards 2019, Chapter 9, Division 10, sections 9.51 to 9.73. The extract identifies Compilation No. 7, compilation date 12 May 2026.

This document is an implementation reference for the Safeguarding Builder AGL layer. It summarises provision triggers, layout rules, display colours, and modelling assumptions. It is not a substitute for the MOS.

## General Builder Assumptions

- AGL generation is optional and controlled from the Lighting UI.
- The builder models light locations and plan-view display characteristics. It does not validate photometric intensity, vertical beam distribution, circuiting, power supply, control, monitoring, or serviceability requirements.
- Where the MOS depends on operational intent that is not available in the runway geometry, the builder uses explicit user options rather than inferring intent. Examples include night use, RVR below 350 m, LAHSO, and optional CAT I lighting enhancements.
- For runway edge-light triggers, if either runway end type is `Non-Instrument`, `Non-Precision`, or `Precision Approach`, the builder assumes the runway is intended for night use.
- Blank or unsupported runway type values do not fall back to a default AGL standard. Type-dependent AGL features are not generated for unsupported runway ends. Shared runway features use the supported end types only; if neither end has a supported type, type-dependent AGL features are skipped.
- Point symbols are used for light fittings. Each feature records `beam_type` and `style_key` so symbology can distinguish omnidirectional, unidirectional, and bidirectional fittings without inferring from colour alone.
- Omnidirectional lights are drawn as plain circular markers. Unidirectional lights are drawn as circular markers with prongs facing the observable direction. Bidirectional or dual-display lights are modelled as split circular markers with prongs on the observable axis, using `colour_p`, `colour_r`, and `symbol_ang` fields. QGIS renderer rotation is applied after the QML style is loaded.
- Coincident lights are resolved before the AGL layer is written. Current assumptions:
  - Stopway end lights override stopway edge lights at the same point.
  - Threshold plus runway end lights at the same point are represented as one split green/red marker.
  - Otherwise, coincident lights are reduced by a fixed priority order to avoid unreadable overplotting.
- Unless otherwise stated, lateral placement is generated relative to the runway centreline and current runway width, with runway edge light rows using at least a 30 m effective lit width where required.

## Precision Approach CAT II/III Approach Lighting

MOS reference: 9.42.

### Triggers

- A precision approach CAT II or CAT III lighting system must be provided for a precision approach CAT II or CAT III runway.
- Where a precision approach CAT II or CAT III lighting system is provided, runway TDZ lights must also be provided.

### Layout Requirements

- The approach lighting system must include a row of lights on the extended runway centreline extending at least to Point B, 300 m from threshold.
- The system must include 2 side rows of lights between the threshold and Point B.
- The system must include crossbars at Point A, 150 m from threshold, and Point B, 300 m from threshold.
- Centreline lights must be at equal longitudinal intervals between threshold and crossbars, or between crossbars, as close as possible to 30 m and within the MOS tolerance.
- Side row lights must be:
  - on each side of the centreline;
  - longitudinally aligned with the centreline lights;
  - at the same longitudinal spacing as the centreline lights; and
  - laterally spaced so the innermost side-row lights are not less than 18 m and not more than 22.5 m apart.
- The Point A crossbar must fill the gaps between the centreline and side row lights.
- The Point B crossbar must extend on both sides of the centreline lights to 15 m from the centreline.
- Where centreline lights continue beyond Point B using the distance-coded pattern, additional crossbars must be provided at Points C, D and E where those points are within the system length.
- Additional crossbar outer ends must lie on straight lines converging to the runway centreline 300 m from threshold.
- Object screening and horizontal plane requirements apply but are not modelled geometrically by the builder.

### Characteristics

- From threshold to Point B, centreline light positions consist of barrettes showing variable white.
- Beyond Point B, the builder uses the MOS distance-coded centreline option:
  - 2 variable-white light sources from Point B to Point D; and
  - 3 variable-white light sources beyond Point D.
- Centreline barrettes must be at least 4 m long. If composed of point-source lights, those lights must be uniformly spaced at intervals not exceeding 1.5 m.
- Each side row light position consists of a red barrette, with length and light spacing equal to the TDZ barrettes.
- Crossbar lights are fixed variable-white lights, uniformly spaced at intervals not exceeding 2.7 m.

### Builder Assumptions

- Generated for precision approach CAT II/III ends through the per-end approach lighting configuration.
- The base generated CAT II/III system is 900 m long unless a user approach-length override is entered.
- Centreline positions use 30 m spacing from threshold outward, subject to any user spacing override.
- Centreline barrettes from threshold to Point B are represented by 4 point light units spaced 1.5 m apart, giving a 4.5 m barrette span.
- Side row barrettes use the TDZ barrette pattern: 3 red light units at 1.5 m spacing, with innermost lights at 9 m each side of centreline.
- Point A and Point B crossbars are generated as variable-white point lights at intervals not exceeding 2.7 m, avoiding the central centreline barrette gap.
- Points C, D and E are generated when included within the selected approach length. Their half-widths are derived from the MOS convergence rule, using 300 m from threshold as the convergence point.
- The builder uses the distance-coded centreline option beyond Point B. The alternative continuing-barrette centreline and associated sequenced flashing lights are not generated.
- The less-than-420 m CAT II concession, displaced-threshold single-source concession, object-screening checks, photometric intensity, circuiting, and independent flasher operation are not modelled.

## Runway Edge Lights

MOS references: 9.51, 9.52, 9.53, 9.63.

### Triggers

- Required for a non-instrument or non-precision runway intended for night use.
- Required for a precision approach runway intended for day or night use.
- A runway intended for night visual circling, circuits, or both requires omnidirectional edge lights meeting the non-instrument/non-precision characteristics.
- A runway available for take-off operations with RVR below 350 m requires edge lights meeting the precision-style characteristics.

### Layout Requirements

- Place lights in two parallel straight rows, equidistant from the runway centreline, with opposite pairs aligned.
- For non-instrument and non-precision runways, rows normally run from threshold to opposite runway end.
- If threshold-position edge lights are replaced by the optional omnidirectional threshold light pattern, edge lights commence one light space in from the threshold and finish one light space from the opposite runway end.
- For precision approach runways, edge lights commence one light space in from the threshold and continue to one light space from the opposite runway end.
- Longitudinal spacing:
  - Instrument runway: 60 m, tolerance +0 m / -5 m.
  - Non-instrument runway: 90 m +/- 10 m.
- Intersection omissions or irregular spacing are allowed for non-instrument and non-precision runways only, subject to MOS constraints. Precision approach runway edge lights must not be omitted.
- At runway or taxiway intersections on non-instrument and non-precision runways, runway edge lights may be irregularly spaced or omitted if no 2 consecutive lights are omitted and visual guidance is not significantly altered.
- If a runway edge light cannot be omitted at an intersection, an inset runway edge light must replace the elevated light.
- Edge rows should be along the declared runway edges or no more than 3 m outside them.
- Runways less than 30 m wide are treated as 30 m wide for edge-light placement.

### Characteristics

- Non-instrument and non-precision edge lights are fixed, omnidirectional, and variable white.
- Precision approach edge lights are fixed, unidirectional, with the main beam directed towards the threshold.
- Precision approach edge lights show variable white except lights within 600 m of the runway end, which show yellow.
- Edge lights before a displaced threshold, where the pre-threshold runway remains available for aircraft use, show red toward the displaced threshold and white, yellow as appropriate, or blue in the opposite direction depending on the runway context.

### Builder Assumptions

- The builder uses `variable white` for ordinary runway edge lights and split directional markers for directional edge display.
- Runway edge light spacing and shared row placement use the higher runway standard across the runway. If either end is instrument/precision, 60 m spacing applies to both edge rows. If both ends are non-instrument, 90 m spacing applies. If either end is precision approach, the shared edge rows use the precision one-light-space inset from both physical ends.
- RVR below 350 m remains an optional Lighting UI input and does not otherwise override runway edge spacing or placement while RVR design data is not captured separately.
- Directional edge displays are stored as primary and reciprocal colours. Current split combinations include white/yellow, yellow/white, red/white, white/red, red/yellow, and yellow/red.
- The 600 m yellow end-zone display is assessed per landing direction. It applies to the direction whose runway end is a precision approach runway, or to both directions when the runway is marked for RVR below 350 m operations in the Lighting UI.
- Where yellow end-zone display applies, it is modelled as a directional split where one side faces the landing threshold direction and the opposite side remains white unless another rule applies.
- Intersecting runway omissions are modelled where both runway geometries are available. Edge lights on non-instrument and non-precision runways are omitted where they fall within another runway footprint, provided the omission does not remove 2 consecutive lights on the same side.
- Taxiway intersection geometry is not recorded in the AGL inputs. Taxiway-related omissions, irregular spacing remarks, inset replacement at intersections, and related compliance checks are not modelled or coded.
- Circling guidance light rows and toe-in angle are not modelled.

## Runway Threshold Lights

MOS references: 9.54, 9.55, 9.56, 9.57, 9.58.

### Triggers

- Required where runway edge lights are provided.

### Layout Requirements

- Located in a straight line at right angles to the runway centreline.
- If the threshold is at the runway extremity, locate as close as possible to the extremity and within the MOS tolerance.
- If the threshold is displaced, locate at the displaced threshold within +/- 1 m.
- Non-instrument and non-precision threshold lights must comprise at least 6 equally spaced unidirectional lights.
- For a precision approach runway, threshold lights are equally spaced at intervals not exceeding 3 m across the runway width.
- Optional non-instrument/non-precision conspicuity pattern may replace threshold-aligned edge lights with omnidirectional green threshold lights on each edge.

### Characteristics

- Non-instrument and non-precision threshold lights are fixed, unidirectional, and show green in the direction of approach.
- Precision approach threshold lights are fixed and show green in the direction of approach.
- Non-instrument and non-precision threshold lights must be inset if the threshold is permanently displaced or elevated lights cannot be installed.
- For runways with a starter extension, inset threshold lights may align with reciprocal runway end fittings.

### Builder Assumptions

- Threshold lights are generated at the relevant threshold line with green display in the approach direction.
- Where runway end lights coincide with threshold lights, the builder merges them into one split green/red marker.
- The optional omnidirectional threshold edge replacement pattern is not separately modelled unless represented by user-selected threshold lighting behaviour.

## Threshold Wing Bars

MOS reference: 9.59.

### Triggers

- Optional on a precision approach runway to increase threshold conspicuity for night operations.

### Layout Requirements

- Wing bars are symmetrically disposed on either side of the threshold.
- Each wing bar is at right angles to the runway centreline.
- Each wing bar consists of 5 lights spaced 2.5 m apart.
- The innermost light aligns with the row of runway edge lights on the corresponding side.

### Characteristics

- Fixed, unidirectional, elevated unless alignment constraints require otherwise.
- Show green in the direction of approach.

### Builder Assumptions

- Generated only when the Lighting UI option is enabled and the runway type is precision approach.
- Photometric intensity and elevation constraints are not checked.

## Runway Threshold Identification Lights (RTIL)

MOS reference: 9.59.

### Triggers

- Used where the threshold is difficult to locate from the air during the day.
- Must be used with specified temporarily displaced threshold markings for some temporary displacement cases.
- May be used by day or night in other cases.

### Layout Requirements

- One light unit on each side of the runway, equidistant from the centreline, on a line perpendicular to the centreline.
- Normally located 12 m to 15 m outside each runway edge light row and in line with the threshold.
- If impracticable, may be located laterally up to 20 m from the edge light row and longitudinally up to 12 m before the threshold.
- Each unit must be at least 12 m from runway and taxiway edges.

### Characteristics

- Flashing white.
- Synchronized flashes, normally 100 to 120 flashes per minute.
- Beam axis aimed outward from a line parallel to the runway centreline and inclined above horizontal.

### Builder Assumptions

- RTIL are generated when the user enables the option and a displaced-threshold condition exists.
- The builder uses a default 12 m lateral offset beyond the edge light row.
- Flash synchronization, intensity, aiming, and elevation are not modelled.

## Temporarily Displaced Threshold Lights

MOS references: 9.60, 9.61, 9.62.

### Triggers

- Required at night if a runway threshold is temporarily displaced.

### Layout Requirements

- Provided on each side of the runway.
- Located in line with the displaced threshold, at right angles to the runway centreline.
- Innermost light on each side aligns with the corresponding runway edge light row.
- Each side array normally has 5 lights. For runways 30 m wide or less, each side may use 3 lights.
- Lights are spaced 2.5 m apart.

### Characteristics

- Outer lights are fixed, unidirectional, and green in the approach direction.
- For visual circling or circuit operations, the innermost light of each side array may be fixed omnidirectional green.
- Intensity is intended to be close to 1.5 times runway edge lights, and not less than runway edge lights.

### Builder Assumptions

- Generated when the temporary displaced threshold option is enabled and a displacement value exists.
- The builder uses 5 lights per side, or 3 lights per side for runways 30 m wide or less.
- The innermost omnidirectional option is not separately styled at present.

## Runway Lighting Before a Displaced Threshold

MOS reference: 9.63.

### Triggers

- Applies where the runway area before a displaced threshold remains available for aircraft use.

### Requirements

- Edge lights in the pre-threshold area show red toward the displaced threshold.
- In the opposite direction, they show white, yellow for precision approach where appropriate, or blue for relevant starter extension cases.
- If the pre-threshold portion is closed to aircraft operations, runway lights on that portion are extinguished.

### Builder Assumptions

- The builder models available pre-threshold edge lighting as split directional edge markers where applicable.
- The displaced-threshold length input is interpreted as runway pavement before the displaced threshold that remains available for aircraft use, consistent with take-off use and landing from the opposite direction.
- The separate pre-threshold area input is treated as stopway by default in the declared-distance workflow and does not trigger section 9.63 runway edge-light treatment.
- Starter-extension classification is not currently captured, so the blue opposite-direction starter-extension case is not generated.
- Closed pre-threshold areas are not inferred automatically. Explicit closed-area input support is tracked in `docs/TODO.md`.

## Runway End Lights

MOS references: 9.64, 9.65, 9.66.

### Triggers

- Required for a runway with runway edge lights.

### Layout Requirements

- Located in a straight line at right angles to the runway centreline.
- If the runway end is at the extremity, locate as close as possible to the extremity within the MOS tolerance.
- If the runway end is not at the extremity, locate at the runway end within +/- 1 m.
- Normally at least 6 lights, equally spaced between the runway edge light rows.
- If an alternative threshold pattern is used, runway end lights may use that threshold pattern.
- For precision approach CAT III, runway end light spacing must not exceed 6 m.
- Starter extension rules include a passing gap and separate blue edge lighting beyond the declared end.

### Characteristics

- Non-instrument and non-precision end lights are fixed, unidirectional, and red in the direction of the runway.
- Precision approach runway end lights are inset, fixed, unidirectional, and red in the direction of the runway.
- Where runway end coincides with runway threshold, the MOS allows bidirectional fittings or back-to-back separate fittings.

### Builder Assumptions

- Runway end lights are generated where enabled and shown red toward the runway.
- Coincident runway end and threshold lights are merged into one split green/red marker.
- Starter extension pass-through gap logic and blue starter-extension end lighting are not fully modelled.

## Runway Turn Pad, Runway Bypass Pad, and Starter Extension Edge Lights

MOS reference: 9.67.

### Triggers

- Required where an aircraft turn pad, runway bypass pad, or runway starter extension is provided on a runway with edge lights.

### Layout Requirements

- Blue edge lights mark the edge of the relevant pad or starter extension.
- Located 0.6 m to 1.8 m outside the relevant edge.
- If the start of a splay is more than 10 m from the previous runway edge light, provide a blue light where the pad or extension commences.
- Mark changes of direction along the side of the pad.
- If a side is longer than 30 m, provide equally spaced blue lights with spacing not exceeding 30 m.

### Characteristics

- Characteristics follow taxiway edge light requirements under MOS section 9.93.

### Builder Assumptions

- Not currently generated as part of runway AGL. Pad, bypass, and starter-extension geometry support is tracked in `docs/TODO.md`.

## Stopway Lights

MOS reference: 9.68.

### Triggers

- Required on a stopway longer than 180 m that is intended for night use.

### Layout Requirements

- Located along both sides of the stopway, in line with runway edge lights, up to the stopway end.
- Spacing is uniform and not greater than runway edge light spacing.
- The last pair of side lights is located at the stopway end.
- Stopway end is further marked by at least 2 stopway lights equally spaced across the stopway end between the last side pair.

### Characteristics

- Fixed, unidirectional, red in the direction of the runway.
- Not visible to a pilot approaching to land over the stopway.

### Builder Assumptions

- Generated when stopway lighting is enabled and stopway length is present.
- A pre-threshold area is treated as a stopway by default in the input workflow.
- Stopway end lights override stopway edge lights where they occupy the same point.
- Visibility shielding from the approach over the stopway is not modelled.

## Hold Short Lights

MOS reference: 9.69.

### Triggers

- Required for a runway intended to accommodate LAHSO.

### Layout Requirements

- At least 6 inset lights.
- Located across the runway as near as possible to the hold short line.
- Not beyond the hold short line and not more than 3 m before it.
- At least 75 m from the centreline of the intersecting runway.
- At right angles to the runway and symmetrical about the centreline.
- Closest lights are offset 1.5 m each side of centreline, with subsequent lights spaced at 3 m.

### Characteristics

- Unidirectional, white in the direction of approach to the hold short position.
- Flash in unison at 25 to 35 flashes per minute, with approximately two-thirds illuminated and one-third suppressed per cycle.
- ATC control, intensity, monitoring, and secondary power requirements apply.

### Builder Assumptions

- Not currently generated.
- LAHSO-specific input, hold-short line location, and intersecting runway context are tracked in `docs/TODO.md`.

## Runway Centreline Lights

MOS reference: 9.70.

### Triggers

- Required on precision approach CAT II or CAT III runways.
- Required for runways intended for take-offs with operating minimum below RVR 350 m.
- Recommended for precision approach CAT I and some take-off runways if the width between runway edge lights exceeds 50 m.

### Layout Requirements

- Located from threshold to runway end.
- Longitudinal spacing:
  - Approximately 15 m for RVR conditions below 350 m.
  - Approximately 30 m for RVR conditions of 350 m or greater.
- May be offset by not more than 0.6 m from true runway centreline.
- Offset should be on the left side of the landing aircraft, or for bidirectional runways on the left side from the direction of the majority of landings.

### Characteristics

- Inset, fixed lights.
- White from threshold to 900 m from runway end.
- From 900 m to 300 m from runway end, pattern is two red lights followed by two white lights.
- Last 300 m before runway end shows red.

### Builder Assumptions

- Generated for required CAT II/III and RVR below 350 m cases, and optionally for recommended CAT I cases.
- Spacing is selected from the low-visibility UI option.
- Directional colour zoning is modelled for both runway directions using split markers.
- The 2-red/2-white sequence is generated per direction using the light sequence index.

## Simple TDZ Lights

MOS reference: 9.71.

### Triggers

- Optional. CASA notes their purpose as situational awareness and overrun risk mitigation.

### Layout Requirements

- If provided, comprise two pairs of lights, with one pair on each side of the runway centreline.
- Located 0.3 m beyond the upwind edge of the final TDZ marking.
- Inner-light lateral spacing equals the selected TDZ marking lateral spacing.
- Spacing within each pair is not more than the greater of 1.5 m or half the width of the TDZ marking.
- If there are no TDZ markings, locate to provide equivalent TDZ information.

### Characteristics

- Fixed, unidirectional, white or variable white.
- Aligned to be visible to the landing pilot in the direction of approach.

### Builder Assumptions

- Not currently generated as a separate simple TDZ light system.
- Requires final TDZ marking context and an explicit user option.

## Runway TDZ Lights

MOS reference: 9.72.

### Triggers

- Required for precision approach CAT II or CAT III operations.
- May be provided for a precision approach CAT I lighting system.

### Layout Requirements

- Series of transverse rows or barrettes symmetrically located on both sides of runway centreline.
- Extent is the lesser of:
  - 900 m from threshold; or
  - the overall length of TDZ markings under section 8.24.
- Each barrette has 3 light units spaced 1.5 m apart.
- Innermost light of each barrette is 9 m from true runway centreline.
- First pair of barrettes is 60 m from threshold.
- Subsequent barrettes are spaced 60 m longitudinally.

### Characteristics

- Inset, fixed, unidirectional, variable white.

### Builder Assumptions

- Generated for CAT II/III when enabled and optionally for CAT I via UI.
- TDZ lighting extent is aligned to generated TDZ marking extent where marking metadata is available.
- If marking metadata is unavailable, the builder estimates the MOS 8.24 TDZ marking extent from declared LDA and marking rules.

## Photometric Characteristics

MOS reference: 9.73 and Figures 9.75.

### Requirements

- MOS figures and tables define intensity and calculation methods for runway lights.
- Some sections cross-reference different Figure 9.75 photometric curves by light type, runway width, spacing, and approach category.

### Builder Assumptions

- The builder records layout and display characteristics only.
- Photometric compliance is out of scope for generated geometry and symbology.
- Future work could add report fields or QA warnings for light type, intensity class, and figure/table references, but it should not imply photometric certification.
