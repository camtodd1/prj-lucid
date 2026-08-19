# EASA CS-ADR-DSN Ruleset

**Status:** Current

**Profile:** `easa_cs_adr_dsn_issue_7` (`draft`)

This package implements a draft EASA CS-ADR-DSN Issue 7 design-standard
profile. Its conventional and controlling OLS capabilities are supported.
The overall profile remains draft while the partial pavement/shoulder and
parallel-runway-separation capabilities are completed.

## Capability Summary

Supported policy services include runway strips, RESA, clearway, stopway,
taxiway separation, calculated declared distances, runway markings, runway
lighting, and approach lighting. The visual-aid capability is supported for
the runway and approach families implemented by `markings.py` and `lighting.py`;
optional compatibility-only displaced-threshold lighting remains explicitly
identified in traceability metadata.

The EASA OLS path uses CS-ADR-DSN J-1/J-2 dimensions, clearway-dependent take-off
climb origins and widths, obstacle free zone families, and guidance-only outer
horizontal surface provenance without MOS139 parameter fallbacks. Runway approach,
take-off climb, airport-wide OLS, and the mandatory Category II/III OFZ family are
supported for the source-backed cases covered by the shared geometry contract.
Category I inner-surface output is labelled guidance-only under GM1 J.480(a).
Required Category II/III OFZ surfaces participate in the derived controlling lower
envelope. Representative EASA evidence now covers EHTE Code 2B NI/NPA with a
modernised Annex 14 comparison, EHAM Code 4F CAT II/III, EHRD Code 4C CAT I,
and EGLL dual-parallel Code 4F CAT II/III workflows under strict topology,
determinism, and performance gates. Independent technical review has passed;
the controlling lower-envelope capability is supported.

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
