# Development Roadmap

**Status:** Roadmap

**Last reviewed:** 22 July 2026

This file is the single project documentation backlog. It lists incomplete
work only; completed implementation history belongs in Git and regression
fixtures.

## Priorities

- [x] Resolve GeoPackage `Polygon`/`MultiPolygon` declaration mismatches without
  changing generated geometry.
- [x] Maintain a representative QGIS workflow smoke set for shared geometry
  changes. Repeat isolated runs when investigating suspected performance or
  state-leak regressions.
- [x] Validate declared distances and stopway behavior against source-backed
  sample airports. CAP 168 checkpoints now cover YBPM and YBCP, including
  TORA/TODA/ASDA/LDA relationships, displaced thresholds, clearways, stopway
  polygon dimensions and placement, and active-ruleset source provenance.
- [ ] Review AGL and runway-marking output in QGIS using representative runway
  configurations.

## Protected Airspace

- [x] Complete the OLS comparison refactor: explicit finalization results,
  invariant auditing, a single ordered repair/finalization pass, transitions
  derived from the finalized partition, numerical-sliver normalization, and
  per-run comparison caches. The 103-test comparison suite and 14-fixture
  workflow matrix pass.
- [ ] Complete the modernised ICAO Annex 14 OFS/OES boundary:
  document complex transitional coverage, reconcile capability declarations,
  and keep the profile `partial` where source or topology evidence is still
  incomplete.
- [ ] Reduce exceptional geometry recovery and unresolved curved-surface
  comparisons in the modernised OFS/OES and comparison paths.
- [ ] Resolve patchy or truncated comparison change contours where a curved
  baseline surface, particularly a conical surface, meets a controller
  transition or horizontal plane. Keep the repair bounded and avoid repeating
  full-domain buffering for individual triangulated segments.
  Deferred after the July 2026 comparison-finalization refactor; the existing
  bounded clipping repair and documented limitation remain unchanged.
- [ ] Prove comparison gain, loss, no-change, transition, and baseline-only
  outputs are exclusive and cover their intended domains.
- [ ] Add targeted source checkpoints and representative fixtures when a change
  affects complex transitional, conical/axis, displaced-threshold, clearway,
  stopway, parallel, converging, or intersecting configurations.
- [ ] Evaluate vertex-count reduction for smoothed MOS139 axis/conical
  intersections only if observed runtimes make it worthwhile; do not
  change the accepted compatibility lock solely for benchmark improvement.

## Rulesets and Frameworks

- [ ] Complete EASA CS-ADR-DSN Issue 7 table-level traceability, interpretation
  policy, and targeted plugin UI validation for the capabilities being
  implemented.
- [ ] Complete CAP 168 scope outside the supported OLS contract, beginning with
  RESA and approach-adjacent transitional behavior on curved tracks.
- [ ] Resolve remaining ruleset/framework ownership boundaries before adding a
  second supplementary safeguarding framework.
- [ ] Complete the generic safeguarding terminology refactor while retaining
  NASF source provenance.

## Physical, Marking, and Lighting Outputs

- [ ] Consolidate entered stopway lengths, declared-distance calculations, and
  stopway polygon output across rulesets. CAP 168 validation is complete; the
  cross-ruleset consolidation remains open.
- [ ] Add runway-suitability inputs used by pre-threshold marking rules.
- [ ] Complete MOS139 holding-position edge cases and confirm touchdown-zone
  marking defaults and runway-length basis.
- [ ] Add explicit closed pre-threshold, starter-extension, pad, bypass, and
  LAHSO inputs required by the outstanding AGL cases.

## CNS and Future Generators

- [ ] Replace CNS `HeightRule = "TBD"` values with implemented vertical logic.
- [ ] Implement specialised glide path and localiser geometry.
- [ ] Add an aircraft-characteristics registry and design-aircraft nomination.
- [ ] Implement NASF Guideline A aircraft-noise generation.
- [ ] Implement NASF Guideline H helicopter-site generation.
