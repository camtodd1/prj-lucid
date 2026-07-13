# Annex 14 Source Matrix

Use this matrix to track source capture before promoting capabilities from
`scaffold` or `unsupported`.

| Area | Module | Status | Notes |
| --- | --- | --- | --- |
| Runway type mapping | `classification.py` | scaffolded | Existing app type labels map to NI/NPA/PA codes. |
| Reference code / design group | `classification.py` | partial | Table 1-1 and Table 1-2 captured; current OLS keeps ARC, modernised OFS/OES uses explicit ADG or critical aircraft data. |
| Physical characteristics | `physical_data.py` | pending | Runway, strip, RESA, shoulder, taxiway, and declared-area tables. |
| Taxiway and separations | `taxiway.py` | pending | Include taxiway and parallel runway separation standards. |
| Current OLS | `current_ols.py` | scaffolded | Current enforceable Annex 14 OLS guideline stream added; surface dimension source input still pending. |
| Modernised OFS | `ols_surfaces.py`, `surfaces/annex14_geometry.py` | source-checked partial | Future Chapter 4 OFS tables and elevation rules were visually checked against the supplied Ninth Edition extract. Representative production values and independent contour/elevation checkpoints are locked by `tests/fixtures/ols/source_validation_v1.json`; complete ADG/option and airport-fixture coverage remains pending. |
| Modernised OES | `oes.py`, `surfaces/annex14_geometry.py` | source-checked partial | Horizontal, straight-in instrument, precision approach, instrument departure, and take-off climb values were visually checked against Tables 4-10–4-15. Independent elevation/contour checkpoints pass; TODA/clearway and broader airport-fixture evidence remain pending. |
| Source-backed analytical validation | `tests/ols_source_oracle.py`, `tests/test_ols_source_validation.py` | first tranche complete | Production-independent MOS/OFS/OES/comparison calculations, source hashes, clauses/pages, expected values and tolerances are documented in `docs/ols_source_validation_2026-07-13.md`. Independent reviewer sign-off is pending. |
| Obstacle limitation requirements | `obstacle_requirements.py` | captured | Section 4.4 captured as penetration/exception/aeronautical-study policy; no geometry parameters. |
| Surface establishment requirements | `obstacle_requirements.py` | captured | Section 4.5 captured as OFS by runway use and OES by operation; no geometry parameters. |
| Markings | `markings.py` | pending | Runway marking dimensions, offsets, and applicability. |
| Lighting | `lighting.py` | pending | Runway, threshold, end, centreline, approach, and displaced threshold lighting. |
