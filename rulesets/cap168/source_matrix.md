# CAP 168 Source Matrix

This matrix records the UK CAA CAP 168 source-loading state. The reviewed
source is *CAP 168 Licensing of Aerodromes*, Thirteenth Edition, July 2025,
Chapter 4, incorporating Amendment 15. Its current OLS table is labelled
applicable until 20 November 2030.

| Area | Source | Implementation | Status / interpretation |
| --- | --- | --- | --- |
| Take-off climb | 4.8-4.20, Table 4.1, printed pp.227-229 / PDF pp.4-6 | `TOCS_PARAMS`, `TAKE_OFF_CLIMB_CONSTRUCTION_RULES` | Loaded. Normal Code 3/4 final width is 1,200 m; 1,800 m is retained as the >15-degree heading-change option. Clearway station/width, wide-runway, slew and reduced-slope rules are explicit. |
| Approach | 4.21-4.27, Table 4.2, printed pp.231-234 / PDF pp.8-11 | `APPROACH_PARAMS`, `APPROACH_CONSTRUCTION_RULES` | Loaded for NI, NPA and precision Codes 1-4, including elevation datum, 150 m instrument cap, wide-runway and offset/curved-track rules. Current applicability ends 20 November 2030. |
| Transitional | 4.34-4.39, especially 4.36, printed p.238 / PDF p.15 | `TRANSITIONAL_PARAMS` | Loaded: 20% for NI/NPA Codes 1/2; 14.3% otherwise. |
| Inner horizontal | 4.45-4.52, printed p.240 / PDF p.17 | `IHS_HEIGHT_RULE`, `IHS_PLAN_RULES` | Source-loaded, constructor integration pending. Elevation is 45 m above the lowest runway threshold, not RED. Plan form varies by actual main-runway length. |
| Conical | 4.53-4.55, printed pp.240-241 / PDF pp.17-18 | `CONICAL_RULES` | Loaded: 5%; 105 m above IHS normally, 55 m NI Code 2, 35 m NI Code 1. Constructor integration pending. |
| Outer horizontal | 4.56-4.58, printed p.241 / PDF p.18 | `OUTER_HORIZONTAL_RULES` | Loaded. Applicability/radius depends on actual main-runway length, so legacy ARC-only lookup is intentionally not used. |
| OFZ / inner surfaces | 4.59-4.73, printed pp.241-244 / PDF pp.18-21 | `INNER_APPROACH_PARAMS`, `INNER_TRANSITIONAL_PARAMS`, `BAULKED_LANDING_PARAMS`, `OFZ_APPLICABILITY_RULES` | Source-loaded for precision runway combinations, including Cat I versus Cat II/III establishment language. End-to-end geometry fixtures remain pending. |
| Independent validation | Chapter 4 source facts above | `tests/fixtures/ols/source_validation_v1.json` | Representative source constants, independently calculated approach elevations/contour, IHS elevation and conical contour are locked. Reviewer sign-off pending. |

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

CAP168 OLS capability remains `unsupported` in profile metadata even though the
parameter model is source-loaded. Promotion first requires:

- a datum-aware airport-wide constructor using the lowest threshold;
- correct circle/racetrack selection and subsidiary-runway joins;
- actual-runway-length inputs for IHS and OHS applicability;
- conditional clearway and >15-degree TOCS widths;
- CAP168-specific generated-geometry and controlling-envelope fixtures; and
- independent technical review of the source capture and generated results.
