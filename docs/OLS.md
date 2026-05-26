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
- collects two runway-end elevation values per runway from `thr_elev_1` and `thr_elev_2`;
- averages the available runway elevation values;
- uses ARP elevation where `abs(arp_elevation - average_runway_elevation) <= 3.0`;
- otherwise uses the average runway elevation;
- rounds the selected value down to the nearest 0.5 m using `math.floor(value * 2) / 2.0`.

### Compliance Finding

Status: implemented, subject to input naming/meaning confirmation.

The calculation method matches the MOS rule if `thr_elev_1` and `thr_elev_2` represent the elevations of the physical runway ends, including existing and proposed runway ends.

The code and UI currently describe these values as threshold elevations. If those values are displaced threshold elevations rather than runway-end elevations, the RED calculation may not fully match Section 7.04.

### Recommended Follow-up

- Confirm whether `thr_elev_1` and `thr_elev_2` are intended to be physical runway-end elevations or threshold elevations.
- If they are physical runway-end elevations, rename the internal variables, UI labels, and log messages to avoid confusion.
- If displaced threshold elevations are needed elsewhere, store them separately from runway-end elevations.
- Add a unit test covering:
  - ARP within 3 m of average runway-end elevation;
  - ARP more than 3 m from average runway-end elevation;
  - rounding down to the nearest half metre;
  - multiple existing/proposed runway ends.
