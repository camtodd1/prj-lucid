# CAP 168 Source Matrix

**Status:** Current

This matrix records the UK CAA CAP 168 source-loading state. The reviewed
source is *CAP 168 Licensing of Aerodromes*, Thirteenth Edition, July 2025,
Chapter 4, incorporating Amendment 15. Its current OLS table is labelled
applicable until 20 November 2030.

| Area | Source | Implementation | Status / interpretation |
| --- | --- | --- | --- |
| Take-off climb | 4.8-4.20, Table 4.1, printed pp.227-229 / PDF pp.4-6 | `TOCS_PARAMS`, `TAKE_OFF_CLIMB_CONSTRUCTION_RULES` | Loaded. Normal Code 3/4 final width is 1,200 m; 1,800 m is retained as the >15-degree heading-change option. Clearway station/width, wide-runway, slew and reduced-slope rules are explicit. |
| Approach | 4.21-4.27, Table 4.2, printed pp.231-234 / PDF pp.8-11 | `APPROACH_PARAMS`, `APPROACH_CONSTRUCTION_RULES` | Loaded for NI, NPA and precision Codes 1-4, including elevation datum, 150 m instrument cap, wide-runway and offset/curved-track rules. Current applicability ends 20 November 2030. |
| Transitional | 4.34-4.39, especially 4.36, printed p.238 / PDF p.15 | `TRANSITIONAL_PARAMS` | Loaded: 20% for NI/NPA Codes 1/2; 14.3% otherwise. |
| Inner horizontal | 4.45-4.52, printed p.240 / PDF p.17 | `IHS_HEIGHT_RULE`, `IHS_PLAN_RULES`, `Cap168OlsConstructionPolicy` | Integrated. Elevation is 45 m above the lowest runway threshold, not RED. The longest physical runway is the main runway; plan form varies by its length, with applicable subsidiary joins. |
| Conical | 4.53-4.55, printed pp.240-241 / PDF pp.17-18 | `CONICAL_RULES`, `Cap168OlsConstructionPolicy` | Integrated: 5%; 105 m above IHS normally, 55 m NI Code 2, 35 m NI Code 1. |
| Outer horizontal | 4.56-4.58, printed p.241 / PDF p.18 | `OUTER_HORIZONTAL_RULES` | Loaded. Applicability/radius depends on actual main-runway length, so legacy ARC-only lookup is intentionally not used. |
| OFZ / inner surfaces | 4.59-4.73, printed pp.241-244 / PDF pp.18-21 | `INNER_APPROACH_PARAMS`, `INNER_TRANSITIONAL_PARAMS`, `BAULKED_LANDING_PARAMS`, `OFZ_APPLICABILITY_RULES` | Source-loaded for precision runway combinations, including Cat I versus Cat II/III establishment language, and exercised by the CAP168 workflow fixtures. |
| Runway threshold markings | 7.207-7.210, Table 7.3 | `markings.py`, `generate_detailed_runway_markings` | Loaded for paved runways. Threshold bars and Table 7.3 piano keys use the CAP168 source reference; standard width rows are 18, 23, 30 and 45 m. Widths outside those rows retain an explicit QA skip for the piano-key layout. |
| Independent validation | Chapter 4 source facts above | `tests/fixtures/ols/source_validation_v1.json` | Representative source constants, independently calculated approach elevations/contour, IHS elevation and conical contour are locked. Production promotion was approved by the project owner on 14 July 2026; a secondary independent source review remains recommended release governance. |

## Confirmed source corrections and retained interpretations

The supplied PDF was checked visually. These are present in the rendered source,
not text-extraction artefacts:

1. Table 4.1 prints `180 m` beneath the normal 1,200 m Code 3/4 final width,
   while its own footnote 4 specifies 1,800 m for an intended-track heading
   change over 15 degrees. The conditional parameter uses the unambiguous
   footnote value of 1,800 m.
2. Table 4.2 prints `6 m` for the precision Code 3/4 distance before threshold.
   The user confirmed this is `60 m`; the corrected value also agrees with
   paragraph 4.23.
3. Table 4.2 prints `360 m` for the precision Code 3/4 second section. A 3,600 m
   section is required to rise the remaining 90 m at 2.5% to the 150 m plane in
   4.26 and makes the published 3,000 + 3,600 + 8,400 = 15,000 m total. The user
   confirmed the corrected value is `3,600 m`.
4. Paragraph 4.50 prints `250 m` as the NI Code 2 short-runway IHS radius. The
   user confirmed the corrected value is `2,500 m`; that value is now recorded
   in `IHS_PLAN_RULES`.
5. Paragraph 4.73(1), describing Code 1/2 OFZ, points back to the area in 4.70
   (Code 3/4) rather than 4.72. The loaded Code 1/2 balked-landing origin follows
   the immediately preceding Code 1/2 area in 4.72 and records the resulting
   `60_m_beyond_lda` rule.

## Capability position

CAP168 conventional OLS is production-supported. Its supported scope includes
airport-wide, approach, take-off climb, OFZ and controlling-lower-envelope
construction; longest-runway main-runway selection; and explicit aligned,
offset, curved and greater-than-15-degree nominated tracks.

The OLS fixture manifest and runtime ledger retain the pure policy/source checks
and headless QGIS contracts for short, single, main/subsidiary, parallel, and
intersecting runway configurations. Numeric topology closure is bounded to
0.020 m² per completed partition and is reported separately from exceptional
recovery. Offset and curved paths must be supplied as line geometry beginning
at the applicable construction origin; missing or invalid nominated paths
remain visibly blocked.

CAP168 physical capabilities retain their own capability declarations. In
particular, RESA remains unsupported and is not implied by this OLS promotion.
