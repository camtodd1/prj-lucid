# ICAO Annex 14 Vol I Ruleset Scaffold

This package is a source-capture scaffold for ICAO Annex 14 Volume I rulesets.
It exposes two protected-airspace profiles through the ruleset selector:

- `ICAO Annex 14 Vol I - Current OLS`
- `ICAO Annex 14 Vol I - Modernised OFS/OES (from 21 Nov 2030)`

The current OLS profile is the landing pad for the enforceable Annex 14 OLS
surfaces. The modernised OFS/OES profile holds the future protected-airspace
model that is not enforceable until 21 November 2030.

Implemented now:

- Ruleset metadata, aliases, and capability declarations.
- Runway type classification aliases used by the existing generator.
- Aerodrome reference code number/letter classification from Table 1-1.
- Aeroplane Design Group classification from Table 1-2, applicable from
  21 November 2030.
- Current OLS profile scaffold for enforceable Annex 14 protected airspace.
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

Pending source input:

- Physical characteristics: runway, strip, RESA, shoulder, taxiway, and separation
  tables.
- Current Annex 14 OLS surface dimension tables and geometry generation.
- Full complex transitional and inner transitional geometry construction.
- TODA/clearway-aware departure and take-off climb start positions.
- Runway markings and aeronautical ground lighting parameters.
