# Ruleset Phase 0 Audit

This document captures the initial ruleset audit for expanding Safeguarding
Builder beyond the current MOS139 implementation. It is intended to be the
handoff into Phase 1 ruleset foundation work, not a final regulatory
interpretation.

## Goals

- Separate aerodrome-standard logic from shared QGIS geometry construction.
- Preserve the existing MOS139 behaviour while creating a path for Annex 14,
  future Annex 14 OLS modernisation, EASA, and local standards.
- Keep Australian NASF planning guidelines and CNS safeguarding as selectable
  supplementary frameworks rather than implicitly bundling them into every
  aerodrome standard.
- Define stable ruleset identifiers, capability names, and migration boundaries.
- Identify the policy-coupled code that must move behind ruleset services.

## Non-Goals

- Implement a second standard in Phase 0.
- Add grandfathered override inputs in Phase 0.
- Reinterpret MOS, Annex 14, EASA, or NASF source material in this audit.
- Refactor generation code before a regression harness exists.

## Current Ruleset State

The dialog already has a ruleset selector, but it is disabled and only contains
`MOS139`.

Current behaviour:

- `SafeguardingBuilderDialog._setup_ruleset_selector_ui()` creates a disabled
  `comboBox_ruleset`.
- Dialog persistence saves and loads a `ruleset` field.
- `get_all_input_data()` includes the selected ruleset in final input data.
- Runway validation stores a per-runway `ruleset`, defaulting to `MOS139`.
- Processing does not currently use the selected ruleset to choose dimensions,
  applicability rules, geometry algorithms, or output capabilities.

## Proposed Ruleset Model

Use one selected aerodrome standard plus zero or more supplementary frameworks.

```text
RulesetContext
    aerodrome_standard: mos139_2019
    supplementary_frameworks:
        - nasf_aus
        - cns_bra_aus
    implementation_status: stable | partial | experimental
```

The aerodrome standard should own:

- runway classification vocabulary and mapping;
- physical runway and protection-area dimensions;
- OLS dimensions and applicability;
- runway marking requirements;
- airfield ground lighting rules;
- declared-distance and clearway policies;
- regulatory references for those outputs.

Supplementary frameworks should own:

- NASF Guideline B/C/D/E/F/G/I planning outputs;
- CNS building restricted area dimensions;
- Australian-only specialised safeguarding outputs;
- framework-specific references and labels.

The same geometry helpers can still be shared. The key distinction is that
generators should ask a ruleset or framework service for decisions and values
instead of importing MOS/NASF constants directly.

## Stable Identifiers

Initial aerodrome standard IDs:

| ID | Display Name | Initial Status | Notes |
| --- | --- | --- | --- |
| `mos139_2019` | CASA Part 139 MOS 2019 | Stable after migration | Current implemented behaviour. |
| `icao_annex14_current` | ICAO Annex 14 current | Planned | Good first second-standard candidate. |
| `icao_annex14_future_ols` | ICAO Annex 14 future OLS modernisation | Planned, likely experimental | Treat as separate because topology may differ from current OLS generation. |
| `easa_cs_adr_dsn` | EASA CS-ADR-DSN | Planned | Scope depends on required output families. |
| `custom_airport_local` | Local / airport-specific standard | Future | Should probably compose a base standard plus controlled overrides. |

Initial supplementary framework IDs:

| ID | Display Name | Initial Status | Notes |
| --- | --- | --- | --- |
| `nasf_aus` | Australian NASF Guidelines | Current behaviour | Includes Guideline B/C/D/E/F/G/I grouping and outputs. |
| `cns_bra_aus` | Australian CNS BRA safeguarding | Partial | Current data includes many placeholder height rules. |
| `met_station_aus` | MET station safeguarding | Current behaviour | Could remain an optional framework or airport-support output. |

## Capability Names

Rulesets and frameworks should declare capabilities so the UI and processing
pipeline can disable unsupported outputs clearly.

Suggested capability keys:

- `classification.runway_type_mapping`
- `physical.pavement`
- `physical.shoulder`
- `physical.strip`
- `physical.resa`
- `physical.clearway`
- `physical.stopway`
- `physical.taxiway_separation`
- `ols.airport_wide`
- `ols.runway_approach`
- `ols.takeoff_climb`
- `ols.ofz`
- `ols.controlling_lower_envelope`
- `markings.runway`
- `lighting.runway`
- `lighting.approach`
- `declared_distances.calculated`
- `framework.nasf.guidelines`
- `framework.cns.bra`
- `framework.met.station`

Each capability should carry:

- `status`: `supported`, `partial`, `unsupported`, or `experimental`;
- `source`: ruleset/framework ID;
- `notes`: short user-facing caveat;
- `output_groups`: generated layer families affected.

## Policy Coupling Inventory

### Ruleset Selector And Persistence

Files:

- `safeguarding_builder_dialog.py`
- `dialog/persistence.py`
- `dialog/runway_group.py`

Current coupling:

- Selector is hard-coded to `MOS139 (current)` and disabled.
- Save/load payload stores a string ruleset value.
- Runway validation stores `ruleset` but no downstream code consumes it.

Phase 1 implications:

- Replace hard-coded selector content with a registry.
- Save a structured ruleset object while continuing to accept legacy string
  payloads.
- Treat selected aerodrome standard as airport-level state, not independent
  per-runway state, unless a future feature explicitly supports mixed standards.

### MOS OLS And Physical Dimensions

Files:

- `dimensions/ols_dimensions.py`
- `surfaces/physical.py`
- `surfaces/specialised.py`
- `guidelines/ols_guideline.py`
- `safeguarding_builder.py`

Current coupling:

- `RUNWAY_TYPE_MAP` defines MOS runway type abbreviations.
- `STRIP_WIDTH_PARAMS`, `STRIP_EXTENSION_PARAMS`, and `RESA_PARAMS` contain
  MOS physical dimensions and applicability decisions.
- `APPROACH_PARAMS`, `INNER_APPROACH_PARAMS`, `INNER_TRANSITIONAL_PARAMS`,
  `BAULKED_LANDING_PARAMS`, `TOCS_PARAMS`, `IHS_PARAMS`, `CONICAL_PARAMS`,
  `OHS_PARAMS`, and `TRANSITIONAL_PARAMS` contain MOS OLS dimensions.
- `TAXIWAY_SEPARATION_PARAMS` contains MOS taxiway separation offsets, with
  several references marked "Verify".
- `_calculate_reference_elevation_datum()` implements the MOS RED policy.
- `_calculate_effective_clearway_specs()` implements MOS clearway length/width
  policy and a MOS cap at half TORA.
- OLS generators include MOS-specific assumptions such as conical continuation
  where OHS applies.
- Output attributes are named `ref_mos`.

Classification:

- Lookup values: strip widths, RESA lengths, OLS dimensions, taxiway offsets.
- Applicability decisions: RESA required, OHS present, precision-only OFZ
  surfaces, runway type fallbacks.
- Calculation policy: RED, clearway effective dimensions, conical continuation.
- Geometry algorithm: current OLS topology and controlling lower envelope.
- Citation/output label: `ref_mos` fields and MOS strings in attributes.

Phase 1 implications:

- Create a MOS139 ruleset service that initially wraps existing helpers.
- Introduce generic reference fields or metadata while preserving existing
  `ref_mos` attributes for compatibility.
- Keep future Annex 14 OLS modernisation as a separate capability because it
  may not fit the current OLS topology.

### Runway Markings

Files:

- `surfaces/physical.py`
- `docs/runway_marking_matrix.md`
- `docs/TODO.md`

Current coupling:

- `generate_detailed_runway_markings()` is explicitly MOS139.
- Threshold piano-key tables, centreline marking widths, aiming point rules,
  TDZ offsets, displaced-threshold arrows, pre-threshold markings, side stripes,
  and runway holding position distances are hard-coded.
- Several assumptions are captured as QA notes rather than separate policies.
- TODO already calls for alternate marking rule sets such as Annex 14.

Classification:

- Lookup values: threshold stripe counts/gaps, line widths, holding distances.
- Applicability decisions: marking families by surface, width, runway type,
  LDA, displaced thresholds, LAHSO.
- Geometry algorithm: marking polygon construction and clipping.
- Citation/output label: MOS section references and QA notes.

Phase 1 implications:

- Extract marking decisions into a `markings` ruleset service before adding a
  second marking standard.
- Keep low-level rectangle/polygon helpers in `surfaces/physical.py` or a
  shared geometry module.

### Airfield Ground Lighting

Files:

- `dimensions/agl_dimensions.py`
- `surfaces/airfield_ground_lighting.py`
- `dialog/agl_options.py`
- `docs/airfield_ground_lighting_rules.md`

Current coupling:

- AGL reference strings and numeric rules are MOS Part 139 2019.
- Generation imports constants directly from `dimensions.agl_dimensions`.
- Dialog default approach profiles come from `approach_profile_for_end()`.
- Some regulatory concessions are documented but not generated.

Classification:

- Lookup values: spacing, light counts, colours, approach lighting profiles.
- Applicability decisions: runway type support, precision/instrument triggers,
  TDZ/approach/wing-bar/RTIL generation.
- Calculation policy: shared runway edge spacing, threshold counts, low-visibility
  centreline spacing.
- Geometry algorithm: light placement and coincident-light merging.
- Citation/output label: MOS references in attributes.

Phase 1 implications:

- AGL should not be globally imported from MOS constants once additional
  standards exist.
- Dialog previews should query the active ruleset, or show defaults only after
  a ruleset is selected.
- Unsupported lighting capabilities for a ruleset must be explicit rather than
  silently using MOS.

### NASF Guidelines

Files:

- `guidelines/guideline_constants.py`
- `guidelines/simple.py`
- `guidelines/lighting.py`
- `guidelines/ols_guideline.py`
- `dimensions/cns_dimensions.py`
- `safeguarding_builder.py`

Current coupling:

- Group names and output sections are branded as NASF Guidelines.
- Guideline B/C/D/E/I dimensions are hard-coded in `guideline_constants.py`.
- Guideline E has both NASF and MOS references.
- Guideline F currently produces OLS outputs, but those OLS dimensions are MOS
  values from `ols_dimensions.py`.
- Guideline G uses CNS BRA dimensions from `dimensions/cns_dimensions.py`.

Classification:

- Supplementary framework rules: NASF B/C/D/E/G/I.
- Mixed framework/aerodrome-standard rules: Guideline F OLS when using MOS OLS.
- Lookup values: guideline radii, offsets, zone widths/lengths, CNS BRA radii.
- Applicability decisions: ARP/CNS/runway prerequisites and framework toggles.
- Citation/output label: NASF and MOS references.

Phase 1 implications:

- NASF should be selectable independently from the aerodrome standard.
- For non-Australian aerodrome standards, NASF outputs should either be disabled
  by default or clearly labelled as an additional Australian planning framework.
- Guideline F should be renamed internally as an OLS output family generated
  under the active aerodrome standard, with NASF grouping kept as a presentation
  option only if desired.

### CNS BRA

Files:

- `dimensions/cns_dimensions.py`
- `guidelines/simple.py`
- `dialog/cns_table.py`

Current coupling:

- CNS facility types are entered manually in the dialog.
- `CNS_BRA_SPECIFICATIONS` stores facility-specific BRA geometry.
- Height rules are mostly `TBD`.
- Glide Path and Localiser are explicitly empty pending specialised geometry.

Classification:

- Supplementary framework rules.
- Lookup values: facility-zone radii and shape type.
- Applicability decisions: facility type support.
- Missing policy: height rules, GP/LOC specialised geometry.

Phase 1 implications:

- Keep CNS outside the aerodrome-standard ruleset until the source standard is
  confirmed.
- Mark the framework capability as partial.

### Reports And Output Metadata

Files:

- `reports/runway_summary.py`
- `safeguarding_builder.py`
- `core/styles.py`
- QML style files

Current coupling:

- Reports collect and display `mos_refs`.
- Generated attributes often use `ref_mos`.
- Output group names include NASF and OLS terminology.
- Style keys are output-family oriented and mostly ruleset-neutral.

Classification:

- Citation/output label.
- Compatibility surface for downstream users.

Phase 1 implications:

- Add generic regulatory reference collection while preserving `ref_mos` until
  a schema migration is planned.
- Add ruleset/framework metadata to reports and generated layer groups.

## Proposed Phase 1 Interfaces

Phase 1 should introduce interfaces that can wrap existing helpers first.

```python
class RulesetProfile:
    id: str
    display_name: str
    edition: str
    status: str
    capabilities: dict

    def classify_runway_type(self, label: str) -> str: ...
    def precision_type_codes(self) -> set[str]: ...
    def reference_elevation_datum(self, arp_elevation, runway_data_list): ...
    def strip_parameters(self, context): ...
    def resa_parameters(self, context): ...
    def clearway_parameters(self, context): ...
    def ols_parameters(self, surface_type: str, context): ...
    def taxiway_separation_offset(self, context): ...
    def marking_policy(self, context): ...
    def lighting_policy(self, context): ...
```

Suggested context objects:

- `RunwayClassificationContext`
- `RunwayEndContext`
- `RunwayPhysicalContext`
- `OlsSurfaceContext`
- `LightingContext`
- `MarkingContext`

These can start as plain dictionaries if that keeps the migration small, but
typed dataclasses would make contract testing easier.

## Migration Order Recommended By Audit

1. Add `rulesets/registry.py`, `rulesets/base.py`, and `rulesets/mos139/`.
2. Wrap `dimensions/ols_dimensions.py` through a MOS139 ruleset service without
   moving tables yet.
3. Create `RulesetContext` in `run_safeguarding_processing()` after input
   validation.
4. Route RED, strip, RESA, clearway, OLS parameter, and taxiway separation calls
   through the active ruleset.
5. Migrate markings policy behind the active ruleset.
6. Migrate AGL policy behind the active ruleset.
7. Split NASF/CNS into supplementary framework capability declarations.
8. Enable the selector only after MOS139 output has a regression harness.

## Verification Needs

The repository currently relies on syntax checks and QGIS runtime validation.
Before enabling a second ruleset, add a lightweight test harness for:

- ruleset registry loading;
- legacy `MOS139` payload compatibility;
- runway type classification;
- strip, RESA, OLS, taxiway, marking, and AGL policy lookups;
- RED and clearway policy calculations;
- capability gating and unsupported-output warnings;
- report reference collection.

For geometry regression, prefer summaries over exact WKT:

- feature counts by family;
- reference strings by family;
- area/length/elevation ranges with tolerances;
- layer/group presence;
- generated warning messages.

## Open Questions

- Which Annex 14 edition should `icao_annex14_current` target?
- Should NASF outputs remain enabled by default when a non-MOS aerodrome
  standard is selected?
- Should the UI split "Aerodrome Standard" and "Supplementary Frameworks" before
  the second ruleset ships, or can that wait until Phase 2?
- Do generated layers need a new generic reference field, or should `ref_mos`
  be retained with a generic companion field first?
- Should mixed-standard airports be supported, or should the selected aerodrome
  standard be airport-wide only?
- What is the first golden airport/runway scenario set for MOS139 regression?

## Phase 0 Exit Criteria

Phase 0 is complete when:

- this audit is reviewed and updated with stakeholder decisions;
- stable ruleset and framework IDs are accepted;
- the first additional ruleset scope is chosen;
- Phase 1 implementation tickets can be created without further architecture
  discovery.
