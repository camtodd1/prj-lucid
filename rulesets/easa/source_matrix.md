# EASA Source Matrix

**Status:** Working reference

**Target:** CS-ADR-DSN Issue 7, incorporated in the March 2026 Easy Access Rules

The code targets Issue 7. The former Issue 6 identifier is a compatibility alias
only. The supplied Issue 6 Chapter H/J PDF is recorded in
`tests/fixtures/ols/source_validation_v1.json` by filename, scope, and SHA-256;
EASA's [Issue 7 change information](https://www.easa.europa.eu/sites/default/files/dfu/change_information_-_cs-adr-dsn_issue_7.pdf)
lists changes to L/Q/R provisions rather than Chapters H/J. Capability status in
`metadata.py` is authoritative; a verified numeric value does not by itself make
an entire generated-output family supported.

## Coverage

| Family | Primary source | Implementation status |
| --- | --- | --- |
| Runway classification | Internal adapter to NI/NPA/PA categories | Supported adapter |
| Runway strips | CS ADR-DSN.B.155, B.160, B.175 | Supported |
| RESA | CS ADR-DSN.C.210, C.215 | Supported |
| Pavement and shoulders | CS ADR-DSN.B.090, B.125, B.135 | Partial decision tree |
| Taxiway separations | CS ADR-DSN.D.260, Table D-1 | Supported |
| Parallel runways | CS ADR-DSN.B.050, B.055 | Partial profile capability |
| Airport-wide OLS | CS ADR-DSN.H.415, H.420, H.430; CS ADR-DSN.J.470-J.480, Table J-1 | Supported for source-referenced IHS, conical, and transitional output using the conservative composite runway footprint; the optional outer horizontal surface remains guidance-only under GM1 H.410 |
| Obstacle-free zone (OFZ) | CS ADR-DSN.H.445, H.450-H.460; CS ADR-DSN.J.480, Table J-1 | Supported for the mandatory Category II/III inner approach, inner transitional, and balked landing family; Category I inner-surface output is retained as an explicit GM1 J.480(a) guidance-only caveat |
| Controlling lower envelope | Derived from source-backed Chapter H/J candidate surfaces | Partial generated contract; OFZ candidate inclusion and broader controlling-output evidence are still open |
| Runway approach surfaces | CS ADR-DSN.J.470-J.480, Table J-1 | Supported for aligned generated sections, variable-length horizontal resolution against the inner horizontal surface, and source-referenced QGIS geometry; nominated-track and wider promotion scope remains subject to the shared OLS contract |
| Take-off climb surface | CS ADR-DSN.J.485, Table J-2 | Supported for source-backed aligned, clearway-origin, and greater-than-15-degree heading-change cases with source-referenced QGIS geometry; reduced-slope guidance remains outside the advertised contract |
| Outer horizontal surface | GM1 ADR-DSN.H.410 | Verified guidance-only values |
| Runway markings | CS ADR-DSN.L.530-L.575 | Supported for runway centreline, threshold, aiming-point, touchdown-zone, and generated runway marking policy; source-backed applicability tests cover code-number and LDA bands. Runway-holding-position distance remains intentionally ungenerated because CS ADR-DSN.D.335, not Chapter L, determines its location. |
| Approach and runway lighting | CS ADR-DSN.M.626-M.695, M.705 | Supported for simple/CAT I/CAT II-III approach systems and runway edge, threshold, end, centreline, touchdown-zone, and stopway light policy; source-backed spacing, count, profile, and applicability tests are locked in `tests/fixtures/ols/easa_visual_aids_v1.json`. RETIL and temporary displaced-threshold options remain compatibility-only and are labelled accordingly. |
| Declared distances | CS ADR-DSN.B.035 | Supported calculation |
| Clearway | CS ADR-DSN.B.195 | Supported policy |
| Stopway | CS ADR-DSN.B.200 | Supported policy; polygon consolidation open |

## Retained Interpretations

- Category II/III OFZ applicability follows CS ADR-DSN.H.445. Category I inner
  approach, inner transitional, and balked landing parameters are retained as
  guidance-only output under GM1 ADR-DSN.J.480(a), not as mandatory OFZ output.
- The outer horizontal surface is guidance, not a Table J-1 certification
  surface.
- Threshold marking width, non-instrument aiming-point conspicuity, touchdown
  zone offsets, temporary displaced-threshold lighting, and selected lighting
  gauges contain documented representative or derived values.
- Runway-holding position geometry is not inferred from the marking-pattern
  clause alone; the current helper returns no fixed distance.
- Conditional and guidance values need a consistent designer-selection versus
  variance-assessment policy before the profile can be promoted.

## Promotion Gate

Promotion requires table-level traceability for every advertised capability,
tests that assert source references as well as values, representative QGIS UI
validation, and an agreed interpretation policy. See
[`docs/roadmap.md`](../../docs/roadmap.md).
