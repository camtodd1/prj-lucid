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
- Empty physical, taxiway, OLS, markings, and lighting policy modules.
- An OES service placeholder for future obstacle evaluation surface workflows.

Pending source input:

- Physical characteristics: runway, strip, RESA, shoulder, taxiway, and separation
  tables.
- OLS dimensions and surface families.
- OES rules and any ADG-derived evaluation surfaces.
- Runway markings and aeronautical ground lighting parameters.
