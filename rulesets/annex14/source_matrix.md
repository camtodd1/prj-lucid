# Annex 14 Source Matrix

Use this matrix to track source capture before promoting capabilities from
`scaffold` or `unsupported`.

| Area | Module | Status | Notes |
| --- | --- | --- | --- |
| Runway type mapping | `classification.py` | scaffolded | Existing app type labels map to NI/NPA/PA codes. |
| Reference code / design group | `classification.py` | partial | Table 1-1 and Table 1-2 captured; broader integration with runway data and OES still pending. |
| Physical characteristics | `physical_data.py` | pending | Runway, strip, RESA, shoulder, taxiway, and declared-area tables. |
| Taxiway and separations | `taxiway.py` | pending | Include taxiway and parallel runway separation standards. |
| OLS | `ols_surfaces.py` | pending | Airport-wide, approach, take-off climb, transitional, and OFZ families. |
| OES | `oes.py` | pending | Define evaluation surfaces and ADG-derived variants where applicable. |
| Markings | `markings.py` | pending | Runway marking dimensions, offsets, and applicability. |
| Lighting | `lighting.py` | pending | Runway, threshold, end, centreline, approach, and displaced threshold lighting. |
