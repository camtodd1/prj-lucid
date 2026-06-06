# ICAO Annex 14 Vol I Ruleset Scaffold

This package is a source-capture scaffold for an ICAO Annex 14 Volume I ruleset.
It is registered with the ruleset selector and exposes the same grouped service
contract as the MOS139 and EASA rulesets.

Implemented now:

- Ruleset metadata, aliases, and capability declarations.
- Runway type classification aliases used by the existing generator.
- Empty physical, taxiway, OLS, markings, and lighting policy modules.
- An OES service placeholder for future obstacle evaluation surface workflows.
- A design-group placeholder for future Annex 14 reference code and ADG-derived
  compatibility inputs.

Pending source input:

- Aerodrome reference code number and letter classification tables.
- Physical characteristics: runway, strip, RESA, shoulder, taxiway, and separation
  tables.
- OLS dimensions and surface families.
- OES rules and any ADG-derived evaluation surfaces.
- Runway markings and aeronautical ground lighting parameters.
