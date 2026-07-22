# Documentation

This directory contains maintained implementation references for Safeguarding
Builder. The code and capability declarations remain authoritative when prose
and implementation disagree.

## Current References

| Document | Purpose |
| --- | --- |
| [`roadmap.md`](roadmap.md) | Active, incomplete work only |
| [`airfield_ground_lighting_rules.md`](airfield_ground_lighting_rules.md) | MOS139 AGL rules, assumptions, and known gaps |
| [`declared_distances_inputs.md`](declared_distances_inputs.md) | Current declared-distance model and validation |
| [`ols_modernisation_comparison.md`](ols_modernisation_comparison.md) | Baseline/comparison OLS behavior and output semantics |
| [`runway_marking_matrix.md`](runway_marking_matrix.md) | MOS139 runway-marking rules and implementation coverage |
| [`safeguarding_standardisation_matrix.md`](safeguarding_standardisation_matrix.md) | Cross-jurisdiction safeguarding taxonomy |
| [`qgis_field_name_mapping.csv`](qgis_field_name_mapping.csv) | Legacy-to-current QGIS field-name mapping |
| [`templates/test-input-template.json`](templates/test-input-template.json) | Complete placeholder template for sourcing regression inputs |

Ruleset-specific documentation lives with its implementation:

- [`rulesets/mos139/README.md`](../rulesets/mos139/README.md)
- [`rulesets/easa/README.md`](../rulesets/easa/README.md)
- [`rulesets/cap168/README.md`](../rulesets/cap168/README.md)
- [`rulesets/annex14/README.md`](../rulesets/annex14/README.md)

Test commands and fixture contracts live in [`tests/README.md`](../tests/README.md)
and [`tests/fixtures/ols/README.md`](../tests/fixtures/ols/README.md). Runtime
history is data, not narrative documentation; its schema is described in the
root [`README.md`](../README.md).

## Status Convention

Maintained reference documents begin with a short status line:

- **Current**: describes implemented behavior and must change with the code.
- **Working reference**: mixes implemented behavior with explicitly identified
  open decisions.
- **Roadmap**: contains incomplete work only.

Dated test evidence belongs in versioned fixtures or dated implementation notes,
not in the maintained documentation set. Completed plans and checklists should
be removed; Git history preserves them.

## Markdown and Notation

Use these conventions for new and edited documentation:

- Use one `#` heading, ATX headings, fenced code blocks, and tables with aligned
  header delimiters.
- Use title case for headings and wrap prose at approximately 80 characters.
- Use repository-relative Markdown links. Put file names, identifiers, commands,
  environment variables, field names, and literal values in backticks.
- Use ISO 8601 dates (`2026-07-16`) where a machine-readable date is needed;
  use an unambiguous written date (`16 July 2026`) in prose.
- Use SI notation with a space between value and unit: `150 m`, `0.5 m²`,
  `2.5%`. Use British/Australian spelling, including *metre* and *modernised*.
- Use `MOS139`, `CAP 168`, `CS-ADR-DSN`, `OLS`, `OFS/OES`, `OFZ`, `TOCS`,
  `IHS`, and `OHS` consistently. Expand an uncommon acronym on first use.
- Use *ruleset* for an aerodrome design standard implementation and
  *framework* for supplementary safeguarding policy such as NASF.
- Mark open work only in [`roadmap.md`](roadmap.md). Reference documents may
  identify a limitation, but should link to the corresponding roadmap item
  instead of maintaining a second checklist.

The repository-level [`.markdownlint.json`](../.markdownlint.json) records the
enforceable Markdown defaults. Generated files and extracted source material
are outside the prose style contract.
