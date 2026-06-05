# MOS139 Ruleset Package

This package contains the current CASA Part 139 MOS 2019 ruleset implementation.
It is the reference structure for future rulesets such as EASA, Annex 14, or
future Annex 14 OLS modernisation.

## Public Shape

`profile.py` exposes `MOS139_PROFILE`, the registered ruleset profile used by
the plugin. Existing generator code should normally call methods on the active
profile returned by `rulesets.registry.get_ruleset_profile()` or
`SafeguardingBuilder.get_active_ruleset()`.

The profile keeps legacy-style facade methods, for example:

```python
ruleset.ols_parameters(...)
ruleset.strip_parameters(...)
ruleset.threshold_marking_params(...)
ruleset.agl_value(...)
```

It also exposes grouped service adapters for newer code:

```python
ruleset.classification
ruleset.ols
ruleset.physical
ruleset.markings
ruleset.lighting
```

The facade methods are retained so existing generation code does not need a
large rewrite while rulesets are being introduced.

## Module Ownership

`metadata.py`
: Ruleset id, display name, edition, aliases, and advertised capabilities.

`profile.py`
: Public MOS139 profile facade. It delegates to grouped services and keeps the
existing active-ruleset method names stable.

`services.py`
: Service grouping layer for `classification`, `ols`, `physical`, `markings`,
and `lighting`.

`classification.py`
: Runway type string to MOS abbreviation mapping and precision approach type
codes.

`physical_data.py`
: Pavement/shoulder references, strip dimensions, and RESA policy.

`taxiway.py`
: Taxiway minimum separation offsets and lookup behaviour.

`ols_surfaces.py`
: OLS surface dimensions and lookup behaviour, including approach, take-off
climb, inner horizontal, conical, outer horizontal, transitional, OFZ-related
surfaces, and IHS base height.

`markings.py`
: Runway marking policy including threshold bars, centreline widths, aiming
points, touchdown-zone marking offsets, and runway holding positions.

`lighting.py`
: Airfield Ground Lighting references, dimensions, colours, approach profiles,
and helper rules.

`ols_dimensions.py`
: Internal compatibility facade. It re-exports split MOS139 modules for older
imports. New MOS139 code should prefer the domain modules above.

## Compatibility Shims

The root-level files below are compatibility shims:

```text
dimensions/ols_dimensions.py
dimensions/agl_dimensions.py
```

They forward old imports to this ruleset package. They should not be used as
the source of truth for new MOS139 work.

## Adding Or Changing MOS139 Rules

Put changes in the domain module that owns the rule:

- runway type mappings: `classification.py`
- physical strip or RESA rules: `physical_data.py`
- taxiway separation rules: `taxiway.py`
- OLS surface rules: `ols_surfaces.py`
- runway markings: `markings.py`
- lighting and AGL: `lighting.py`
- profile metadata/capabilities: `metadata.py`

Keep `profile.py` focused on delegation and public API stability. If a new
policy area is added, add it to `services.py`, expose it through `profile.py`,
and extend `tests/test_rulesets.py` contract tests.

## Testing

After ruleset edits, run:

```bash
python3 -m unittest tests.test_rulesets
python3 -m py_compile dimensions/*.py rulesets/*.py rulesets/mos139/*.py tests/*.py
```

For plugin-wide confidence, also run the broader compile command documented in
the root `README.md`.
