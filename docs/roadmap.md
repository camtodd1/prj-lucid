# Development Roadmap

**Status:** Roadmap

**Last reviewed:** 31 July 2026

This file is the single project documentation backlog. It lists incomplete
work only; completed implementation history belongs in Git and regression
fixtures.

## Priorities

- [ ] Review AGL and runway-marking output in QGIS using representative runway
  configurations.

## Protected Airspace

- [ ] Add imported or user-defined specific OES geometry for curved and other
  operations. The automatic modernised workflow remains limited to aligned
  straight-in standard OES and does not expose procedure-specific controls.
- [ ] Evaluate vertex-count reduction for smoothed MOS139 axis/conical
  intersections only if observed runtimes make it worthwhile; do not
  change the accepted compatibility lock solely for benchmark improvement.

## Rulesets and Frameworks

- [ ] Add a ruleset for Airspace Act changes, including the distinction between
  Commonwealth-leased airports and non-Commonwealth airports.
- [ ] Complete the remaining EASA CS-ADR-DSN Issue 7 scope: pavement/shoulder
  decision-tree coverage, parallel-runway separation, and controlling-envelope
  evidence. Chapter H/J airport-wide OLS and Category II/III OFZ are supported;
  retain the explicit CAT I guidance and outer-horizontal guidance caveats.
- [ ] Complete CAP 168 scope outside the supported OLS contract, beginning with
  RESA and approach-adjacent transitional behavior on curved tracks.
- [ ] Resolve remaining ruleset/framework ownership boundaries before adding a
  second supplementary safeguarding framework.

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

- [ ] Implement specialised glide path and localiser geometry.
- [ ] Add an aircraft-characteristics registry and design-aircraft nomination.
- [ ] Implement NASF Guideline A aircraft-noise generation.
- [ ] Implement NASF Guideline H helicopter-site generation.

## Data and Workflow Integration

- [ ] Integrate a digital elevation model (DEM).
- [ ] Explore an agentic workflow outside QGIS that auto-populates airport
  input files from verified sources such as the AIP. Consider delivering this
  as an external client rather than as part of the plugin.

## Reporting and Layouts

- [ ] Extend the per-run OLS table report into a production chart layout with
  a georeferenced map inset of the generated OLS surfaces, legend, scale and
  grid information, north point, notes, and title block.
