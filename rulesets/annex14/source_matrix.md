# Annex 14 Source Matrix

**Status:** Current

This matrix separates the current conventional OLS applicable until
20 November 2030 from the future OFS/OES model applicable from
21 November 2030.

| Area | Module | Status | Notes |
| --- | --- | --- | --- |
| Runway type mapping | `classification.py` | scaffolded | Existing app type labels map to NI/NPA/PA codes. |
| Reference code / design group | `classification.py` | partial | Table 1-1 and Table 1-2 captured; current OLS keeps ARC, modernised OFS/OES uses explicit ADG or critical aircraft data. |
| Current OLS physical dependencies | `physical_data.py` | source-loaded | Chapter 3 strip length/width/graded width, clearway and stopway rules required by OLS construction are loaded. Other physical families remain out of scope. |
| Taxiway and separations | `taxiway.py` | pending | Include taxiway and parallel runway separation standards. |
| Current OLS | `current_ols.py`, `ols_construction.py` | production-supported | Current Table 4-1 approach, transitional, IHS, conical and OFZ families plus Table 4-2 take-off climb are source-loaded and constructed through the conventional OLS engine. |
| Modernised OFS | `ols_surfaces.py`, `surfaces/annex14_geometry.py` | source-checked partial | Future Chapter 4 OFS tables and elevation rules were visually checked against the supplied Ninth Edition extract. Representative production values and independent contour/elevation checkpoints are locked by `tests/fixtures/ols/source_validation_v1.json`; complete ADG/option and airport-fixture coverage remains pending. |
| Modernised OES | `oes.py`, `surfaces/annex14_geometry.py` | source-checked partial | Horizontal, straight-in instrument, precision approach, instrument departure, and take-off climb values were visually checked against Tables 4-10–4-15. Independent elevation/contour checkpoints pass; TODA/clearway and broader airport-fixture evidence remain pending. |
| Source-backed analytical validation | `tests/ols_source_oracle.py`, `tests/test_ols_source_validation.py` | First tranche complete | Production-independent MOS/OFS/OES/comparison calculations, source hashes, clauses/pages, expected values, and tolerances are stored in `tests/fixtures/ols/source_validation_v1.json`. Optional peer review remains useful for high-impact changes but is not a routine internal-use gate. |
| Obstacle limitation requirements | `obstacle_requirements.py` | captured | Section 4.4 captured as penetration/exception/aeronautical-study policy; no geometry parameters. |
| Surface establishment requirements | `obstacle_requirements.py` | captured | Section 4.5 captured as OFS by runway use and OES by operation; no geometry parameters. |
| Markings | `markings.py` | pending | Runway marking dimensions, offsets, and applicability. |
| Lighting | `lighting.py` | pending | Runway, threshold, end, centreline, approach, and displaced threshold lighting. |

## Current OLS source record

- `ICAO Annex 14 Aerodrome Design and Operations - Chapter 4.pdf`, SHA-256
  `15a5618515f4c7088eb59b86392b53c24f15a05fa9341484931c421489f39cb9`.
- `ICAO Annex 14 Aerodrome Design and Operations - Standards and Recommended Practices.pdf`,
  SHA-256 `71064dc685b4a008828f2655fb7a8217e44e3407d4c0f78d2b4f82b9cbe74a36`.
- `ICAO Annex 14 Amendment 18 - State Letter.pdf`, SHA-256
  `39ebf233b74c4843a3c572339e8465a73b4103ca2046a8f271dd74963d3cb10f`.

The current Chapter 4 tables are visually verified on supplied PDF pages
11–14. Chapter 3 strip and clearway dependencies are visually verified in the
full standard and Amendment 18 material. Amendment 18 changes the
non-instrument code 3 strip lateral distance to 55 m. It does not identify
3.4.2 strip-end length as amended; the conventional 60 m requirement for
codes 2–4 is therefore retained, while non-instrument code 1 uses 30 m.

Annex 14 4.1.5 permits the inner-horizontal plan form to follow aerodrome
layout and states that the radius is measured from established reference
points. The shared constructor uses the established strip-end racetrack plan
and the applicable Table 4-1 radius. The IHS elevation uses the application's
independently calculated/established reference elevation datum. These are
recorded implementation interpretations because the detailed establishment
guidance sits in Doc 9137, Part 6 rather than the supplied normative tables.

The post-2030 OFS/OES parameters and geometry remain in `ols_surfaces.py` and
`surfaces/annex14_geometry.py`; current OLS activation does not route through
or modify that model.
