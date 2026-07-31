# Safeguarding Standardisation Matrix

**Status:** Research baseline and implementation roadmap

**Last reviewed:** 31 July 2026

This document maps the nine Australian National Airports Safeguarding
Framework (NASF) guidelines to the closest UK, EASA/EU and ICAO mechanisms.
It is intended to guide additional generator families without treating unlike
regulatory mechanisms as interchangeable.

NASF is a national land-use planning framework. ICAO primarily supplies
international Standards and Recommended Practices (SARPs) and technical
manuals; EASA currently combines common aerodrome requirements with national
implementation; and the UK combines CAA guidance, aerodrome safeguarding maps
and Department for Transport planning policy. A shared hazard does not
therefore imply shared geometry, thresholds or legal effect.

## Classification

| Code | Equivalence | Meaning for implementation |
| --- | --- | --- |
| **D** | Direct | The mechanism has source-defined geometry or parameters suitable for a jurisdiction-specific generator. |
| **P** | Partial | The same hazard is addressed, but by a different geometry, an asset/procedure-specific assessment or a case-by-case study. |
| **F** | Framework only | The source creates a duty to consult, monitor or assess but does not define portable geometry. |
| **N** | No equivalent found | No common mechanism was identified in the reviewed primary sources. National or airport-specific controls may still apply. |

The codes describe implementation equivalence, not the legal status of a
source. Outputs must retain their own provenance and applicability metadata.

## Safeguarding Taxonomy

```text
Airport Safeguarding
├─ Compatible Land Use
│  ├─ Aircraft Noise
│  └─ Public Safety / Third-Party Ground Risk
├─ Protected Airspace
│  ├─ Aerodrome OLS / OFS / OES
│  ├─ Instrument Flight Procedure Surfaces
│  └─ CNS Building Restricted Areas
├─ Development-Created Hazards
│  ├─ Wildlife Attraction
│  ├─ Hazardous, Confusing or Misleading Lights
│  ├─ Wind Turbines
│  ├─ Building-Induced Turbulence
│  ├─ Solar Glint and Glare
│  └─ Gaseous Emissions, Plumes, Dust and Smoke
├─ Special Sites and Activities
│  ├─ Heliports / Hospital Helicopter Landing Sites
│  ├─ Temporary Obstacles and Cranes
│  └─ Laser Emitters, Fireworks and Directed Light
└─ Emerging Hazards
   ├─ Drones / UAS
   └─ Radio-Frequency Interference, including 5G
```

## Cross-Jurisdiction Mapping

Source identifiers refer to the [Primary Source Register](#primary-source-register).

| Safeguarding element | Australia (NASF) | United Kingdom | EASA / European common framework | ICAO baseline | Equivalence and implementation consequence |
| --- | --- | --- | --- | --- | --- |
| Aircraft noise / compatible land use | Guideline A: noise metrics, disclosure and planning controls [AUS-1] | Airport-specific noise contours and planning controls; there is no single CAP 738 safeguarding polygon [UK-10] | No EASA-wide safeguarding geometry; noise and land-use controls sit principally with environmental/planning law and Member States | Annex 16 Vol I; Doc 9184 Part 2 land-use zoning; Doc 9911 contour computation [ICAO-8, ICAO-9, ICAO-10] | **P** — support imported contours first; a compliant calculation engine needs fleet, track, performance, movement and noise data. |
| Public safety / third-party ground risk | Guideline I: runway-end Public Safety Area [AUS-1] | DfT Public Safety Controlled Zone (PSCZ) and Public Safety Restricted Zone (PSRZ) [UK-5] | No harmonised EASA public-safety-zone shape found | Doc 9184 addresses compatible land use, but no universal ICAO runway-end public-safety polygon was found [ICAO-9] | **D** for the UK; **N/P** for EASA and ICAO. Do not reuse NASF trapezoid dimensions for a UK PSZ. |
| Aerodrome protected airspace | Guideline F: OLS and PANS-OPS planning protection [AUS-1] | CAP 168 OLS, applied through CAP 738 safeguarding maps [UK-1, UK-2] | Regulation 139/2014 Art 8; CS-ADR-DSN Issue 7 Chapters H/J [EASA-1, EASA-2] | Annex 14 Vol I current OLS; Amendment 18 OFS/OES from 21 November 2030 [ICAO-1, ICAO-2] | **D** — already belongs to selectable aerodrome rulesets, not a supplementary safeguarding framework. |
| Instrument flight procedure protection | Guideline F includes PANS-OPS protection [AUS-1] | CAP 738 requires separate IFP assessment; CAP 785B governs implementation and safeguarding; CAP 232 supplies survey requirements [UK-1, UK-8, UK-11] | Art 8 GM1 identifies PANS-OPS surfaces adopted into national law as “other surfaces” [EASA-2] | PANS-OPS Doc 8168 Vol II [ICAO-3] | **D/P** — geometry is procedure-specific. Prefer authoritative surface import and obstacle intersection before attempting automatic procedure design. |
| CNS facility protection | Guideline G Building Restricted Areas (BRAs) by facility type [AUS-1] | Official technical-site maps and asset-specific assessment under CAP 738; CAP 764 adds wind-turbine assessment [UK-1, UK-4] | Art 9(f) requires consultation for radiation or objects affecting CNS; no common BRA dimensions are specified [EASA-2] | Annex 10 facility performance/siting requirements; EUR Doc 015 provides regional BRA guidance, not global SARPs [ICAO-4, ICAO-5] | **P/F** — use facility inventory plus authority-approved templates. Never substitute NASF Guideline G dimensions. |
| Wildlife attraction | Guideline C: 0–3 km, 3–8 km and 8–13 km management zones [AUS-1] | A 13 km wildlife consultation circle appears on official safeguarding maps; CAP 772 explicitly says 13 km is not itself a universal requirement [UK-2, UK-3] | Arts 9(e) and 10 plus ADR.OPS.B.020 require assessment and management, with no common radius [EASA-2] | Annex 14, PANS-Aerodromes and Doc 9137 Part 3 require a site-specific wildlife hazard management programme [ICAO-1, ICAO-6] | **D** for a UK consultation overlay; **F** for EASA/ICAO. The UK circle must not inherit NASF A/B/C risk semantics. |
| Hazardous, confusing or misleading lights | Guideline E: four runway-aligned intensity-control zones plus a 6 km area [AUS-1] | CAP 738 §§3.17–3.20 uses distraction/confusion, glare and full-cut-off assessment; CAP 736 covers directed light [UK-1, UK-9] | Art 9(c) requires consultation; common rules do not reproduce NASF candela bands [EASA-2] | Annex 14 Vol I §5.3.1 addresses non-aeronautical lights and laser emissions [ICAO-1, ICAO-7] | **P/F** — build a screening/assessment record, not a relabelled NASF zone generator. |
| Wind turbines | Guideline D: 30 km assessment radius [AUS-1] | Officially safeguarded aerodromes promulgate wind-turbine maps normally based on a 30 km ARP radius; CAP 764 requires obstacle, IFP and CNS assessment [UK-1, UK-4] | Covered indirectly by Arts 8 and 9(f); no EASA-wide wind-turbine radius [EASA-2] | Annex 14 obstacle controls and Annex 10/CNS assessment apply; no global ICAO 30 km circle [ICAO-1, ICAO-4] | **D** for a fixed 30 km UK consultation overlay; **F/P** elsewhere. The aerodrome’s lodged map overrides generated geometry. |
| Building-induced turbulence / windshear | Guideline B: runway-based trigger zone followed by specialist assessment [AUS-1] | CAP 738 requires consideration near the airport, with a specialist study where a development may generate hazardous turbulence [UK-1, UK-2] | Art 9(b) expressly requires consultation; detailed common criteria are not yet provided [EASA-2, EASA-4] | Doc 9817 addresses low-level windshear and turbulence but does not supply a universal building-development zone [ICAO-11] | **P/F** — store a jurisdiction-specific screening decision and study result; do not apply the NASF trigger rectangle outside Australia. |
| Helicopter landing sites | Guideline H protects strategically important HLS [AUS-1] | CAP 738 Chs 8–9 and CAP 1264 cover heliport/HHLS safeguarding, approach/take-off surfaces and downwash [UK-1, UK-6] | CS-HPT-DSN Issue 1 covers surface-level VFR heliports located at aerodromes in scope; it is not a general off-airport HLS code [EASA-5] | Annex 14 Vol II and Heliport Manual Doc 9261 [ICAO-12, ICAO-13] | **Out of scope** for this airport safeguarding plugin. |
| Solar glint and glare | No dedicated guideline; overlaps Guideline E/G | CAP 738 Appendix C and CAA safeguarding guidance require case-specific glare, radar, OLS, IFP and wildlife review [UK-1, UK-2] | Art 9(d); GM1 ADR-DSN.M.615 describes a dazzle safety assessment and uses 20,000 cd/m² as a maximum acceptable luminance assumption for solar panels [EASA-2, EASA-3] | Annex 14 light-safety principles and Doc 9184 land-use guidance; no universal solar exclusion polygon identified [ICAO-1, ICAO-9] | **P** — implement line-of-sight/sun-reflection analysis and receptor records, not a fixed buffer. Treat the EASA luminance value as source-scoped guidance, not a global threshold. |
| Emissions, plumes, dust and smoke | No dedicated guideline; related to operational-airspace protection | CAP 738 includes dust/smoke from construction and thermal uplift or vapour plumes in safeguarding assessment [UK-1, UK-2] | The current common rules are high-level; RMT.0751 explicitly includes gaseous emissions in its future scope [EASA-4] | Doc 9184 environmental control and Doc 9817 windshear/turbulence guidance are relevant, but no generic exclusion geometry was found [ICAO-9, ICAO-11] | **P/F** — create a consultation checklist and specialist-study attachment, not automatic pass/fail geometry. |
| Temporary obstacles and cranes | Guideline F protected-airspace assessment | CAA notification is required for a crane over 10 m AGL within 6 km of an aerodrome unless shielded by higher surroundings, and for a crane at or above 100 m AGL regardless of location [UK-7] | Art 8 consultation plus applicable OLS/other-surface assessment [EASA-2] | Annex 14 obstacle assessment, marking, lighting and publication [ICAO-1] | **D** for a UK notification screening layer; all actual acceptability checks still run against OLS, IFP and CNS controls. |
| Laser emitters and directed light | Closest match is Guideline E | CAP 736 notification and safety assessment [UK-9] | Arts 9(c)/(f); laser protection is also in the scope of RMT.0751 [EASA-2, EASA-4] | Annex 14 Vol I defines laser-protected flight zones; Doc 9815 supplies guidance [ICAO-7] | **D/P** — a strong future generator candidate, but extract current zone dimensions and irradiance criteria from a controlled source before coding. |
| Drones / UAS and emerging air mobility | No current dedicated NASF guideline | CAP 722 governs UAS operations; aerodrome-specific flight-restriction and coordination requirements apply | RMT.0751 includes drones, but does not yet provide a common aerodrome-surroundings buffer [EASA-4] | ICAO RPAS provisions do not yet amount to a generic airport land-use safeguarding polygon | **F/N** — policy watch only; do not introduce a speculative radius. |

## Key Jurisdiction Findings

### United Kingdom

The UK is the closest near-term source of additional generator-ready mechanisms.
Officially safeguarded aerodromes lodge maps with planning authorities, and the
map is the controlling local artifact. Generic dimensions below are therefore
defaults or screening rules, not replacements for a lodged map.

#### Public Safety Zones

The October 2021 DfT policy defines two runway-end triangles based on each
landing threshold. The aerodrome operator produces the official maps.

| Zone | Published applicability | Length from landing threshold | Half-width at threshold | Distal form | Proposed output |
| --- | --- | ---: | ---: | --- | --- |
| PSRZ | Relevant runway ends at airports to which PSZ policy applies | 500 m | 75 m | Tapers away from the runway | `public_safety_restricted_zone` |
| PSCZ | Fewer than 45,000 commercial ATMs/year | 1,000 m | 140 m | Tapers away from the runway | `public_safety_controlled_zone` |
| PSCZ | Greater than 45,000 commercial ATMs/year | 1,500 m | 140 m | Tapers away from the runway | `public_safety_controlled_zone` |

PSZs are established at airports with more than 18,000 commercial air transport
movements per year. The source text uses “fewer than” and “greater than” 45,000
for the PSCZ length and does not state the equality case in the reviewed page.
Do not silently choose a band for exactly 45,000 movements; require an explicit
operator value or a source-confirmed interpretation. Generated output should be
labelled **indicative** until reconciled with the official airport map.

Required inputs are the landing threshold, outward runway centreline bearing,
annual commercial movements, PSZ applicability, and any airport-specific
override geometry. A runway extension, threshold movement or traffic change can
require the official zone to be redefined.

#### Wildlife and Wind-Turbine Consultation Maps

- Generate a single 13 km UK wildlife consultation circle from the ARP. Retain
  fields stating that it is a consultation envelope and not a universal
  regulatory risk boundary. Do not generate NASF’s three wildlife bands.
- Generate a fixed 30 km UK wind-turbine consultation circle for an officially
  safeguarded aerodrome. A lodged renewable-energy map or operator-supplied
  geometry must take precedence when authoritative import support is added.
- Neither circle decides acceptability. Candidate developments still require
  land-use/wildlife review or OLS, IFP, CNS and operational assessment.

#### Temporary Obstacles

Implement the UK crane rule as a notification-screening result with independent
tests for:

1. distance to the relevant aerodrome boundary or approved reference geometry;
2. height above ground and height relative to surrounding obstacles;
3. the nationwide 100 m AGL trigger; and
4. intersection with OLS, IFP and CNS protection layers.

The 6 km rule is a notification mechanism, not an obstacle-clearance surface.

### EASA / European Common Framework

Regulation (EU) No 139/2014 Articles 8–10 and Regulation (EU) 2018/1139 Annex
VII establish broad safeguarding, monitoring and wildlife-management duties.
They cover nearly every NASF hazard but generally leave detailed implementation
to Member States. EASA itself describes the current framework as too high-level
and opened RMT.0751, **Protection of aerodrome surroundings**, on 23 March 2026.

Consequences for this project:

- keep EASA CS-ADR-DSN OLS in the aerodrome ruleset;
- do not invent EASA-wide radii for wildlife, wind turbines, CNS, turbulence,
  emissions or drones;
- allow national implementations to be added as their own safeguarding
  profiles under the EASA common legal provenance; and
- version future RMT.0751-based rules separately from the current Articles 8–10
  baseline.

Solar glare is the main non-OLS area with more detailed EASA guidance. A future
assessment should model pilots on approach, touchdown and runway roll plus ATC
receptors. The 20,000 cd/m² assumption in GM1 ADR-DSN.M.615 must remain tied to
that source edition and must not be presented as an ICAO, UK or universal limit.

### ICAO

ICAO sources form a technical baseline rather than a single NASF-equivalent
planning framework:

- Annex 14 Vol I supplies obstacle, visual-aid, non-aeronautical-light and
  wildlife provisions.
- PANS-OPS Doc 8168 Vol II supplies procedure-design criteria. These surfaces
  depend on the actual procedure and cannot be reconstructed reliably from
  runway type alone.
- Annex 10 and regional/national material supply CNS facility protection. ICAO
  EUR Doc 015 is useful for European BRA design, but it is regional guidance and
  must not be labelled as a global ICAO standard.
- Doc 9184 Part 2 and Doc 9911 support compatible land use and aircraft-noise
  contours; they do not prescribe one universal land-use contour.
- Annex 14 Vol II and Doc 9261 provide the appropriate global heliport basis,
  but heliports are outside this plugin's airport safeguarding scope.
- Annex 14 laser-protected flight zones are an additional mechanism with useful
  geometry, subject to controlled extraction of the current numeric criteria.

## Recommended Implementation Backlog

| Priority | Mechanism | Proposed family/profile | First deliverable | Principal caveat |
| ---: | --- | --- | --- | --- |
| 0 | UK, EASA and ICAO protected airspace | Existing `cap168`, `easa` and `annex14` rulesets | Preserve current ruleset ownership and provenance | Do not duplicate OLS inside a supplementary framework. |
| 1 | UK wildlife consultation | `wildlife_consultation` / `uk_caa_safeguarding` | One fixed 13 km ARP circle with consultation metadata | Not a universal legal boundary and not NASF three-band zoning. |
| 1 | UK wind-turbine consultation | `wind_energy_consultation` / `uk_caa_safeguarding` | Fixed 30 km ARP circle plus OLS/IFP/CNS intersection hooks | Lodged aerodrome map overrides generated geometry. |
| 1 | UK public safety zones | `public_safety_ground_risk` / `uk_dft_psz_2021` | PSRZ and PSCZ indicative triangles per runway end | Confirm applicability and the exactly-45,000 movement case; official map controls. |
| 1 | UK crane notification | `temporary_obstacle_notification` / `uk_caa_cranes` | 6 km/10 m and nationwide 100 m screening with reason codes | Notification does not imply approval. |
| 2 | IFP protection | `ifp_protection` / source-specific profile | Import authoritative 2D/3D procedure surfaces and intersect candidates | Procedure design and approval remain external specialist functions. |
| 2 | UK/ICAO CNS protection | `cns_bra` / authority-specific profile | Facility inventory, approved template library and candidate intersection | Dimensions vary by facility, installation and responsible authority. |
| — | Heliport safeguarding | Not implemented | — | Explicitly out of scope for this airport safeguarding plugin. |
| 2 | ICAO/UK laser protection | `directed_light_protection` | Laser-zone geometry and source-scoped irradiance attributes | Numeric criteria require current controlled-source verification. |
| 3 | Solar glint and glare | `solar_glare_assessment` | Sun-path/reflection engine with pilot/ATC receptors and time intervals | No credible fixed exclusion buffer. |
| 3 | Aircraft noise | `noise_land_use` | Import, validate, style and compare externally produced contours | Full Doc 9911 computation needs substantial operational and aircraft data. |
| 3 | Turbulence and plume hazards | `aerodynamic_hazard_screening` | Screening record, study boundary import and specialist conclusion fields | No portable UK/EASA/ICAO pass/fail geometry. |
| 4 | EASA RMT.0751 and UAS/5G | Versioned policy watch | Source/version registry and change-detection checklist | Do not implement proposed or emerging material as current regulation. |

### Implemented UK Profile

The selectable `uk_caa_safeguarding` profile implements the priority 1 UK
mechanisms as follows:

- fixed, indicative ARP-centred wildlife and wind-turbine consultation circles
  at 13 km and 30 km respectively, with explicit source/applicability metadata;
- opt-in DfT PSRZ and PSCZ triangles at both landing thresholds, requiring an
  explicit 1,000 m or 1,500 m PSCZ selection rather than inferring the unresolved
  exactly-45,000-movement case; and
- an opt-in crane candidate screen with independent 6 km/over-10 m unshielded
  and nationwide at-or-above-100 m AGL reason codes, duration/DGC screening,
  and CAA lighting outcomes. The generated 6 km area uses the ARP only as a
  labelled proxy until approved aerodrome-boundary/reference geometry is supplied.

CAP 168 OLS remains owned by the existing protected-airspace ruleset and is not
duplicated by this supplementary profile.

## Data and Provenance Contract

Every non-NASF output family should expose at least:

| Field | Purpose |
| --- | --- |
| `family_id` | Stable generic family such as `wildlife_consultation`. |
| `profile_id` | Jurisdiction/source implementation such as `uk_caa_safeguarding`. |
| `source_id` | Identifier from the primary source register or a more specific controlled-source record. |
| `source_version` | Edition, amendment and effective/applicability date. |
| `authority_level` | Regulation, policy, certification specification, guidance, airport map or user-supplied study. |
| `applicability` | Airport/runway/facility/site conditions under which the output applies. |
| `geometry_status` | `official`, `operator_supplied`, `generated_indicative`, `imported` or `screening_only`. |
| `assessment_result` | `not_assessed`, `consult`, `specialist_study`, `acceptable`, `mitigation_required` or `not_acceptable`. |
| `caveat` | Human-readable limitations, overrides and non-equivalence notes. |

Source parameters belong in jurisdiction profiles. Generic geometry helpers may
be shared, but generator names, layer groups and fields should not encode NASF
guideline letters.

## Primary Source Register

Only primary regulator, government or ICAO sources were used for the mapping.
Paywalled ICAO store entries establish document identity and edition but are not
a substitute for a controlled copy when extracting numeric criteria.

### Australia

- **AUS-1** — Australian Government, [NASF principles and Guidelines A–I](https://www.infrastructure.gov.au/infrastructure-transport-vehicles/aviation/aviation-safety/aviation-environmental-issues/national-airports-safeguarding-framework/national-airports-safeguarding-framework-principles-and-guidelines).

### United Kingdom

- **UK-1** — UK CAA, [CAP 738: Safeguarding of Aerodromes](https://www.caa.co.uk/publication/pid/576), Version 3, 29 October 2020.
- **UK-2** — UK CAA, [What is safeguarding?](https://www.caa.co.uk/commercial-industry/aerodromes/safeguarding/what-is-safeguarding/), current web guidance reviewed 31 July 2026.
- **UK-3** — UK CAA, [CAP 772: Wildlife Hazard Management at Aerodromes](https://www.caa.co.uk/data-and-publications/publications/documents/content/cap-772/), Version 2, 20 October 2017, status current.
- **UK-4** — UK CAA, [CAP 764: Policy and Guidelines on Wind Turbines](https://www.caa.co.uk/data-and-publications/publications/documents/content/cap-764/), Version 7, 17 December 2025.
- **UK-5** — UK Department for Transport, [Control of development in airport public safety zones](https://www.gov.uk/government/publications/control-of-development-in-airport-public-safety-zones/control-of-development-in-airport-public-safety-zones), updated 8 October 2021.
- **UK-6** — UK CAA, [CAP 1264: Standards for helicopter landing areas at hospitals](https://www.caa.co.uk/data-and-publications/publications/documents/content/cap1264/), Version 3.2, 13 February 2026.
- **UK-7** — UK CAA, [Crane notification](https://www.caa.co.uk/commercial-industry/airspace/event-and-obstacle-notification/crane-notification/), current web guidance reviewed 31 July 2026.
- **UK-8** — UK CAA, [Aerodrome safeguarding: other publications](https://www.caa.co.uk/commercial-industry/aerodromes/safeguarding/other-publications/), including CAP 785B.
- **UK-9** — UK CAA, [Outdoor laser lights and fireworks](https://www.caa.co.uk/commercial-industry/airspace/event-and-obstacle-notification/commercial-displays-and-events/outdoor-laser-lights-and-fireworks/), referring to CAP 736.
- **UK-10** — UK CAA, [Noise: international policy and regulation](https://www.caa.co.uk/environmental-sustainability/uk-aviation-environmental-review/uk-aer-noise/noise-international-policy-and-regulation/).
- **UK-11** — UK CAA, [Introducing or amending an instrument flight procedure](https://www.caa.co.uk/commercial-industry/airspace/instrument-flight-procedures/introducing-or-amending-an-ifp/), including CAP 232 survey and CAP 785 approval references.

### EASA / European Union

- **EASA-1** — EASA, [Easy Access Rules for Aerodromes, March 2026 revision](https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-aerodromes), incorporating CS-ADR-DSN Issue 7, applicable since 24 May 2025.
- **EASA-2** — EASA, [Regulation (EU) No 139/2014 Articles 8–10](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-aerodromes-regulation-eu?erules-id=ERULES-1963177438-2062), safeguarding and monitoring of aerodrome surroundings and wildlife hazard management.
- **EASA-3** — EASA, [CS-ADR-DSN Issue 7, GM1 ADR-DSN.M.615](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-aerodromes-regulation-eu?erules-id=ERULES-1963177438-2468), including dazzle and solar-panel guidance.
- **EASA-4** — EASA, [RMT.0751: Protection of aerodrome surroundings](https://www.easa.europa.eu/en/document-library/terms-of-reference-and-rulemaking-group-compositions/tor-rmt0751), Issue 1, 23 March 2026.
- **EASA-5** — EASA, [CS-HPT-DSN Issue 1](https://www.easa.europa.eu/en/document-library/certification-specifications/cs-hpt-dsn-issue-1), 23 May 2019.

### ICAO

- **ICAO-1** — ICAO, [Annex 14 Vol I: Aerodrome Design and Operations](https://store.icao.int/en/annex-14-aerodromes), Ninth Edition, July 2022, including Amendment 18.
- **ICAO-2** — ICAO, [Amendment 18 OLS quick-reference guide](https://www.icao.int/sites/default/files/APAC/Meetings/2025/2025%20Workshop%20on%20Implementation%20of%20New%20ICAO%20Annex/Training%20Materials/OLS_QU-1.PDF), implementation workshop material.
- **ICAO-3** — ICAO, PANS-OPS [Doc 8168 Vol II: Construction of Visual and Instrument Flight Procedures](https://store.icao.int/en/shop-by-areas/safety/flight-operations?p=2), Seventh Edition, 2020, with later amendments/corrigenda as applicable.
- **ICAO-4** — ICAO, [Annex 10: Aeronautical Telecommunications](https://store.icao.int/en/annexes/annex-10), including Vol I radio navigation aids and Vol IV surveillance.
- **ICAO-5** — ICAO EUR/NAT, [EUR Doc 015: Building Restricted Areas](https://www.icao.int/eurnat/eur%20and%20nat%20documents/forms/allitems.aspx?rootfolder=%2Feurnat%2Feur+and+nat+documents%2Feur+documents%2Feur+documents%2F015+-+building+restricted+areas), regional guidance.
- **ICAO-6** — ICAO, [Airport Services Manual Part III: Wildlife Hazard Management, Doc 9137](https://store.icao.int/en/airport-services-manual-part-iii-wildlife-hazard-management-doc-9137p3), Fifth Edition, 2020.
- **ICAO-7** — ICAO, [Manual on Laser Emitters and Flight Safety, Doc 9815](https://store.icao.int/en/shop-by-areas?p=39), First Edition, 2003, used with Annex 14 Vol I §5.3.1.
- **ICAO-8** — ICAO, [Land-use Planning and Management](https://www.icao.int/environmental-protection/land-use-planning-and-management), including Annex 16 and Doc 9184 context.
- **ICAO-9** — ICAO, [Airport Planning Manual Part II: Land Use and Environmental Management, Doc 9184](https://store.icao.int/en/airport-planning-manual-land-use-and-environmental-management-doc-9184-part-2), Fourth Edition, 2018.
- **ICAO-10** — ICAO, [Recommended Method for Computing Noise Contours Around Airports, Doc 9911](https://store.icao.int/en/recommended-method-for-computing-noise-contours-around-airports-doc-9911), Second Edition, 2018.
- **ICAO-11** — ICAO, [Manual on Low-Level Wind Shear and Turbulence, Doc 9817](https://store.icao.int/en/shop-by-areas?p=39), First Edition, 2005, as amended.
- **ICAO-12** — ICAO, [Annex 14 Vol II: Heliports](https://store.icao.int/en/annexes/annex-14), Fifth Edition, July 2020, including Amendment 10.
- **ICAO-13** — ICAO, [Heliport Manual Doc 9261, Parts I and II](https://store.icao.int/en/shop-by-areas/safety/flight-safety?p=2), Sixth Edition, 2026.

## Open Verification Items

- [ ] Obtain controlled copies of the current ICAO numeric source material
      before implementing laser zones or CNS BRAs.
- [ ] Confirm the DfT PSCZ rule for exactly 45,000 commercial movements and the
      treatment of exactly 18,000 movements before hardcoding applicability.
- [ ] Validate UK PSZ generated orientation and taper against at least one
      current official airport PSZ map.
- [ ] Confirm whether CAP 785B surface data can be imported in an existing
      exchange format or needs a project-defined GeoPackage/GeoJSON schema.
- [ ] Select the first EASA Member State national safeguarding implementation;
      Articles 8–10 alone do not supply enough geometry for a useful profile.
- [ ] Review RMT.0751 outputs when published and create a new source version;
      do not mutate the current EASA baseline in place.
- [x] Keep heliports out of scope for this airport safeguarding plugin,
      or are exposed through the current runway-oriented workflow.
