# OLS Modernisation Comparison

The **OLS modernisation comparison** protected-airspace policy keeps the selected
design ruleset as the baseline and additionally generates the modernised ICAO
Annex 14 OFS/OES model applicable from 21 November 2030.

The calculation compares the two controlling lower envelopes point by point:

`delta height = future Annex 14 elevation - baseline elevation`

Outputs are grouped as follows:

- **OFS — Protected Airspace Change**
  - **Baseline OLS Wireframe**: outline-only baseline controlling envelope.
  - **Future Annex 14 Wireframe**: dashed outline-only future Annex 14 controlling envelope.
  - **Height Gain** (green): future OFS is higher than the baseline OLS.
  - **Height Loss** (red): future OFS is lower than the baseline OLS.
  - **No Height Change** (neutral): future OFS and baseline OLS are effectively equal.
  - **Change Contours**: signed `future - baseline` isolines at 0.5 m intervals,
    with primary contours every 1.0 m. Positive values indicate gain and negative
    values indicate loss.
  - **Planar Transition / Equal Height** (dashed): approximate breakline where
    the two controlling elevations are equal.
  - **No Future OLS Overlay** (grey): baseline controlling OLS area with no
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
    **No Future OLS Overlay**.

OES layers are assessment-trigger comparisons, not development approval limits.
Every comparison output feature has a readable, layer-qualified `comparison_id`
(for example `OFS-GAIN-000001`) for reporting a specific test issue. Each change
feature also retains the baseline and future controlling surface identifiers,
surface types, ruleset identifier, sampled minimum and maximum change, and the
interior classification sample as `delta_sample_m`. The interior sample is not
an average or representative value. Gain/loss polygons are labelled with their
minimum-to-maximum change range on larger map features. Areas outside the common
domains are not classified as gains or losses; baseline-only areas are shown
separately as **No Future OLS Overlay**.

Change contours are generated from the same baseline/future elevation functions
and finalized controller-pair polygons used by the comparison. Affine candidate
pairs use exact isolines; curved pairs use a clipped triangulated approximation.
The zero contour is omitted because it is already represented by the separate
equal-height transition layer, and only primary contours are labelled to limit
map clutter. Each contour has a unique `comparison_id`, its
source polygon `parent_id`, signed `delta_m`, contour class and both controlling
surface identifiers.

The comparison requires:

- controlling OLS generation to be enabled;
- an existing ruleset selected as the baseline;
- an Aeroplane Design Group for every runway used by future Annex 14 generation;
- complete runway operational and elevation inputs needed by both rulesets.
