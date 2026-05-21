# TODO

## Placeholder Guidelines

- [ ] Implement Guideline A aircraft noise generation.

  Notes:
  - `guidelines/simple.py` currently logs Guideline A as not implemented.
  - Top-level Guideline A groups are treated as expected empty placeholders.
  - `README.md` documents Guideline A as placeholder-only.

- [ ] Implement Guideline H generation.

  Notes:
  - Top-level Guideline H groups are treated as expected empty placeholders.
  - `README.md` documents Guideline H as placeholder-only.

## Airfield Ground Lighting Generation

- [ ] Add optional Airfield Ground Lighting (AGL) generation.

  Scope:
  - Add an additional UI dialog tab for AGL inputs.
  - Capture additional AGL parameters per runway end.
  - Make AGL generation opt-in so default runs avoid the extra processing cost.
  - Keep generation logic separate from existing Guideline E lighting control zones unless shared helpers are genuinely useful.
  - Include generated AGL layers in the normal output/grouping/style workflow when enabled.

## Declared Distances And Stopways

- [ ] Add stopway geometry generation.

  Notes:
  - Runway summaries currently warn when stopway length contributes to ASDA but no `Stopway` features are generated.
  - Keep generated stopway layers in the normal physical geometry output/grouping/style workflow.

- [ ] Add validation warnings for inconsistent declared-distance results.

  Source:
  - Remaining item in `docs/declared_distances_inputs.md`.

- [ ] Add optional declared-distance override fields.

  Source:
  - Remaining item in `docs/declared_distances_inputs.md`.

- [ ] Feed declared-distance outputs into the runway summary report.

  Source:
  - Remaining item in `docs/declared_distances_inputs.md`.

## CNS Safeguarding

- [ ] Replace CNS `HeightRule = "TBD"` values with implemented height logic.

  Notes:
  - `dimensions/cns_dimensions.py` still has `TBD` height rules across CNS facility definitions.
  - `guidelines/simple.py` currently skips or warns for unimplemented CNS slope height rules.
