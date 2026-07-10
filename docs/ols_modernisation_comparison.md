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
  - **Planar Transition / Equal Height** and **No Future OLS Overlay**.

OES layers are assessment-trigger comparisons, not development approval limits.
Every comparison output feature has a readable, layer-qualified `comparison_id`
(for example `OFS-GAIN-000001`) for reporting a specific test issue. Each change
feature also retains the baseline and future controlling surface identifiers,
surface types, ruleset identifier, sampled minimum and maximum change, and a
representative interior-point change. Gain/loss polygons are labelled with the
representative change value on larger map features. Areas outside the common
domains are not classified as gains or losses; baseline-only areas are shown
separately as **No Future OLS Overlay**.

The comparison requires:

- controlling OLS generation to be enabled;
- an existing ruleset selected as the baseline;
- an Aeroplane Design Group for every runway used by future Annex 14 generation;
- complete runway operational and elevation inputs needed by both rulesets.
