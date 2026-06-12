# EASA Ruleset Package

This package contains the draft EASA CS-ADR-DSN Issue 7 ruleset implementation.
It follows the same profile/service structure as `rulesets.mos139` so callers
can resolve the active ruleset through `rulesets.registry.get_ruleset_profile()`
and use the shared ruleset contract.

Source verification status is tracked in `docs/easa_source_verification.md`.
This package targets the current EASA online Easy Access Rules publication,
which incorporates CS-ADR-DSN Issue 7. It should remain treated as a draft
current-EASA implementation until the table-level source verification register
is complete.

Current implemented policy data covers physical runway dimensions, declared
distances, clearway, stopway, OLS surface parameters, runway markings,
airfield ground lighting, taxiway separation, and partial parallel runway
separation.

Controlling OLS remains registered as unsupported until its EASA integration
path is added.

## Modules

`profile.py`
: Public EASA profile facade. It delegates to grouped services and keeps the
active-ruleset method names stable.

`metadata.py`
: Profile identifiers, aliases, status, and capability declarations.

`services.py`
: Grouped service adapters for classification, OLS, physical, markings, and
lighting.

`classification.py`
: Runway type mapping from UI strings to ruleset abbreviations.

`ols_surfaces.py`, `physical_data.py`, `markings.py`, `lighting.py`
: EASA policy sources for implemented families.

`ols.py`, `taxiway.py`
: Compatibility wrappers that satisfy the ruleset contract. `ols.py` delegates
to `ols_surfaces.py`; `taxiway.py` stores CS ADR-DSN.D.260 Table D-1 separation
lookups plus the CS ADR-DSN.B.050 and B.055 parallel runway separation rules.
Segregated parallel operations accept an arrival-threshold stagger value where
positive values reduce the minimum distance and negative values increase it.
