# Declared Distances

**Status:** Current

**Last reviewed:** 16 July 2026

Safeguarding Builder calculates declared distances for each runway direction
and accepts optional published-value overrides. The generated records are used
by physical outputs, reports, runway-centreline attributes, and take-off climb
surface construction.

## Terms

| Field | Meaning |
| --- | --- |
| `TORA` | Take-off run available |
| `TODA` | Take-off distance available |
| `ASDA` | Accelerate-stop distance available |
| `LDA` | Landing distance available |

Each runway produces one record per direction, such as `07` and `25` for runway
`07/25`.

## Inputs

Threshold coordinates and displaced-threshold lengths establish the physical
runway length and landing threshold positions. Each runway end also accepts:

- clearway and stopway lengths;
- take-off and landing availability;
- optional published overrides for `TORA`, `TODA`, `ASDA`, and `LDA`; and
- source notes.

Blank clearway and stopway values are treated as zero. Operation availability
defaults to enabled. Blank published values use the calculated result.

## Baseline Calculation

For a runway with no operational restriction:

```text
physical length = threshold distance
                + primary displaced threshold
                + reciprocal displaced threshold

TORA = physical length
TODA = TORA + departure-end clearway
ASDA = TORA + departure-end stopway
LDA  = landing-threshold distance available in that direction
```

The active ruleset supplies clearway policy. A default or entered clearway may
be capped by that ruleset, including the common half-`TORA` limit. Published
overrides replace calculated values in the effective output while preserving
the calculated values and recording warnings where the relationship is
unusual.

## Validation

- Lengths must be non-negative.
- Displaced thresholds must fit within the physical runway model.
- `TODA` and `ASDA` must be at least `TORA` when take-off is available.
- `LDA` must be positive when landing is available.
- Values for unavailable operations should be blank or zero.
- Supplied overrides must be positive and are annotated when they conflict with
  the calculated geometry or normal declared-distance relationships.

## Outputs and Ownership

- `safeguarding_builder.py` validates runway data and calculates the per-end
  records.
- `surfaces/physical.py` generates declared-distance and clearway geometry.
- `reports/declared_distances.py` formats the declared-distance report.
- `reports/runway_summary.py` incorporates the records into runway summaries.
- `rulesets/*/physical_data.py` owns ruleset-specific clearway and stopway
  policy.

Source-backed sample-airport validation and stopway polygon consolidation are
tracked in [`roadmap.md`](roadmap.md).
