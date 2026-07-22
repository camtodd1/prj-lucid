# OLS Ruleset And Modernisation Comparison

**Status:** Current

**Last reviewed:** 22 July 2026

The OLS tab provides independent **Baseline OLS** and **Comparison OLS**
selectors. Choosing **None — baseline only** generates only the baseline.
Rulesets are selectable when their controlling-envelope capability is available;
incomplete rulesets remain visible but disabled.

The OLS tab keeps the shared contour defaults visible and places detailed
controls behind two disclosures. **Surface-specific overrides** repeats the
same two-column baseline/comparison layout, reports whether overrides are in
use, and only shows the surface families used by each selected ruleset.
**Comparison change contours** is shown whenever a comparison ruleset is
selected. Conventional OLS comparisons use one OLS signed-change interval.
Comparisons involving modernised Annex 14 instead expose the independent OFS
and OES signed-change intervals; OFS/OES controls are not shown for rulesets
where those families do not apply. The Reset action appears only after an
interval differs from its default. With no comparison selected, the comparison
column shows a baseline-only empty state.
Annex 14 exposes separate OES intervals for Precision Approach, Take-off Climb,
and Instrument Departure, plus separate OFS intervals for Approach,
Transitional, Balked Landing, Inner Approach, and Inner Transitional surfaces.
The previous family-wide OFS/OES values remain load-compatible fallbacks.
MOS139 contour controls mirror the generated layer groups: Obstacle Free Zone
(Inner Approach, Inner Transitional, Balked Landing), Primary Surfaces
(Approach, Take-off Climb, Transitional), and Secondary (Conical). Controlling
envelope contours continue to inherit their source-surface intervals.
In the generated layer tree, the selected baseline is grouped under
**Baseline OLS — [ruleset]**, alongside the optional **Comparison OLS —
[ruleset]** group. Obstacle Free Zone, Primary, Secondary, and Controlling
Surfaces sit inside the baseline group. OFZ layers are grouped by runway end
before the individual surface and contour layers.

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
Adjacent or disjoint parts are emitted as one (potentially multipart) feature
when their baseline surfaces are congruous, their comparison surfaces are
congruous, and their three-decimal minimum-to-maximum change ranges match.
Planar surfaces are congruous when their plane equations match. Conical
surfaces are congruous when their normalized base footprints, base elevations,
slopes, and maximum distances match.
Where such a dissolve spans multiple controller IDs, the relevant ID and
surface fields list the contributing values separated by semicolons. Collapsed
interior rings below the comparison minimum-area threshold are removed from the
dissolved geometry; material holes are preserved. Joined boundaries are snapped
to a one-micrometre grid and re-unioned when this removes a numerical seam
without materially changing the output area. Zero-area out-and-back segments
are removed from both exterior boundaries and retained material holes.
Areas outside the common domains are not classified as gains or losses;
baseline-only areas are shown separately as **No Comparison OLS Overlay**.

The 0.01 m numerical comparison tolerance applies when a complete
controller-pair region is effectively equivalent. It does not create a buffer
or polygon band around an equal-height transition. Where future and baseline
surfaces cross, gain and loss meet directly at the zero-height line; the line
itself is represented by the transition output and has no polygonal area.
Axis/conical controlling regions sample an extended overlap on a fixed,
globally aligned grid and project the resulting vertices onto the equality
curve before clipping it to either ruleset footprint. Separate envelopes with
the same surface models therefore use the same transition chords over their
common domain. Equality-contour seeding is independent of controller tie
ownership, and a selected transition curve is reused without a second
simplification when it partitions the overlap.

Change contours are generated from the same baseline/future elevation functions
and finalized controller-pair polygons used by the comparison. Affine candidate
pairs use exact isolines; curved pairs use a clipped triangulated approximation.
When an affine isoline lands on a controller transition, a 0.01 m clipping retry
rejoins fragments caused solely by small boundary-coordinate residuals.
Curved comparison contours can still appear patchy or truncated where a
conical baseline meets a controller transition or horizontal plane. This is a
known limitation tracked under
[Protected Airspace in the roadmap](roadmap.md#protected-airspace).
The zero contour is omitted because it is already represented by the separate
equal-height transition layer, and only primary contours are labelled to limit
map clutter. Each contour has a unique `comparison_id`, its
source polygon `parent_id`, signed `delta_m`, contour class and both controlling
surface identifiers.

### Comparison geometry invariants

The following invariants apply to every OLS ruleset comparison, not only
MOS139/Annex 14 modernisation comparisons:

- A gain polygon must not contain a material negative height difference, and a
  loss polygon must not contain a material positive height difference.
- A polygon that crosses zero must be split on the controller pair's
  equal-height locus. An interior `pointOnSurface()` sample can label a pure
  polygon, but must never classify an entire mixed-sign repair remainder.
- Coverage-repair and cleanup passes must use the same controller-pair solver as
  the initial partition. Each repaired area is added to the assigned coverage
  immediately so a numerical overlap cannot recover it again under another
  controller pair. A final sign and exclusivity audit runs after all local
  repairs so a late attachment cannot reintroduce an opposite-sign area,
  overlap, or contour.
- If common-domain recovery creates a numerical sliver, it may be reattached
  locally to one verified adjacent controller-pair polygon. This ruleset-agnostic
  rule is limited to recovery-tracked parts no more than 0.10 m wide whose
  interior lower-envelope samples and substantial shared boundary identify one
  unambiguous target. Provenance must cover the complete part; untracked, wider,
  mixed-controller, ambiguous and unrelated segments remain separate. This is
  not a class-wide dissolve.
- Gain and loss share the same zero-height edge. The transition output is this
  common boundary, not two independently sampled approximations.
- Opposite-sign contour levels are never emitted into a gain or loss feature.
  Millimetric residuals at the shared boundary are treated as zero and do not
  create a polygonal no-change strip.

Conical/conical transition and change-contour lines require a second, geometric
quality check. Triangulation can place an isoline accurately in height while
still producing a visibly oscillating path. The regulariser therefore accepts
a straight chord only when both its elevation residual and its displacement
from the sampled line are within bounds. If the chord is vertically accurate
but too distant, a fair fitted curve is tried instead. Any accepted line must
remain simple, inside the comparison domain, endpoint-compatible and within the
configured elevation-residual limit.

The YSSY three-runway mixed MOS139/CAP168 case is the regression example for
these rules. It exposed mixed-sign late repair polygons and a high-frequency
conical contour that was vertically close but visually jagged. After the final
sign split, it produces no material cross-zero polygons or wrong-sign contours.
The formerly irregular +46 m contour has a maximum local turn of about 0.28
degrees and a maximum height residual of about 0.017 m; the conical transition
has a maximum equality residual of about 0.004 m in EPSG:32756.

Comparison mode exposes a conventional OLS signed-change interval, or
independent OFS and OES intervals when modernised Annex 14 is involved. The
intermediate interval controls generated isoline spacing and the primary
interval controls contour classification and labelling. Both default to 1.0 m
intermediate and 5.0 m primary values, are persisted with the input file, and
are written to each change-contour feature.

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
- YSSY three-runway mixed inputs.

The QGIS 4.0.2 end-to-end runner validates geometry, candidate and controlling
coverage, comparison-domain coverage, mutually exclusive change classes,
comparison IDs, and staged runtime. The 11 July run passed all four cases with
no invalid or empty geometry and no duplicate comparison IDs. The accompanying
unit suite passed 110 tests.

Remaining work is targeted internal hardening rather than a calculation rewrite:
OLS-tab clarity, phase-based progress/cancellation, regulatory-scope
documentation, and the promoted-versus-diagnostic layer contract. Performance
comparisons are optional diagnostics rather than release gates.

## Comparison-refactor baseline — 22 July 2026

The invariant-audit slice established a one-run QGIS 4.0 checkpoint before the
comparison repair pipeline is consolidated. Counts are gain/loss/no-change/
transition; boundary components measure the complete gain/loss adjacency and
zero components measure the verified published zero contour.

| Fixture/family | Runtime | Features | Common domain | Unclassified | Boundary/zero components | Recovery parts | Invariants |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| YBBN/OFS | 17.93 s fixture | 25/0/0/0 | 8,981,676.99 m2 | 0.0002 m2 | 0/0 | 4 | pass |
| YBBN/OES | 17.93 s fixture | 33/59/2/12 | 471,236,515.02 m2 | 716.4341 m2 | 475/30 | 26 | fail: coverage and transition adjacency |
| YMML/OFS | 25.60 s fixture | 73/15/0/8 | 18,172,243.18 m2 | 0.0022 m2 | 18/15 | 16 | fail: transition adjacency |
| YMML/OES | 25.60 s fixture | 62/176/5/18 | 536,044,732.51 m2 | 0.0028 m2 | 1083/32 | 36 | fail: transition adjacency |

All four partitions had zero material class overlap, zero height-sign
violations, and zero invalid or empty comparison parts. The YBBN/OES coverage
gap and transition lines that no longer coincide with final gain/loss adjacency
are now explicit pre-refactor failures; they are not repaired by the audit.
