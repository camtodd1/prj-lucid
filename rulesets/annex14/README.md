# ICAO Annex 14 Vol I Rulesets

This package exposes two independent ICAO Annex 14 Volume I
protected-airspace profiles through the ruleset selector:

- `ICAO Annex 14 Vol I - Current OLS`
- `Annex 14 Modernised OLS`

The current OLS profile is production-supported for the conventional OLS
applicable until 20 November 2030. The modernised OFS/OES profile holds the
future protected-airspace model that is not enforceable until
21 November 2030.

Implemented now:

- Ruleset metadata, aliases, and capability declarations.
- Runway type classification aliases used by the existing generator.
- Aerodrome reference code number/letter classification from Table 1-1.
- Aeroplane Design Group classification from Table 1-2, applicable from
  21 November 2030.
- Current Table 4-1 and Table 4-2 conventional OLS construction, including
  airport-wide, approach, take-off climb, transitional and precision OFZ
  families.
- Current Chapter 3 strip, clearway and stopway dependencies used by the OLS
  constructor.
- Per-runway ADG input in the main dialog for modernised Annex 14 OFS/OES
  generation, alongside the existing ARC inputs used by current OLS and other
  design standards.
- Approach surface lookups from Tables 4-1 and 4-2.
- Transitional surface lookup from 4.2.2.
- Inner approach surface lookups from Tables 4-3, 4-4, and 4-5.
- Inner transitional surface lookups from Tables 4-6, 4-7, and 4-8.
- Balked landing surface lookup from Table 4-9.
- Coordinated obstacle free surfaces package for Chapter 4 OFS data.
- Horizontal obstacle evaluation surface lookup from Table 4-10.
- Straight-in instrument approach obstacle evaluation surface lookup from
  Table 4-11.
- Precision approach obstacle evaluation surface lookup from Table 4-12.
- Instrument departure obstacle evaluation surface lookup from Table 4-13.
- Take-off climb obstacle evaluation surface lookup from Tables 4-14 and 4-15.
- Obstacle limitation requirement policy from 4.4.
- Obstacle surface establishment policy from 4.5.
- First-pass Annex 14 OFS/OES plan-view geometry builder for approach,
  inner approach, balked landing, horizontal, straight-in instrument,
  precision approach, instrument departure, and take-off climb surfaces.
- Empty physical, taxiway, markings, and lighting policy modules.
- An OES service placeholder for future obstacle evaluation surface workflows.

Pending source input outside current OLS:

- Remaining physical characteristics: runway, RESA, shoulder, taxiway, and
  separation tables.
- Runway markings and aeronautical ground lighting parameters.
