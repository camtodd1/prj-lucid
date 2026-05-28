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
