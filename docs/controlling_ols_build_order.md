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

## Planar And Conical Milestone Status

Status: validated as a proof-of-concept for controlling regions with planar,
transitional, and conical candidates.

The current implementation generates a derived `Controlling OLS POC` output
group containing:

- candidate surface diagnostics;
- solved controlling planar region polygons;
- solved controlling transition edge diagnostics.

The controlling lower-envelope model currently includes:

- IHS constant planes;
- OHS constant planes;
- Approach axis-rising planar sections;
- TOCS axis-rising planar surfaces;
- Transitional strip-adjacent and approach-adjacent planar panels;
- Conical distance-rising surfaces from the IHS footprint.

The solver treats all registered candidates from all runways as one
airport-wide competition set. For each candidate, its controlling region is
constructed by subtracting the parts of its footprint where any other
applicable candidate is lower. The equality boundary between two planar
candidates is represented as a half-plane split, so planar interactions are
constructed exactly rather than by a sampled grid.

Conical has been reintroduced as a non-planar candidate. Its evaluator derives
elevation from horizontal distance to the IHS footprint. Conical-vs-flat
interactions are clipped by exact distance buffers. Conical-vs-sloping planar
interactions are clipped as a local elevation-equality problem. For
axis-rising surfaces such as Approach and TOCS, the solver resolves the
conical intersection along the surface stationing so the equality edge is
placed at the correct height rather than approximated as a single constant
offset. This avoids treating a sloping-plane/conical intersection as a simple
buffer, which is not geometrically correct and can round planar corners or
place the equality edge at the wrong height.

No-OLS strip-core exclusion masks are applied to runway-related planar
candidates before competition. These masks suppress IHS, Approach, TOCS, and
Transitional candidate footprints within the runway strip core/lower-edge
corridor where no OLS surface should be apparent. OHS is intentionally not
masked by these strip-core exclusions, so it can remain the controlling
airport-wide surface where no lower runway-related candidate applies.

The planar region output now includes a stable `region_id` attribute for
diagnostic labelling and GeoJSON review. The region layer uses the
`test_ols_polygon.qml` style during development.

### Current Checkpoint

The current checkpoint confirms the following behaviours on tested runway
configurations:

- conical intersections with Approach/TOCS planar regions align with the
  expected equality boundary from the candidate geometry;
- conical regions are clipped away where an axis-rising surface is lower, and
  axis-rising surfaces are clipped away where conical is lower;
- no-OLS runway strip/lower-edge exclusions do not leave empty volumes inside
  the represented OLS array;
- repaired coverage gaps are resolved by a local lower-envelope pass, not by
  assigning an entire gap to a single sampled candidate;
- adjacent fragments belonging to the same candidate are dissolved before
  output so same-surface seams do not become transition-edge artefacts;
- transition-edge diagnostics are generated from the solved controlling region
  boundaries and are expected to omit same-surface internal seams.

Several implementation details are important to preserve this behaviour:

- `None` from a comparison means unresolved/unknown and should usually retain
  the candidate to avoid accidental holes;
- an empty `QgsGeometry()` means the comparison was resolved and the candidate
  is known to lose the overlap;
- conical-vs-axis comparisons must return explicit empty geometry when conical
  has no lower area, otherwise conical remnants can survive incorrectly;
- unresolved axis-vs-conical comparisons are clipped from the axis candidate,
  with coverage repair filling any true gaps from the lower-envelope result;
- coverage repair must partition gaps by candidate competition, otherwise a
  repaired sliver can erase valid Approach-vs-Approach boundaries.

### Geometry Defenders

The current engine contains several post-construction geometry defenders. These
are deliberate safeguards around QGIS/GEOS overlay behaviour and around known
places where the proof-of-concept solver can produce slivers, gaps, internal
seams, or invalid polygon artefacts. They are useful for the milestone, but
should be treated as revisit points for future root-cause cleanup.

In `PlanarControllingOlsEngine._controlling_region_geometries`:

- `_clean_region_polygon_parts(...)` is applied to each solved region before it
  is emitted. This is the main final-shape cleanup pass for region polygons.
  It tries to preserve solved boundaries while removing zero-width spikes,
  validating geometry, extracting polygon parts, and only falling back to
  `buffer(0)` if less invasive cleanup fails. Revisit goal: reduce the need for
  ring despiking and fallback buffering by preventing invalid or out-and-back
  rings during subtraction.
- `_repair_region_coverage(...)` runs after the first lower-envelope solve. It
  compares the union of candidate footprints with the union of solved regions
  and identifies unexpected gaps. Revisit goal: determine why any gap is
  produced by the primary solve rather than accepting gap repair as permanent
  behaviour.
- `_gap_lower_envelope_parts(...)` fills each detected gap by rerunning a local
  lower-envelope competition inside the gap. This replaced an earlier
  sample-point assignment because a repaired sliver can cross a valid
  candidate boundary, especially between opposing Approach surfaces. Revisit
  goal: make the primary region solve complete enough that local gap solving is
  no longer required.
- `_merge_region_parts_by_candidate(...)` dissolves adjacent solved fragments
  for the same `surface_id` after coverage repair. This suppresses same-surface
  seams and prevents repaired fragments from appearing as zero-volume transition
  rings. Revisit goal: avoid creating same-candidate fragments that need a
  later dissolve, or make the dissolve an explicit output-normalisation step
  rather than a geometry workaround.

In lower-region comparison handling:

- `_clip_lower_region_to_overlap(...)` clips every computed lower region back
  to the actual candidate/competitor overlap before subtraction. This prevents
  broad half-plane or helper geometries from removing area outside the current
  comparison domain. Revisit goal: keep comparison constructors domain-limited
  enough that this remains a safety check, not a corrective step.
- `_unresolved_comparison_removes_candidate(...)` handles a specific
  axis-vs-conical failure mode. If an axis candidate cannot resolve its
  comparison against conical, the unresolved overlap is clipped from the axis
  candidate and left for coverage repair/local lower-envelope resolution.
  Revisit goal: make axis/conical comparison complete enough that unresolved
  axis-vs-conical overlaps disappear from diagnostics.
- `_axis_conical_lower_region(...)` must return an explicit empty
  `QgsGeometry()` when conical has no lower area against an axis surface. This
  is a semantic defender: `None` means unknown/retain, while an empty geometry
  means known loser/remove. Revisit goal: keep this distinction documented and
  covered by tests so future geometry fixes do not reintroduce conical remnants.

In geometry extraction and validity helpers:

- `_polygon_parts(...)` normalises polygon, multipolygon, and geometry
  collection results into usable polygon parts, calling `makeValid()` where
  needed. Revisit goal: reduce geometry collections from upstream overlay
  operations where practical.
- `_despiked_polygon_geometry(...)` and `_despiked_ring(...)` remove
  zero-width out-and-back ring spikes without using rounded buffers. Revisit
  goal: identify which overlay operations introduce ring spikes and prevent
  them before final cleanup.
- `_has_polygon_area(...)` applies a minimum-area test before regions,
  repaired parts, and transition inputs are accepted. Revisit goal: decide
  whether the current area thresholds are numerical tolerances or should become
  configurable QA parameters.

In output hygiene:

- `region_boundary_features(...)` and `_legacy_shared_boundary_features(...)`
  suppress same-`surface_id` transition edges. Revisit goal: ensure transition
  diagnostics represent only real controller changes, not internal boundaries
  created by region fragmentation.
- `_deduplicate_controlling_transition_features(...)` removes repeated
  transition line features by adjacent-surface key and WKT. Revisit goal:
  replace WKT-based deduplication with a more explicit topology/keying strategy
  if transition diagnostics become a promoted output.

Known remaining limitations:

- transition-edge diagnostics remain secondary to the region layer and should
  be rechecked as contour clipping and any promoted transition outputs are
  introduced;
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
it should be treated as a bug or as evidence that a required surface
interaction is not yet represented in the competition.

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
