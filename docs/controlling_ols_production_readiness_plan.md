Controlling OLS Production-Readiness Plan
Review Findings
The global cell solver is the correct production foundation, but it still labels/refines cells partly through sampling and relies on downstream gap repair.
All four regression cases pass, but each activates final partition repair. Restored areas range from about 1.23 m² to 164.29 m²; production promotion should not permit unexplained repair.
Transition boundaries are deduplicated using rounded coordinate keys and controller probes rather than explicit cell adjacency.
Region and comparison processing still uses makeValid(), buffer(0), spike removal and residual repair in several normal paths.
Comparison outputs are internally consistent, but small residual gaps remain, reaching approximately 0.011 m² in the current matrix.
Existing fixtures verify generated-output invariants but do not independently establish expected elevation or controlling-surface identity.
MOS139 and modernised Annex 14 tables contain useful citations, but some assumptions, footnotes and applicability rules still need formal traceability and independent review.
Implementation Plan
1. Add production diagnostics before changing geometry
Introduce structured solver and comparison diagnostics recording:unassigned/refined cells;
unresolved candidate comparisons;
approximation methods and error bounds;
invalid input/output geometry;
gap and overlap areas;
repair/fallback activation counts and affected areas;
controller and feature determinism.

Include diagnostics in the regression JSON and concise QGIS logs.
Preserve current geometry during this tranche to establish an attributable pre-hardening baseline.
Classify each defensive operation as:canonical, accuracy-preserving normalisation;
bounded curved-surface approximation;
exceptional recovery repair.

Production fixtures must fail if an exceptional recovery repair activates.
2. Make the global subdivision the sole production solver
Build one noded subdivision from candidate footprints and every applicable pairwise equality boundary.
Use exact boundaries for constant, plane and affine-axis combinations.
Use adaptive, error-bounded isolines for axis/conical and other curved combinations. Treat these as supported approximations only when their horizontal and vertical residual limits pass.
Label each cell with the controlling candidate and validate controller consistency at vertices, edge midpoints and interior checkpoints.
Recursively subdivide inconsistent cells; do not pass them to local gap filling.
Remove the pairwise subtract solver from the production path once the complete fixture matrix passes. Retain it temporarily as a diagnostic comparison implementation.
Make same-controller merging canonical, adjacency-based and area-preserving. Multipart output is acceptable; snapping or buffering must not be used merely to force a single polygon.
Eliminate normal-path _repair_region_coverage() and final partition gap repair after subdivision completeness is proven.
3. Derive topology products from adjacency
Construct a cell-adjacency graph keyed by stable cell and candidate identifiers.
Generate controlling transition boundaries from shared edges between differently controlled adjacent cells.
Remove rounded-coordinate transition deduplication and across-edge sampling from the authoritative path.
Keep baseline controlling transition boundaries diagnostic for the first production release.
Clip contours against final controlling regions using exact intersection; boundary tolerance may be used for QA classification, not to expand the retained geometry.
Enforce valid regions, no unexplained holes, no cross-controller overlap and complete candidate-domain coverage.
4. Rebuild comparison partitioning on hardened envelopes
Intersect final baseline and future controller cells to create one controller-pair subdivision of the common domain.
Split affine controller pairs exactly at the zero-height line.
Split curved pairs using the same adaptive error-bounded mechanism as the controlling solver.
Preserve the current semantic rule: a tolerance can classify an entirely equivalent pair as no-change but must not create a polygon strip around a genuine crossing.
Derive gain, loss, no-change, baseline-only and equal-height transition outputs from this single subdivision.
Remove post-classification spike removal and repeated gap/overlap repair once the partition is complete by construction.
Generate signed contours from the same controller-pair elevation functions and clip them to their owning comparison cells.
5. Establish source-backed validation
Promote MOS139 first; validate modernised Annex 14 OFS/OES and comparison separately afterward.
Create a machine-readable source-validation manifest containing:ruleset and source edition;
paragraph, table and note citations;
applicability conditions;
input assumptions;
independently calculated checkpoints, cross-sections and intersections;
expected controller identity and elevation;
tolerances, derivation reference and reviewer sign-off.

Complete MOS139 traceability for every production candidate family, including approach sections, TOCS, IHS, OHS, conical, transitional and OFZ/inner surfaces.
Add independent analytical oracle code under tests. It must not import the production candidate constructors, controlling solver or comparison engine.
Use real-airport/AIP data for input and scenario realism, but calculate expected elevations and intersections independently from the governing rules.
Cover single, parallel, converging, intersecting, displaced-threshold, clearway/stopway, precision, non-precision and non-instrument configurations.
Add targeted analytical cases for tangential and crossing axis/conical surfaces, conical/conical interaction, nested surfaces, equality ties and near-coincident geometry.
Repeat the same process for modernised OFS/OES. Its computational capability may later become supported, while its future applicability warning and non-enforceable status remain unchanged.
Interfaces and Evidence
Add internal solver_diagnostics and comparison_diagnostics records; do not change saved dialog input schemas or existing layer fields.
Extend the OLS regression report with repair, unresolved-comparison, approximation-error, determinism and source-checkpoint results.
Keep user-facing output contracts unchanged:controlling regions and clipped contours remain published;
candidate surfaces and baseline transition boundaries remain diagnostic;
comparison equal-height transitions remain published.

Store source-backed fixtures separately from performance fixtures so authoritative expected values are not regenerated from current outputs.
Test and Promotion Gates
Unit tests:exact candidate-pair solutions;
adaptive curved-boundary error bounds;
cell adjacency and deterministic tie resolution;
unresolved-versus-empty comparison semantics;
exact contour ownership and clipping.

Metamorphic tests:candidate registration-order permutations;
runway-order permutations;
translated and rotated equivalent configurations;
repeated-run stable IDs and equivalent geometry.

End-to-end tests:existing four fixtures;
new source-backed and targeted topology fixtures;
memory and file output;
every supported QGIS release.

Hard gates:zero invalid or empty required geometry;
zero unexplained gaps, cross-class overlaps or unresolved comparisons;
zero exceptional repair activations;
exact controller identity at all oracle checkpoints;
affine/constant elevation error no greater than 0.001 m;
curved-transition vertical residual no greater than 0.01 m, with a documented horizontal error bound;
contours wholly contained by their owning region;
no duplicate IDs and deterministic outputs.

Performance gate:compare three-run medians with the saved QGIS 4 baseline;
investigate regressions above 20%;
never relax accuracy or topology gates to recover performance.

Promotion:promote MOS139 ols.controlling_lower_envelope from partial to supported only after all MOS gates and independent technical review pass;
retain modernised Annex 14 and comparison as partial until their separate source-backed matrix passes;
publish supported families, tolerances, known exclusions and validation evidence in the release notes.

Assumptions for Review
Recommended sequence is MOS139 controlling OLS first, followed by modernised Annex 14 OFS/OES and comparison.
Mandatory evidence is regulation traceability plus an independent analytical oracle; external peer-tool comparison is supplementary rather than required.
Broad recovery repairs may remain available for diagnostics, but activation prevents a production-supported result.
Implementation status: tranche 1 diagnostics and regression reporting are now
implemented. Geometry construction remains unchanged while these diagnostics
establish the attributable pre-hardening baseline. Use `--production-gates` to
reject exceptional recovery or unresolved comparisons; the current performance
fixtures are expected to expose (and therefore fail on) known downstream repair
until tranches 2–4 eliminate those activations.

Tranche 2/3 progress: the global solver now audits polygonize coverage and
records unanimous and ambiguous omitted cells without mutating production
geometry. Applying those cells is deliberately blocked because the intersecting
and stress benchmarks showed changed OES classifications. An exact shared-edge
cell-adjacency network is now constructed as the authoritative internal
topology, without rounded coordinate keys or across-edge probes. The historical
probed transition layer remains diagnostic and unchanged for output-contract
compatibility during the first production release. Production gates require the
adjacency network and reject either class of unapplied coverage gap.

MOS139 disposition: accepted and locked on 12 July 2026. Its current controlling
geometry is promoted to `supported` under the explicit compatibility contract
in `docs/mos139_controlling_ols_lock.md`. Remaining topology and comparison
hardening applies to modernised Annex 14 OFS/OES and must not alter the locked
MOS139 controller identities or geometry digests.
