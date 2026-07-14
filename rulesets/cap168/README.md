# UK CAA CAP 168 ruleset

Draft ruleset profile for UK CAA CAP 168 Edition 13.

Implemented parameters:

- Aerodrome reference code number and letter from CAP 168 Table 3.1.
- Runway minimum width from CAP 168 Table 3.2.
- Runway strip length, width, graded area, construction, strength, slope, starter-extension, RNP APCH, and wide non-instrument runway variations from CAP 168 3.69-3.101.
- Runway centreline, threshold, aiming point, touchdown zone, side stripe, dashed side stripe, and holding-position marking parameters from CAP 168 Chapter 7 and Table 3.3.
- Approach, runway edge, threshold/end, starter-extension, runway centreline, touchdown-zone, simple touchdown-zone, and intensity-balance lighting parameters from CAP 168 Chapter 6.
- Declared-distance policy from CAP 168 3.19.
- Clearway length, width, and slope parameters from CAP 168 3.176-3.185.
- Stopway width policy from CAP 168 3.186-3.195.
- Parallel runway separation from CAP 168 3.21 and 3.24-3.25.
- Taxiway-to-runway, taxiway-to-taxiway/object, stand taxilane, and object-height restriction parameters from CAP 168 3.163-3.167.
- Current OLS source parameters from CAP 168 Chapter 4 and Tables 4.1-4.2,
  applicable until 20 November 2030. Approach, take-off climb, transitional,
  OFZ, inner-horizontal, conical, and outer-horizontal source rules are loaded.

Release-gated areas:

- RESA remains scaffolded and not yet source-loaded.
- CAP 168 conventional OLS is selectable as a partial profile. Its independent
  construction context uses the longest physical runway as the main runway,
  the lowest threshold datum, short-runway circles, long-runway racetracks,
  subsidiary tangent joins, length-dependent OHS, LDA/clearway declared-distance
  rules, and nominated offset or curved approach/take-off tracks. The approach
  and take-off climb corridors follow those tracks; track-following approach-
  adjacent transitional construction remains release-gated. Production
  promotion also remains gated on the QGIS topology, performance, and
  independent review suites. The `250 m` Code 2 non-instrument IHS radius printed by
  paragraph 4.50 is recorded as the user-confirmed corrected value `2500 m`.

See `source_matrix.md` for clause-level scope, the three user-confirmed numeric
corrections, and the two retained source/cross-reference interpretations.
