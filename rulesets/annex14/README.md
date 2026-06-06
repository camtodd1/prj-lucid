# ICAO Annex 14 Vol I Ruleset Scaffold

This package is a source-capture scaffold for an ICAO Annex 14 Volume I ruleset.
It is registered with the ruleset selector and exposes the same grouped service
contract as the MOS139 and EASA rulesets.

Implemented now:

- Ruleset metadata, aliases, and capability declarations.
- Runway type classification aliases used by the existing generator.
- Aerodrome reference code number/letter classification from Table 1-1.
- Aeroplane Design Group classification from Table 1-2, applicable from
  21 November 2030.
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
- Empty physical, taxiway, markings, and lighting policy modules.
- An OES service placeholder for future obstacle evaluation surface workflows.

Pending source input:

- Physical characteristics: runway, strip, RESA, shoulder, taxiway, and separation
  tables.
- OLS construction/generation from captured OFS dimensions.
- OES rules and any ADG-derived evaluation surfaces.
- Runway markings and aeronautical ground lighting parameters.
