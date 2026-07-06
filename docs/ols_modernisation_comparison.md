# OLS Modernisation Comparison

The **OLS modernisation comparison** protected-airspace policy keeps the selected
design ruleset as the baseline and additionally generates the modernised ICAO
Annex 14 OFS/OES model applicable from 21 November 2030.

The calculation compares the two controlling lower envelopes point by point:

`delta height = future Annex 14 elevation - baseline elevation`

Outputs are grouped as follows:

- **OFS — Protected Airspace Change**
  - **Height Gain** (green): future OFS is higher than the baseline OLS.
  - **Height Loss** (red): future OFS is lower than the baseline OLS.
- **OES — Assessment Trigger Change**
  - **Trigger Height Raised** (green): the future aeronautical-study trigger is
    higher than the baseline OLS.
  - **Trigger Height Lowered** (red): the future aeronautical-study trigger is
    lower than the baseline OLS.

OES layers are assessment-trigger comparisons, not development approval limits.
Each feature retains the baseline and future controlling surface identifiers,
surface types, ruleset identifier, sampled minimum and maximum change, and a
representative interior-point change. Areas outside the common domains are not classified
as gains or losses.

The comparison requires:

- controlling OLS generation to be enabled;
- an existing ruleset selected as the baseline;
- an Aeroplane Design Group for every runway used by future Annex 14 generation;
- complete runway operational and elevation inputs needed by both rulesets.
