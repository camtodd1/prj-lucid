# EASA CS-ADR-DSN Ruleset

**Status:** Current

**Profile:** `easa_cs_adr_dsn_issue_7` (`draft`)

This package implements a draft EASA CS-ADR-DSN Issue 7 design-standard
profile. It is selectable for preview and validation, but its conventional and
controlling OLS capabilities remain `partial` until the source, topology,
performance, interpretation, and independent-review gates are complete.

## Capability Summary

Supported policy services include runway strips, RESA, clearway, stopway,
taxiway separation, and calculated declared distances. Pavement, shoulders,
parallel-runway separation, OLS, markings, and lighting contain verified values
but remain partial at the profile level because applicability or geometry is
not yet a complete operational contract.

The EASA OLS path uses CS-ADR-DSN J-1/J-2 dimensions, clearway-dependent take-off
climb origins and widths, obstacle free zone families, and guidance-only outer
horizontal surface provenance without MOS139 parameter fallbacks.

## Module Ownership

- `metadata.py` owns identifiers and capability declarations.
- `profile.py` exposes the shared ruleset facade.
- `classification.py` maps dialog runway types to policy categories.
- `physical_data.py`, `taxiway.py`, `ols_surfaces.py`, `markings.py`, and
  `lighting.py` own domain policy and source metadata.
- `ols.py` is a compatibility wrapper around `ols_surfaces.py`.

[`source_matrix.md`](source_matrix.md) records the verification state and known
interpretations. Remaining promotion work is tracked in
[`docs/roadmap.md`](../../docs/roadmap.md).
