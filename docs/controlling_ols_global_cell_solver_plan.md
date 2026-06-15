# Controlling OLS Global Cell Solver Plan

## Objective

Generate controlling OLS regions by constructing one airport-wide partition of
all candidate surface domains, then labelling each atomic cell with the lowest
applicable surface.

This replaces the current primary region-construction strategy of solving each
candidate independently and subtracting losing overlaps pair-by-pair. The
candidate model remains useful: every surface still contributes a stable
`surface_id`, footprint, metadata, and `z(x, y)` elevation evaluator.

## Why Change

The YMEN failure case shows that per-candidate subtraction creates persistent
same-surface fragmentation. The source OHS candidate is one polygon, but the
solved OHS controlling region becomes a multipart geometry with false internal
seams. Similar fragmentation appears across TOCS, Approach, Conical, and
Transitional outputs.

Post-process dissolves are not a robust fix. They either fail to remove topology
artefacts or require buffer-based welding that moves regulatory boundaries.

## Method

1. Build effective candidate footprints, including no-OLS exclusion masks.
2. Add construction linework:
   - effective candidate footprint boundaries;
   - no-OLS/exclusion boundaries as part of those footprints;
   - exact plane/plane equality lines;
   - exact conical/flat equality boundaries;
   - axis/conical equality curves for Approach/TOCS versus Conical;
   - fallback lower-region boundaries for pair types without a first-class
     equality constructor.
3. Polygonize the complete linework into atomic cells.
4. For each cell, evaluate all candidate surfaces applicable at a representative
   point.
5. Assign the cell to the lowest candidate, with the existing stable order
   acting as the temporary tie-break.
6. Dissolve cells by `surface_id`.
7. Derive transition diagnostics from labelled cell adjacency or solved region
   boundaries.
8. Clip source contours by the solved controlling regions as before.

## Acceptance Checks

- Candidate footprints remain traceable through `surface_id`.
- Existing footprint/no-OLS boundaries are preserved, not moved by buffers.
- Plane/plane boundaries are straight equality lines.
- Approach/TOCS versus Conical boundaries use generated equality curves rather
  than a fixed conical offset.
- Same-controller internal seams are not present in the controlling region
  geometry.
- OHS does not backfill no-OLS runway strip-core exclusions.
- The existing pairwise solver remains available as a fallback until the global
  solver is validated across representative aerodromes.

