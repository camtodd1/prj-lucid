# Safeguarding Standardisation Matrix

**Status:** Working reference

**Last reviewed:** 16 July 2026

This working document maps generic safeguarding elements to their source
standards across jurisdictions. It is intended to support the refactor from
NASF guideline-specific generator names toward generic safeguarding output
families with jurisdiction-specific policy references.

Use this table to identify equivalent or partially equivalent standards before
adding new rulesets, UI labels, generator names, or source-reference fields.

## Safeguarding Taxonomy

```text
Airport Safeguarding
├─ Aircraft Noise
├─ Public Safety
├─ Protected Airspace
│  ├─ OLS
│  ├─ PANS-OPS
│  └─ CNS Protection
├─ Wildlife Hazard
├─ Lighting Hazard
├─ Wind Turbines
├─ Building-Induced Turbulence
├─ Helicopter Operations
├─ Solar Glare
├─ Emissions / Visibility
└─ Emerging Air Mobility
```

## Cross-Jurisdiction Mapping

| Safeguarding element | Australia (NASF) | UK | Europe | USA |
| --- | --- | --- | --- | --- |
| Aircraft noise | Guideline A |  |  |  |
| Public safety | Guideline I |  |  |  |
| Protected airspace - OLS | Guideline F |  |  |  |
| Protected airspace - PANS-OPS |  |  |  |  |
| Protected airspace - CNS protection | Guideline G |  |  |  |
| Wildlife hazard | Guideline C |  |  |  |
| Lighting hazard | Guideline E |  |  |  |
| Wind turbines | Guideline D |  |  |  |
| Building-induced turbulence | Guideline B |  |  |  |
| Helicopter operations | Guideline H |  |  |  |
| Solar glare |  |  |  |  |
| Emissions / visibility |  |  |  |  |
| Emerging air mobility |  |  |  |  |

## Working Notes

- The `Topic` column should describe the generic safeguarding element, not a
  jurisdiction-specific document structure.
- Jurisdiction columns should identify the applicable source standard, chapter,
  advisory circular, regulation, or guidance document.
- Use short labels in the matrix and add detail in notes below when a mapping is
  partial, conditional, or split across multiple standards.
- Keep source/provenance references separate from generator names in code. For
  example, `Lighting` can be the generator family while `NASF Guideline E`
  remains the Australian source reference.

## Open Mapping Questions

- [ ] Confirm the best UK standard/source for each safeguarding element.
- [ ] Confirm whether Europe should map to EASA CS-ADR-DSN, ICAO Annex 14, or
      both, depending on topic.
- [ ] Confirm whether USA should map to FAA ACs, 14 CFR Part 77, FAA airport
      design standards, or a combination by topic.
- [ ] Decide whether helicopter-site safeguarding belongs in the same generator
      family structure or should remain a separate future module.
- [x] Use ICAO Annex 14 Volume I, Ninth Edition, Amendment 18 for current OLS
      mapping applicable until 20 November 2030.
- [ ] Confirm whether CNS protection should remain a supplementary framework
      rather than part of the aerodrome-standard ruleset for each jurisdiction.
- [ ] Confirm whether MET station safeguarding belongs in this matrix or in a
      separate airport-support outputs matrix.
