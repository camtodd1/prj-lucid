# Annex 14 Source Matrix

Use this matrix to track source capture before promoting capabilities from
`scaffold` or `unsupported`.

| Area | Module | Status | Notes |
| --- | --- | --- | --- |
| Runway type mapping | `classification.py` | scaffolded | Existing app type labels map to NI/NPA/PA codes. |
| Reference code / design group | `classification.py` | partial | Table 1-1 and Table 1-2 captured; geometry builder can use explicit ADG, critical aircraft data, or a code-letter proxy. |
| Physical characteristics | `physical_data.py` | pending | Runway, strip, RESA, shoulder, taxiway, and declared-area tables. |
| Taxiway and separations | `taxiway.py` | pending | Include taxiway and parallel runway separation standards. |
| OFS | `ols_surfaces.py`, `surfaces/annex14_geometry.py` | partial | Chapter 4 OFS captured. First-pass geometry covers approach, inner approach, and balked landing; transitional and inner transitional construction still pending. |
| OLS | `ols_surfaces.py`, `surfaces/annex14_geometry.py` | partial | Annex 14 OFS captured and partly generated; remaining complex OFS construction pending. |
| OES | `oes.py`, `surfaces/annex14_geometry.py` | partial | Horizontal, straight-in instrument, precision approach, instrument departure, and take-off climb parameters captured and first-pass plan geometry generated. TODA/clearway refinements pending. |
| Obstacle limitation requirements | `obstacle_requirements.py` | captured | Section 4.4 captured as penetration/exception/aeronautical-study policy; no geometry parameters. |
| Surface establishment requirements | `obstacle_requirements.py` | captured | Section 4.5 captured as OFS by runway use and OES by operation; no geometry parameters. |
| Markings | `markings.py` | pending | Runway marking dimensions, offsets, and applicability. |
| Lighting | `lighting.py` | pending | Runway, threshold, end, centreline, approach, and displaced threshold lighting. |
