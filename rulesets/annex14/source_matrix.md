# Annex 14 Source Matrix

Use this matrix to track source capture before promoting capabilities from
`scaffold` or `unsupported`.

| Area | Module | Status | Notes |
| --- | --- | --- | --- |
| Runway type mapping | `classification.py` | scaffolded | Existing app type labels map to NI/NPA/PA codes. |
| Reference code / design group | `classification.py` | partial | Table 1-1 and Table 1-2 captured; broader integration with runway data and OES still pending. |
| Physical characteristics | `physical_data.py` | pending | Runway, strip, RESA, shoulder, taxiway, and declared-area tables. |
| Taxiway and separations | `taxiway.py` | pending | Include taxiway and parallel runway separation standards. |
| OFS | `ols_surfaces.py` | captured | Chapter 4 obstacle free surfaces captured: approach, transitional, inner approach, inner transitional, and balked landing. Geometry construction pending. |
| OLS | `ols_surfaces.py` | partial | Annex 14 OFS captured; remaining non-OFS Chapter 4 surfaces pending. |
| OES | `oes.py` | partial | Horizontal surface Table 4-10, straight-in instrument approach surface Table 4-11, precision approach surface Table 4-12, instrument departure surface Table 4-13, and take-off climb surface Tables 4-14/4-15 captured; remaining OES surfaces pending. |
| Markings | `markings.py` | pending | Runway marking dimensions, offsets, and applicability. |
| Lighting | `lighting.py` | pending | Runway, threshold, end, centreline, approach, and displaced threshold lighting. |
