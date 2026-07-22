# Development Roadmap

**Status:** Roadmap

**Last reviewed:** 22 July 2026

This file is the single project documentation backlog. It lists incomplete
work only; completed implementation history belongs in Git and regression
fixtures.

## Release Priorities

- [ ] Resolve GeoPackage `Polygon`/`MultiPolygon` declaration mismatches without
  changing generated geometry.
- [ ] Turn the QGIS workflow matrix into release evidence with repeated,
  isolated runs and stable performance comparisons.
- [ ] Validate declared distances and stopway behavior against source-backed
  sample airports.
- [ ] Review AGL and runway-marking output in QGIS using representative runway
  configurations.

## Maintenance

- [ ] Replace remaining legacy `AeroSense` branding with `Safeguarding Builder`
  in the dialog title, runtime dashboard implementation and documentation, and
  dashboard tests.

## Protected Airspace

- [ ] Complete the modernised ICAO Annex 14 OFS/OES promotion boundary:
  document complex transitional coverage, reconcile capability declarations,
  and keep the profile `partial` until source, topology, and review gates pass.
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
- [ ] Expand independent source checkpoints and representative fixtures for
  complex transitional, conical/axis, displaced-threshold, clearway, stopway,
  parallel, converging, and intersecting configurations.
- [ ] Evaluate vertex-count reduction for smoothed MOS139 axis/conical
  intersections without changing the accepted compatibility lock.

## Rulesets and Frameworks

- [ ] Complete EASA CS-ADR-DSN Issue 7 table-level traceability, interpretation
  policy, and plugin UI validation before promoting the draft profile.
- [ ] Complete CAP 168 scope outside the supported OLS contract, beginning with
  RESA and approach-adjacent transitional behavior on curved tracks.
- [ ] Resolve remaining ruleset/framework ownership boundaries before adding a
  second supplementary safeguarding framework.
- [ ] Complete the generic safeguarding terminology refactor while retaining
  NASF source provenance.

## Physical, Marking, and Lighting Outputs

- [ ] Consolidate entered stopway lengths, declared-distance calculations, and
  stopway polygon output across rulesets.
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
