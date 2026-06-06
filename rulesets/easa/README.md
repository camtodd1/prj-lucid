# EASA Ruleset Package

This package contains the draft EASA CS-ADR-DSN Issue 6 ruleset implementation.
It follows the same profile/service structure as `rulesets.mos139` so callers
can resolve the active ruleset through `rulesets.registry.get_ruleset_profile()`
and use the shared ruleset contract.

Current implemented policy data covers physical runway dimensions, OLS surface
parameters, runway markings, and airfield ground lighting. Declared distances,
clearway, stopway, and taxiway separation are registered explicitly as
unsupported until their EASA policy tables are added.

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
to `ols_surfaces.py`; `taxiway.py` returns `None` until EASA taxiway separation
policy is added.
