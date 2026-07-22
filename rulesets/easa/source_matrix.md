# EASA Source Matrix

**Status:** Working reference

**Target:** CS-ADR-DSN Issue 7, incorporated in the March 2026 Easy Access Rules

The code targets Issue 7. The former Issue 6 identifier is a compatibility alias
only. Capability status in `metadata.py` is authoritative; a verified numeric
value does not by itself make an entire generated-output family supported.

## Coverage

| Family | Primary source | Implementation status |
| --- | --- | --- |
| Runway classification | Internal adapter to NI/NPA/PA categories | Supported adapter |
| Runway strips | CS ADR-DSN.B.155, B.160, B.175 | Supported |
| RESA | CS ADR-DSN.C.210, C.215 | Supported |
| Pavement and shoulders | CS ADR-DSN.B.090, B.125, B.135 | Partial decision tree |
| Taxiway separations | CS ADR-DSN.D.260, Table D-1 | Supported |
| Parallel runways | CS ADR-DSN.B.050, B.055 | Partial profile capability |
| Conventional OLS and OFZ | CS ADR-DSN Chapters H/J, Tables J-1/J-2 | Values verified; generated contract partial |
| Outer horizontal surface | GM1 ADR-DSN.H.410 | Verified guidance-only values |
| Runway markings | CS ADR-DSN.L.530-L.575 | Values verified; profile capability partial |
| Approach and runway lighting | CS ADR-DSN.M.626-M.695 | Values verified; profile capability partial |
| Declared distances | CS ADR-DSN.B.035 | Supported calculation |
| Clearway | CS ADR-DSN.B.195 | Supported policy |
| Stopway | CS ADR-DSN.B.200 | Supported policy; polygon consolidation open |

## Retained Interpretations

- Precision CAT I obstacle free zone applicability is an explicit planning
  interpretation.
- The outer horizontal surface is guidance, not a Table J-1 certification
  surface.
- Threshold marking width, non-instrument aiming-point conspicuity, touchdown
  zone offsets, temporary displaced-threshold lighting, and selected lighting
  gauges contain documented representative or derived values.
- Runway-holding position geometry is not inferred from the marking-pattern
  clause alone; the current helper returns no fixed distance.
- Conditional and guidance values need a consistent designer-selection versus
  variance-assessment policy before those choices can be treated as broadly
  supported for internal planning.

## Internal-Use Confidence Checks

Before relying on a capability for an internal planning decision, confirm
table-level traceability for that capability, source-linked value tests,
representative QGIS UI validation, and an agreed interpretation policy. A formal
promotion package or independent sign-off is not required by default. See
[`docs/roadmap.md`](../../docs/roadmap.md).
