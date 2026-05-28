# Obstacle Limitation Surfaces (OLS)

This document records the MOS source requirements used by the Safeguarding Builder and audits how they are applied in the implementation.

## Section 7.04 Reference Elevation Datum

### MOS Requirement

A reference elevation datum must be:

- established for the horizontal and conical surfaces of the OLS; and
- if the elevation of the ARP is within 3 m of the average elevations of all existing and proposed runway ends, the same elevation as the ARP, rounded down to the nearest half metre; and
- if that ARP condition does not apply, the average elevation of existing and proposed runway ends, rounded down to the nearest half metre.

### Implementation

Implemented in `SafeguardingBuilder._calculate_reference_elevation_datum`.

The current logic:

- requires an ARP elevation;
- collects two runway-end elevation values per runway from `runway_end_elev_1` and `runway_end_elev_2`;
- averages the available runway elevation values;
- uses ARP elevation where `abs(arp_elevation - average_runway_elevation) <= 3.0`;
- otherwise uses the average runway elevation;
- rounds the selected value down to the nearest 0.5 m using `math.floor(value * 2) / 2.0`.

### Compliance Finding

Status: implemented.

The calculation method matches the MOS rule because RED now uses the physical runway-end elevations, separate from landing-threshold elevations.

### Recommended Follow-up

- Add a unit test covering:
  - ARP within 3 m of average runway-end elevation;
  - ARP more than 3 m from average runway-end elevation;
  - rounding down to the nearest half metre;
  - multiple existing/proposed runway ends.

## Section 7.06 Conical Surface And OHS Continuation

### MOS Requirement

If an outer horizontal surface is present and the conical surface does not
terminate directly into the commencement of the outer horizontal surface, the
conical surface must continue outwards on the same plane perpendicular to the
periphery of the inner horizontal surface until it reaches the commencement of
the outer horizontal surface.

### Implementation

Implemented in `GuidelineOlsMixin._generate_airport_wide_ols`.

The current logic:

- starts with the conical height extent from `CONICAL_PARAMS`;
- checks whether an OHS applies for the highest airport-wide ARC/type combination;
- compares the tabular conical top against the OHS height when OHS applies;
- extends the conical height extent to `OHS height above RED - IHS height above RED` when that value is greater than the tabular conical extent;
- uses the effective conical extent for the conical polygon, conical contours, attributes, and the OHS-minus-conical geometry difference.

For Code 3/4 precision cases this changes the effective conical extent from
100 m above IHS to 105 m above IHS, so the conical surface reaches the OHS at
150 m above RED.

### Compliance Finding

Status: implemented.
