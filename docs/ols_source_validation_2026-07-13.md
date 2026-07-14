# OLS Source-Backed Validation — 13 July 2026

## Outcome

The first independent, source-backed analytical validation tranche is in
place for MOS139 OLS, CAP168 current OLS, future Annex 14 OFS/OES, and the
modernisation comparison.
It passes without importing QGIS, generated polygons, the controlling solver,
or production elevation evaluators into the calculation oracle.

This closes the earlier gap where tests could prove that the implementation was
internally consistent but could not independently establish that a contour,
controller or curved intersection was at the right elevation. It does **not**
by itself promote every controlling-envelope capability to `supported`.
Airport-specific fixtures, remaining topology/recovery gates and independent
technical review are still required by the production-readiness checklist.

## Authoritative sources

Three user-supplied source extracts were reviewed visually, including the
relevant tables rather than relying only on PDF text extraction:

| Source | Edition / applicability | Verified provisions | SHA-256 |
| --- | --- | --- | --- |
| MOS139 (C.07 2026): CASA Part 139 (Aerodromes) MOS 2019, Chapter 7 | Compilation No. 7, in force 12 May 2026, Authorised Version F2026C00403 | 7.04–7.16; Tables 7.15(1) and 7.16(1) | `ecda4ab7171aef3932a35ac631ac8968d5056c616013ae3f452475b4bd513465` |
| UK CAA CAP 168, Chapter 4 | Thirteenth Edition, July 2025, Amendment 15; current table applicable until 20 November 2030 | 4.8–4.73; Tables 4.1 and 4.2 | `27c1d35fce840caaffeefb898e6fc4df9a4bd4abdb5e8db3f878cfdccce3f649` |
| ICAO Annex 14, Volume I, Chapter 4 | Ninth Edition, July 2022; future OFS/OES provisions applicable as of 21 November 2030 | 4.2–4.3; Tables 4-1–4-15 | `15a5618515f4c7088eb59b86392b53c24f15a05fa9341484931c421489f39cb9` |

The PDFs are not copied into the repository. The fixture records source title,
edition/date, supplied filename, hash, clause/table and printed/PDF page so a
reviewer can reproduce the source check using an authorised copy.

## Evidence design

The validation has three separate layers:

1. `source_validation_v1.json` records cited source facts, explicit synthetic
   airport assumptions, hand-calculated expected results and tolerances.
2. `ols_source_oracle.py` implements only elementary, documented mathematics:
   piecewise linear rise, transverse rise, radial conical rise, affine
   differences, deterministic minimum selection and a closed-form circular
   conical/axis equality curve.
3. `test_ols_source_validation.py` checks both the independent calculations and
   representative production parameter dictionaries against the cited source
   facts. The independent oracle itself has no production imports.
4. `test_ols_source_validation_qgis.py` applies the independent expected values
   to the production axis/conical evaluators, exact affine transition builder
   and controlling-candidate selection under QGIS.

The comparison checks are explicitly derived product checks. A comparison
change value is `future Annex 14 elevation - baseline MOS139 elevation`; it is
not a regulatory dimension in either source document.

## Independent checkpoints

The initial fixture exercises the following calculations:

| Family | Independent result examples |
| --- | --- |
| MOS139 code-3 NPA approach | 120 m contour at station 500 m; 180 m contour at station 3,400 m; section elevations checked through the horizontal segment. |
| MOS139 code-3 TOCS | 125 m contour at station 650 m from a 112 m inner edge; 412 m at the 15,000 m outer edge. |
| MOS139 IHS/conical | IHS at RED + 45 m; 170 m and 220 m conical contours at 500 m and 1,500 m from the IHS edge. |
| MOS139 transitional | 125 m contour 104.895104895 m from a 110 m lower edge at the table's 14.3% slope. |
| Curved MOS139 axis/conical intersection | Four closed-form points on a circular-IHS conical/approach equality arc; axis and conical elevations agree to `1e-9 m`. |
| CAP168 Code 1 precision approach | Section elevations at 3,000 m, 5,500 m and 10,000 m; 200 m contour at station 3,833.333333333 m with 645 m half-width. |
| CAP168 IHS/conical | IHS at 45 m above the lowest threshold; a 200 m conical contour 1,100 m from the IHS edge for a 100 m lowest threshold. |
| Annex 14 future OFS | ADG III instrument approach and 20% transitional contour stations/elevations. |
| Annex 14 future OES | Precision approach, instrument departure, heavy ADG III take-off climb and horizontal-surface elevations. |
| Modernisation comparison | Signed -1 m, 0 m and +5 m delta-contour stations, with controlling identity checked independently on both sides of the zero line. |

The source-to-production checks cover representative values from every
contour-producing family used in those calculations: MOS Approach, TOCS, IHS,
Conical, Transitional, Inner Approach, Inner Transitional, Baulked Landing and
OHS; CAP168 Approach, TOCS, Transitional, OFZ/inner surfaces and source rules
for IHS, Conical and OHS; Annex OFS approach/inner/transitional/balked surfaces; and Annex OES
horizontal, straight-in, precision approach, departure and both take-off mass
categories.

CAP168 airport-wide rules are source-checked and resolved through the new
ruleset-owned construction context. This keeps its lowest-runway-threshold
datum, actual main-runway length, circle/racetrack selection and subsidiary
joins independent of the MOS RED-relative compatibility path.
`rulesets/cap168/source_matrix.md` records the adaptation and release gates.

### CAP168 source corrections

Visual review found five inconsistencies in the supplied July 2025 PDF. The
user subsequently confirmed the three numerical corrections shown below:

- Table 4.1 prints `180 m` for the conditional Code 3/4 final width, while its
  footnote 4 unambiguously says 1,800 m; the conditional parameter uses 1,800 m.
- Table 4.2 `6 m` is corrected to `60 m` for the precision Code 3/4 threshold
  offset; this also agrees with 4.23.
- Table 4.2 `360 m` is corrected to `3,600 m` for the precision Code 3/4 second
  section; this also agrees with the 150 m plane and published section total.
- Paragraph 4.50 `250 m` is corrected to `2,500 m` for the short NI Code 2 IHS
  radius. The staged plan rule now records both the printed and corrected value.
- Paragraph 4.73(1) points the Code 1/2 balked-landing origin to the Code 3/4
  area in 4.70 rather than the immediately preceding Code 1/2 area in 4.72;
  the parameter follows 4.72 and records `60_m_beyond_lda`.

## Numerical contract

- Source parameters must match the captured decimal values within `1e-12`.
- Analytical distances and elevations must match their independent expected
  values within `1e-9 m`.
- Curved equality checkpoints must leave no more than `1e-9 m` difference
  between the two independently evaluated surfaces.
- Production QGIS evaluators are compared with the independent analytical
  values at `0.001 m`; exact affine transition coordinates use `0.000001 m`.
- These analytical tolerances verify the equations. They do not replace the
  separate chord, smoothing, containment and polygon topology tolerances used
  by the QGIS geometry workflow.

## Run

The portable source-backed suite runs with ordinary Python:

```bash
python3 -m unittest tests.test_ols_source_validation -v
```

Result on 13 July 2026 after adding CAP168: **9 portable tests passed** and
**5 QGIS-facing tests passed** (**14 combined**). The QGIS-facing suite includes
a CAP168 section-elevation check against the production axis evaluator.

The QGIS integration and workflow-regression suites remain separate because
they validate generated geometry, clipping, coverage, IDs and performance
rather than independently calculating the regulatory surface elevations.

## Remaining work before production promotion

- Expand parameter traceability from representative contour-producing
  profiles to every applicable MOS/CAP168 runway code/type and every selected
  Annex ADG/operational option.
- Complete track-following CAP168 approach-adjacent transitional construction.
  The airport-wide datum, plan forms and runway-length applicability are now
  integrated, and the three numerical misprints no longer require disposition;
  independent technical review of the source capture and generated results
  remains required.
- Add source-backed airport/runway fixtures for displaced thresholds,
  clearways/stopways, precision/non-precision/non-instrument operations,
  parallel/converging/intersecting runways and near-coincident geometry.
- Compare generated QGIS output with independent checkpoint coordinates,
  elevations and controlling identities for those airport fixtures.
- Complete the topology, unresolved-comparison, exceptional-repair,
  determinism and release-performance gates already listed in `docs/TODO.md`.
- Record reviewer name/date and disposition after an independent technical
  review of both the source capture and calculation assumptions.

Primary/intermediate contour interval compatibility remains intentionally
unimplemented and accepted. Future Annex 14 output remains a model of the
provisions applicable from 21 November 2030, and OES output remains an
assessment trigger rather than a protected-airspace approval limit.
