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
candidates and participate in controlling candidate, region, and
transition-boundary layers.

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
- Approach/TOCS and Conical polygons use one continuous shared equality edge,
  without detached wedges, slivers, or intervening gaps.

### 7. Performance and Output Hygiene

The engine should avoid dense sampled grids as a construction method. Sampling is
acceptable for QA diagnostics only.

Expected layers during development:

- candidate surface diagnostics;
- controlling regions;
- controlling edge network;
- clipped controlling contours;
- optional QA samples.

The output contract separates user-facing solved products from diagnostics:
solved regions and clipped contours are published under `Controlling Surfaces`,
while candidate surfaces and transition boundaries remain in
`99 Debug / Development`.

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

Status: implemented and locked for MOS139 controlling regions with planar,
transitional, and conical candidates. Modernised Annex 14 OFS/OES remains a
separate partial workflow.

The current implementation generates:

- user-facing solved controlling region polygons and clipped controlling
  contours for Approach, TOCS, Conical, and Transitional;
- diagnostic candidate surface and solved transition-boundary layers.

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

### Vertical Model Contract

Approach, TOCS, and Conical polygon outputs now carry the same explicit
vertical-model vocabulary used by the controlling candidate metadata:

- `vertical_model` identifies whether the feature is modelled by linear edge
  interpolation or as a constant elevation;
- `z_units` and `height_reference` describe the vertical unit and datum;
- `lower_edge_role`, `lower_edge_z_m`, `upper_edge_role`, and `upper_edge_z_m`
  identify the defining vertical edges;
- `surface_axis` describes how interpolation is measured in plan;
- `edge_elevation_source` records that the values were calculated by the
  generator.

The controlling engine still evaluates candidates from generated in-memory
models, not by re-reading exported GeoJSON. The shared fields are therefore an
audit contract: exported layers, candidate diagnostics, and solver metadata can
be compared directly when an edge case needs investigation. Future import-based
or file-based workflows should validate that these fields are present before
computing conical intersections.

For conical intersections with Approach and TOCS, the controlling engine now
supplements the existing analytical transition constructors with a sampled
zero-contour method. Over the 2D overlap of the conical footprint and the
axis-rising surface, it samples `z_axis - z_conical`, interpolates zero
crossings along grid-cell edges, and uses that curve as preferred linework for
the global cell solver and region splitting. The older analytical
axis-vs-conical curve remains as a fallback.

The preferred curve is smoothed before it is used for polygonization. An
endpoint-clamped cubic B-spline supplies a curvature-continuous guide, then its
interior vertices are projected back onto the axis/conical equality locus. The
guide is accepted selectively: peak and RMS curvature change must improve,
endpoints must remain fixed, symmetric displacement must remain within 0.5 m,
surface-equality residual must remain within 0.01 m, and topology/domain checks
must pass. Otherwise the projected unsmoothed zero contour remains authoritative.
This order is important: unconstrained 2D smoothing can create an attractive
line that is no longer an equal-elevation intersection.

An explicit `aggressive_least_squares_bspline_visual_trial` profile is
temporarily available for visual evaluation. It fits an endpoint-constrained
cubic B-spline to all ordered sampled-intersection vertices using substantially
fewer solved controls and a stronger control-fairing penalty. Full equality
projection was found to erase most visible influence from the fitted curve, so
this trial retains 75% of the fitted position and blends 25% towards the exact
equality root. The fitted curve is evaluated at 5 m spacing. Its deliberately
wide exploratory bounds are 4 m displacement and 0.10 m elevation-equality
residual, while endpoints remain exact and domain, simplicity and topology
checks still apply. The output transition extractor uses the same temporary
0.04 m observed-residual envelope so the intentionally approximate curve is
not split back into short fragments. The diagnostic transition layer retains
the fitted split edge instead of reprojecting a second display-only line, so it
remains coincident with the controlling polygons. This is an aggressive
inspection profile, not part of the accepted MOS139 compatibility lock.

The zero contour is the single construction boundary. The solver must not
subsequently triangulate the same MOS139 cell onto a different chord when the
sampled residual is within the bounded curved-surface allowance. Polygonized
MOS139 conical cells are retained down to 0.001 m²; discarding these small faces
previously produced a narrow gap which, when filled wholesale, became a false
Approach/Conical wedge. Both owning polygons now inherit the identical noded
curve. Adjacent diagnostic edge segments are line-merged by canonical
controller pair after region construction.

The accepted YBBN intersection had a measured equal-elevation residual between
approximately 0.00002 m and 0.00446 m along the reviewed shared edge. The same
construction was visually accepted for YSSY, YSWS, and YMML; YMML used
EPSG:32755, demonstrating that the metric projected-CRS implementation is not
tied to the EPSG:28356 fixture environment.

The accepted smoothed linework is relatively vertex-dense. A future performance
pass may test fewer spline samples or a bounded post-projection simplification,
but only if the existing equality, displacement, curvature, endpoint, topology,
and geometry-lock gates continue to pass.

No-OLS strip-core exclusion masks are applied before competition. These masks
suppress IHS, OHS, Approach, TOCS, and Transitional candidate footprints within
the runway strip core/lower-edge corridor where no OLS surface should be
apparent.

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
places where the solver can produce slivers, gaps, internal
seams, or invalid polygon artefacts.

The main safeguards are region polygon cleanup, coverage repair, local
lower-envelope repair for unexpected gaps, same-candidate region dissolves,
domain clipping for computed lower regions, explicit unresolved axis/conical
handling, polygon-part normalisation, ring despiking, minimum-area filtering,
and transition-edge de-duplication. Outstanding cleanup and hardening items are
tracked centrally in `docs/TODO.md`.

Known remaining limitations:

- transition-edge diagnostics remain secondary to the locked MOS139 region
  layer; modernised Annex 14 topology and promotion remain separate work.

### Contour Clipping Checkpoint

Contour clipping is implemented for the solved controlling regions.
Approach, TOCS, Conical, and Transitional source contours carry/register the
same stable `surface_id` used by their controlling candidate surface. The
contour output clips each registered contour to the solved region for its
matching parent surface and emits only the retained contour geometry. Retained
parts from the same source contour are collected into one multipart feature so
labels are not repeated along region-boundary fragments.

Transitional contours now use the generated transitional panel `surface_id`,
including strip-adjacent lower/upper edges, strip interval contours,
approach-adjacent lower/upper edges, and approach-adjacent interval contours.
Because transitional lower/top contours can lie exactly on no-OLS strip-core or
IHS/equality boundaries, the clipping pass uses a small spatial tolerance for
Transitional contours before intersecting them with the matching controlling
region. This keeps legitimate shared-edge contours from disappearing due to
polygon-boundary precision effects.

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
