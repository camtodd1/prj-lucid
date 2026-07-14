# OLS Ruleset And Modernisation Comparison

The OLS tab provides independent **Baseline OLS** and **Comparison OLS**
selectors. Choosing **None — baseline only** generates only the baseline.
Rulesets are selectable when their controlling-envelope capability is available;
incomplete rulesets remain visible but disabled.

The OLS tab keeps the shared contour defaults visible and places detailed
controls behind two disclosures. **Surface-specific overrides** repeats the
same two-column baseline/comparison layout, reports whether overrides are in
use, and only shows the surface families used by each selected ruleset.
**Comparison change contours** is shown when an Annex 14 comparison is active
and contains the independent OFS/OES signed-change intervals. The Reset action
appears only after an interval differs from its default. With no comparison
selected, the comparison column shows a baseline-only empty state.
Annex 14 exposes separate OES intervals for Precision Approach, Take-off Climb,
and Instrument Departure, plus separate OFS intervals for Approach,
Transitional, Balked Landing, Inner Approach, and Inner Transitional surfaces.
The previous family-wide OFS/OES values remain load-compatible fallbacks.
MOS139 contour controls mirror the generated layer groups: Obstacle Free Zone
(Inner Approach, Inner Transitional, Balked Landing), Primary Surfaces
(Approach, Take-off Climb, Transitional), and Secondary (Conical). Controlling
envelope contours continue to inherit their source-surface intervals.

The comparison engine solves both selected envelopes and calculates:

`delta height = comparison elevation - baseline elevation`

The selected direction is significant: reversing the two rulesets reverses the
sign of gain and loss outputs. Conventional OLS rulesets share one comparison
family. When modernised ICAO Annex 14 is on either side, the conventional OLS
envelope is compared independently with the Annex 14 OFS and OES families.

The established **OLS modernisation comparison** is the pairing of an existing
OLS baseline with the modernised ICAO Annex 14 OFS/OES model applicable from
21 November 2030. For this pairing:

The calculation compares the two controlling lower envelopes point by point:

`delta height = future Annex 14 elevation - baseline elevation`

Outputs are grouped as follows:

- **OFS — Protected Airspace Change**
  - **Baseline OLS Wireframe**: outline-only baseline controlling envelope.
  - **Future Annex 14 Wireframe**: dashed outline-only future Annex 14 controlling envelope.
  - **Height Gain** (green): future OFS is higher than the baseline OLS.
  - **Height Loss** (red): future OFS is lower than the baseline OLS.
  - **No Height Change** (neutral): future OFS and baseline OLS are effectively equal.
  - **Change Contours**: signed `future - baseline` isolines at 1.0 m intervals,
    with primary contours every 5.0 m. Positive values indicate gain and negative
    values indicate loss.
  - **Planar Transition / Equal Height** (dashed): approximate breakline where
    the two controlling elevations are equal.
  - **No Comparison OLS Overlay** (grey): baseline controlling OLS area with no
    overlapping future Annex 14 comparison surface.
- **OES — Assessment Trigger Change**
  - **Baseline OLS Wireframe** and **Future Annex 14 Wireframe**.
  - **Trigger Height Raised** (green): the future aeronautical-study trigger is
    higher than the baseline OLS.
  - **Trigger Height Lowered** (red): the future aeronautical-study trigger is
    lower than the baseline OLS.
  - **Trigger Height Unchanged** (neutral): the future aeronautical-study trigger
    is effectively equal to the baseline OLS.
  - **Change Contours**, **Planar Transition / Equal Height**, and
    **No Comparison OLS Overlay**.

OES layers are assessment-trigger comparisons, not development approval limits.
Every comparison output feature has a readable, layer-qualified `comparison_id`
(for example `OFS-GAIN-000001`) for reporting a specific test issue. Each change
feature also retains the baseline and comparison ruleset identifiers, both
controlling surface identifiers and types, sampled minimum and maximum change,
and the interior classification sample as `delta_sample_m`. Generic
`comparison_*` fields accompany the legacy `future_*` fields. The interior
sample is not an average or representative value. Gain/loss polygons are
labelled with their minimum-to-maximum change range on larger map features.
Areas outside the common domains are not classified as gains or losses;
baseline-only areas are shown separately as **No Comparison OLS Overlay**.

The 0.01 m numerical comparison tolerance applies when a complete
controller-pair region is effectively equivalent. It does not create a buffer
or polygon band around an equal-height transition. Where future and baseline
surfaces cross, gain and loss meet directly at the zero-height line; the line
itself is represented by the transition output and has no polygonal area.

Change contours are generated from the same baseline/future elevation functions
and finalized controller-pair polygons used by the comparison. Affine candidate
pairs use exact isolines; curved pairs use a clipped triangulated approximation.
The zero contour is omitted because it is already represented by the separate
equal-height transition layer, and only primary contours are labelled to limit
map clutter. Each contour has a unique `comparison_id`, its
source polygon `parent_id`, signed `delta_m`, contour class and both controlling
surface identifiers.

Comparison mode exposes independent OFS and OES signed-change contour intervals
on the OLS tab. The intermediate interval controls generated isoline spacing and
the primary interval controls contour classification and labelling. Both default
to 1.0 m intermediate and 5.0 m primary values, are persisted
with the input file, and are written to each change-contour feature.

Primary/intermediate interval compatibility validation is intentionally not
implemented or tested and is accepted as a supported limitation. Contour levels
are generated on the selected intermediate interval; a generated level is
classified as primary only when it is also an exact multiple of the selected
primary interval. The dialog does not require the primary interval to be an
integer multiple of the intermediate interval.

The comparison requires:

- different baseline and comparison rulesets, unless baseline-only is selected;
- an available controlling-envelope capability for each selected ruleset;
- an Aeroplane Design Group for every runway used by future Annex 14 generation;
- complete runway operational and elevation inputs needed by both rulesets.

Saved inputs now persist `baseline_ols_ruleset` and
`comparison_ols_ruleset`. The earlier `protected_airspace_policy` values are
still loaded and mapped onto the equivalent selector pair.

## Stability checkpoint — 11 July 2026

The calculation and output workflow is considered mostly stable for continued
product work. The current regression matrix contains:

- YBBN single-runway;
- YSSY dual intersecting;
- YSWS dual parallel; and
- YSSY three-runway stress inputs.

The QGIS 4.0.2 end-to-end runner validates geometry, candidate and controlling
coverage, comparison-domain coverage, mutually exclusive change classes,
comparison IDs, and staged runtime. The 11 July run passed all four cases with
no invalid or empty geometry and no duplicate comparison IDs. The accompanying
unit suite passed 110 tests.

Remaining work is primarily productisation rather than a calculation rewrite:
OLS-tab clarity, phase-based progress/cancellation, release performance gates,
regulatory-scope documentation, and the promoted-versus-diagnostic layer
contract.
