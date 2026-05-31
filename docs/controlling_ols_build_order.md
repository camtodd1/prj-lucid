# Controlling OLS Build Order

This document records the proposed build order for a new controlling OLS engine.
The existing comprehensive OLS generation remains in place. The new work should
reuse existing MOS dimensions, runway processing, layer styles, naming
conventions, and contour generation where practical. The construction strategy
changes: controlling OLS is treated as a 3D lower-envelope problem rather than a
post-process over independent 2D plan-view polygons.

## Objective

Create a derived controlling OLS product that identifies only the most limiting
applicable surface at each location.

The target outputs are:

- controlling regions: polygons where a single candidate surface controls;
- controlling edge network: exact boundaries between controlling regions;
- controlling contours: existing/current contour geometry clipped to the regions
  where the parent surface controls.

## Non-Goals

The first implementation should not rewrite the existing comprehensive OLS
generation. It should not replace current MOS parameter handling, styling, UI
inputs, runway preprocessing, or existing individual surface outputs.

The controlling engine should initially be a separate derived model so that it
can be validated against known-good outputs without destabilising production OLS
generation.

## Core Model

Each candidate surface should be represented as a canonical 3D object:

- `surface_id`;
- `surface_type`;
- source runway/end/side/segment metadata where applicable;
- 2D domain/footprint;
- elevation evaluator `z(x, y)`;
- boundary curves;
- parentage for contour clipping.

All runway-derived candidates from all runways enter the same solve. Intersecting
or converging runway cases should therefore be normal lower-envelope competition,
not a separate special-case overlay workflow.

## Build Order

### 1. Candidate Surface Model

Create the controlling-engine data structures without changing existing output.

Initial surface families:

- IHS: constant elevation plane;
- OHS: constant elevation plane;
- Approach: axis-rising planar sections;
- TOCS: axis-rising planar surfaces;
- Transitional: lateral rising planes or ruled planar pieces;
- Conical: radial rising surface, added after planar cases are stable.

Acceptance criteria:

- candidate IDs are stable and traceable;
- each candidate can answer `contains_xy(point)` and `z(point)`;
- candidates retain enough metadata to link existing contours back to their
  parent surface.

### 2. Flat and Axis-Plane Lower Envelope

Implement exact lower-envelope logic for the simplest planar cases:

- Approach vs IHS;
- Approach vs OHS;
- TOCS vs IHS;
- TOCS vs OHS;
- Approach vs TOCS;
- Approach vs Approach;
- TOCS vs TOCS.

Flat/axis interactions should produce exact straight equality lines. For
example, Approach/IHS is a direct clip where the approach elevation crosses the
flat IHS elevation.

Acceptance criteria:

- approach geometry above IHS is not retained as controlling inside the IHS
  domain;
- approach/IHS and TOCS/IHS transition edges are present where expected;
- output regions and edge network match known-good planar interactions before
  conical complexity is introduced.

### 3. Transitional Surfaces

Add transitional candidates before declaring the planar engine complete.

Implementation status: initial integration complete. Generated transitional
strip-adjacent and approach-adjacent panels are registered as generic planar
candidates and participate in the Controlling OLS POC candidate, region, and
transition-edge layers.

Transitional surfaces must include:

- runway-side transitional pieces;
- approach-side transitional pieces where applicable;
- candidates from all runways;
- interactions from converging or intersecting runways.

Acceptance criteria:

- overlapping transitional surfaces compete by elevation;
- lower transitional surface controls where transitional surfaces overlap;
- transitional joins are split at real controlling boundaries;
- transitional contours can be clipped cleanly by controlling regions.

### 4. Controlling Regions and Edge Network

Generate the first primary outputs:

- controlling region polygons;
- controlling edge network as linework with Z values;
- diagnostic attribution fields, including controlling `surface_id`,
  adjacent/competing surface IDs, and construction method.

Acceptance criteria:

- no region is attributed to a surface that is above another applicable surface
  at representative test points;
- edge network aligns with known-good outlines for planar and transitional
  cases;
- diagnostics explain every retained edge.

### 5. Contour Clipping

Reuse existing contour generation where practical. The controlling engine should
not initially rebuild all contour geometry.

Workflow:

- generate candidate contours per source surface as currently done;
- carry parent `surface_id` on contour features;
- clip each contour to the controlling region for the matching parent surface;
- split contours at controlling region boundaries;
- retain only contour segments where the parent surface controls.

Transitional contours require special attention: where transitional surfaces
from converging or intersecting runways overlap, contour segments must terminate
or continue according to the controlling transitional region.

Acceptance criteria:

- clipped contours match known-good contour extents;
- transitional contours intersect and terminate at controlling region edges;
- contours do not appear where their parent surface is above another applicable
  surface.

### 6. Conical Surface

Add conical after the planar and transitional engine is stable.

Conical interactions introduce curved equality boundaries and radial distance
logic, so they should not be the first proof point for the engine.

Acceptance criteria:

- conical controls only where it is lower than IHS/OHS/approach/TOCS/
  transitional candidates;
- conical contours clip correctly against all lower controlling regions;
- known conical alignment issues are tracked separately from controlling logic.

### 7. Performance and Output Hygiene

The engine should avoid dense sampled grids as a construction method. Sampling is
acceptable for QA diagnostics only.

Expected layers during development:

- candidate surface diagnostics;
- controlling regions;
- controlling edge network;
- clipped controlling contours;
- optional QA samples.

All development outputs should remain under a dedicated `Controlling OLS POC`
group until promoted.

## First Implementation Target

The first useful milestone is:

- IHS + OHS + Approach + TOCS;
- exact flat/axis and axis/axis transitions;
- controlling regions and edge network;
- no conical;
- no contour clipping except optional manual QA.

Once this matches known-good planar behaviour, add transitional surfaces as the
next milestone.

## Planar Milestone Status

Status: validated as a proof-of-concept for planar controlling regions.

The current implementation generates a derived `Controlling OLS POC` output
group containing:

- candidate surface diagnostics;
- solved controlling planar region polygons;
- solved controlling transition edge diagnostics.

The planar lower-envelope model currently includes:

- IHS constant planes;
- OHS constant planes;
- Approach axis-rising planar sections;
- TOCS axis-rising planar surfaces;
- Transitional strip-adjacent and approach-adjacent planar panels.

The solver treats all registered planar candidates from all runways as one
airport-wide competition set. For each candidate, its controlling region is
constructed by subtracting the parts of its footprint where any other
applicable planar candidate is lower. The equality boundary between two planar
candidates is represented as a half-plane split, so planar interactions are
constructed exactly rather than by a sampled grid.

No-OLS strip-core exclusion masks are applied to runway-related planar
candidates before competition. These masks suppress IHS, Approach, TOCS, and
Transitional candidate footprints within the runway strip core/lower-edge
corridor where no OLS surface should be apparent. OHS is intentionally not
masked by these strip-core exclusions, so it can remain the controlling
airport-wide surface where no lower runway-related candidate applies.

The planar region output now includes a stable `region_id` attribute for
diagnostic labelling and GeoJSON review. The region layer uses the
`test_ols_polygon.qml` style during development.

Known remaining limitations:

- curved lower-edge boundaries are not yet modelled;
- conical is not yet part of the lower-envelope competition;
- transition-edge diagnostics are secondary to the region layer and may still
  need output hygiene as curved boundaries are introduced;
- contour clipping is still a later milestone.

### Current Non-Overlap Expectation

Within the planar model, solved region features are expected to be mutually
exclusive in plan view for areas where the candidate footprints and no-OLS
exclusions have been represented correctly. A point should not normally belong
to two different controlling region polygons in the output layer.

Small numerical artefacts can still occur at boundaries because QGIS/GEOS
overlay operations work with finite precision. These should be limited to
coincident boundaries, tiny slivers, or duplicate-looking linework rather than
meaningful overlapping area.

There are also intentional equal-elevation/tie cases. The current engine sorts
candidate evaluations by elevation and keeps the first candidate where surfaces
are equal within tolerance, so ties should resolve to one retained region rather
than overlapping duplicate regions. If meaningful polygon overlap is observed,
it should be treated as a bug or as evidence that a missing surface model, such
as curved lower edges or conical, is not yet represented in the competition.

### Equal-Elevation Tie Handling

Equal-elevation overlaps are currently resolved implicitly by candidate
registration order. Python sorting is stable, so where two or more candidates
evaluate to the same elevation within tolerance, the candidate that entered the
engine first is retained as the controlling region and later equal candidates
are suppressed.

This keeps the output layer non-overlapping, but it is not yet an explicit MOS
or domain-priority rule. The behaviour is deterministic for a given generation
run, but the selected surface may change if candidate registration order changes.

Future work should consider an explicit tie-break policy, for example:

- prefer the surface family with the more specific regulatory role;
- prefer runway-specific surfaces over airport-wide surfaces;
- prefer a stable configured surface-type priority order;
- mark true equal-elevation areas with a diagnostic tie flag.

Until that policy is defined, broad equal-elevation overlaps should be reviewed
as a potential modelling decision rather than assumed to be fully resolved.
