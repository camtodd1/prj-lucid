import unittest

from dimensions import agl_dimensions as legacy_agl_dimensions
from dimensions import ols_dimensions as legacy_ols_dimensions
from rulesets.easa import lighting as easa_lighting
from rulesets.easa import markings as easa_markings
from rulesets.easa import ols_surfaces as easa_ols_surfaces
from rulesets.easa import physical_data as easa_physical_data
from rulesets.easa import taxiway as easa_taxiway
from rulesets.mos139 import classification, lighting, ols_surfaces, physical_data, taxiway
from rulesets.registry import (
    DEFAULT_RULESET_ID,
    get_ruleset_profile,
    iter_ruleset_profiles,
    normalize_ruleset_id,
)

REQUIRED_PROFILE_METHODS = [
    "classify_runway_type",
    "precision_type_codes",
    "physical_refs",
    "strip_parameters",
    "resa_parameters",
    "ihs_base_height",
    "ols_parameters",
    "taxiway_separation_offset",
    "taxiway_to_taxiway_separation",
    "taxiway_object_separation",
    "stand_taxilane_to_stand_taxilane_separation",
    "stand_taxilane_object_separation",
    "parallel_runway_separation",
    "centreline_marking_width",
    "threshold_marking_params",
    "aiming_point_rule",
    "touchdown_zone_offsets",
    "runway_holding_position_rule",
    "agl_value",
    "runway_type_supports_agl",
    "runway_is_precision",
    "runway_edge_spacing_for_end",
    "threshold_light_count_for_end",
    "runway_end_light_count_for_end",
    "temp_displaced_threshold_lights_per_side",
    "runway_centreline_required",
    "runway_centreline_recommended",
    "runway_centreline_spacing",
    "approach_profile_for_end",
]

REQUIRED_SERVICE_METHODS = {
    "classification": ["classify_runway_type", "precision_type_codes"],
    "ols": ["ihs_base_height", "parameters"],
    "physical": [
        "refs",
        "strip_parameters",
        "resa_parameters",
        "taxiway_separation_offset",
        "taxiway_to_taxiway_separation",
        "taxiway_object_separation",
        "stand_taxilane_to_stand_taxilane_separation",
        "stand_taxilane_object_separation",
        "parallel_runway_separation",
    ],
    "markings": [
        "centreline_marking_width",
        "threshold_marking_params",
        "aiming_point_rule",
        "touchdown_zone_offsets",
        "runway_holding_position_rule",
    ],
    "lighting": [
        "value",
        "runway_type_supports_agl",
        "runway_is_precision",
        "runway_edge_spacing_for_end",
        "threshold_light_count_for_end",
        "runway_end_light_count_for_end",
        "temp_displaced_threshold_lights_per_side",
        "runway_centreline_required",
        "runway_centreline_recommended",
        "runway_centreline_spacing",
        "approach_profile_for_end",
    ],
}


class RulesetRegistryTest(unittest.TestCase):
    def test_default_ruleset_is_mos139_2019(self):
        self.assertEqual(DEFAULT_RULESET_ID, "mos139_2019")
        self.assertEqual(get_ruleset_profile().id, "mos139_2019")

    def test_legacy_mos139_alias_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_ruleset_id("MOS139"), "mos139_2019")
        self.assertEqual(get_ruleset_profile("MOS139").id, "mos139_2019")

    def test_easa_alias_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_ruleset_id("EASA"), "easa_cs_adr_dsn_issue_7")
        self.assertEqual(get_ruleset_profile("CS-ADR-DSN").id, "easa_cs_adr_dsn_issue_7")
        self.assertEqual(normalize_ruleset_id("easa_cs_adr_dsn_issue_6"), "easa_cs_adr_dsn_issue_7")

    def test_annex14_alias_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_ruleset_id("Annex 14"), "icao_annex14_vol1_current_ols")
        self.assertEqual(get_ruleset_profile("ICAO Annex 14").id, "icao_annex14_vol1_current_ols")
        self.assertEqual(normalize_ruleset_id("Annex 14 OFS/OES"), "icao_annex14_vol1_modernised_ofs_oes")
        self.assertEqual(
            get_ruleset_profile("ICAO Annex 14 Modernised").id,
            "icao_annex14_vol1_modernised_ofs_oes",
        )

    def test_structured_payload_normalizes_to_canonical_id(self):
        self.assertEqual(normalize_ruleset_id({"id": "MOS139"}), "mos139_2019")
        self.assertEqual(normalize_ruleset_id({"design_standard": "MOS139"}), "mos139_2019")
        self.assertEqual(normalize_ruleset_id({"ruleset": "MOS139"}), "mos139_2019")

    def test_profiles_expose_capabilities(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertTrue(profile.supports("ols.airport_wide"))
        self.assertEqual(profile.capability_status("ols.controlling_lower_envelope"), "experimental")

    def test_registered_profiles_expose_ruleset_contract(self):
        for profile in iter_ruleset_profiles():
            with self.subTest(profile=profile.id):
                for method_name in REQUIRED_PROFILE_METHODS:
                    self.assertTrue(callable(getattr(profile, method_name, None)), method_name)

    def test_registered_profiles_expose_grouped_services(self):
        for profile in iter_ruleset_profiles():
            with self.subTest(profile=profile.id):
                for service_name, method_names in REQUIRED_SERVICE_METHODS.items():
                    service = getattr(profile, service_name, None)
                    self.assertIsNotNone(service, service_name)
                    for method_name in method_names:
                        self.assertTrue(callable(getattr(service, method_name, None)), f"{service_name}.{method_name}")

    def test_mos139_adapter_matches_ruleset_ols_helpers(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.classify_runway_type("Precision Approach CAT I"),
            classification.get_runway_type_abbr("Precision Approach CAT I"),
        )
        self.assertEqual(
            profile.strip_parameters(3, "PA_I", 45.0),
            physical_data.get_strip_params(3, "PA_I", 45.0),
        )
        self.assertEqual(
            profile.resa_parameters(3, "PA_I", "NI"),
            physical_data.get_resa_params(3, "PA_I", "NI"),
        )
        self.assertEqual(
            profile.ols_parameters(3, "Precision Approach CAT I", "APPROACH"),
            ols_surfaces.get_ols_params(3, "Precision Approach CAT I", "APPROACH"),
        )
        self.assertEqual(
            profile.taxiway_separation_offset(3, "C", "Precision Approach CAT I"),
            taxiway.get_taxiway_separation_offset(3, "C", "Precision Approach CAT I"),
        )

    def test_mos139_baulked_landing_table_notes(self):
        profile = get_ruleset_profile("mos139_2019")

        inner_approach = profile.inner_approach_parameters(3, "Precision Approach CAT I")
        self.assertEqual(inner_approach["width"], 120.0)

        inner_approach_f = profile.inner_approach_parameters(3, "Precision Approach CAT I", "F")
        self.assertEqual(inner_approach_f["width"], 140.0)
        self.assertEqual(inner_approach_f["width_ref"], "MOS 7.10 Table 7.15(1) note g")

        code_1 = profile.baulked_landing_parameters(1, "Precision Approach CAT I")
        self.assertIsNone(code_1["start_dist_from_thr"])
        self.assertEqual(code_1["start_dist_rule"], "distance_to_end_of_runway_strip")
        self.assertEqual(code_1["start_dist_ref"], "MOS 7.12 Table 7.15(1) note e")

        code_3 = profile.baulked_landing_parameters(3, "Precision Approach CAT I")
        self.assertEqual(code_3["start_dist_from_thr"], 1800.0)
        self.assertEqual(code_3["start_dist_rule"], "1800_m_or_end_of_runway_strip_whichever_is_less")
        self.assertEqual(code_3["start_dist_ref"], "MOS 7.12 Table 7.15(1) note f")
        self.assertEqual(code_3["width"], 120.0)

        code_3_f = profile.baulked_landing_parameters(3, "Precision Approach CAT I", "F")
        self.assertEqual(code_3_f["width"], 140.0)
        self.assertEqual(code_3_f["width_ref"], "MOS 7.12 Table 7.15(1) note g")

    def test_mos139_threshold_marking_params(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(profile.threshold_marking_params(30.0), (8, 1.5))
        self.assertEqual(profile.threshold_marking_params(45.0), (12, 1.7))
        self.assertEqual(profile.threshold_marking_params(30.005), (8, 1.5))
        self.assertIsNone(profile.threshold_marking_params(40.0))

    def test_mos139_centreline_marking_width(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.centreline_marking_width(4, "Non-Precision Approach (NPA)", "Non-Instrument (NI)"),
            0.45,
        )
        self.assertEqual(
            profile.centreline_marking_width(2, "Non-Precision Approach (NPA)", "Non-Instrument (NI)"),
            0.3,
        )
        self.assertEqual(
            profile.centreline_marking_width(3, "Precision Approach CAT II/III", "Precision Approach CAT I"),
            0.9,
        )

    def test_mos139_aiming_point_rule(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.aiming_point_rule(45.0, 700.0, "Precision Approach CAT I"),
            (150.0, 30.0, 4.0, 6.0, "MOS 8.22(3)"),
        )
        self.assertEqual(
            profile.aiming_point_rule(45.0, 2400.0, "Precision Approach CAT I"),
            (400.0, 45.0, 9.0, 23.0, "MOS 8.22(3)"),
        )
        self.assertEqual(
            profile.aiming_point_rule(30.0, 1800.0, "Non-Instrument (NI)"),
            (300.0, 45.0, 6.0, 17.0, "MOS 8.22(8)"),
        )
        self.assertIsNone(profile.aiming_point_rule(23.0, 1800.0, "Non-Instrument (NI)"))

    def test_mos139_touchdown_zone_offsets(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(profile.touchdown_zone_offsets(800.0), [300.0])
        self.assertEqual(profile.touchdown_zone_offsets(1200.0), [150.0, 300.0, 450.0, 600.0])
        self.assertEqual(
            profile.touchdown_zone_offsets(2400.0),
            [150.0, 300.0, 450.0, 600.0, 750.0, 900.0],
        )

    def test_mos139_runway_holding_position_rule(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(
            profile.runway_holding_position_rule(3, "Precision Approach CAT I"),
            (90.0, "MOS 8.39(7); Table 6.56(1)"),
        )
        self.assertEqual(
            profile.runway_holding_position_rule(1, "Non-Precision Approach (NPA)"),
            (40.0, "MOS 8.39(7); Table 6.56(1)"),
        )
        self.assertIsNone(profile.runway_holding_position_rule(1, "Precision Approach CAT II/III"))

    def test_mos139_parallel_runway_separation(self):
        profile = get_ruleset_profile("mos139_2019")
        self.assertEqual(profile.capability_status("physical.parallel_runway_separation"), "supported")
        self.assertEqual(
            profile.parallel_runway_separation(
                1,
                4,
                "Non-Instrument (NI)",
                "Non-Instrument (NI)",
                "simultaneous",
            )["distance_m"],
            210.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                1,
                2,
                "Non-Instrument (NI)",
                "Non-Instrument (NI)",
            )["distance_m"],
            150.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "independent_parallel_approaches",
            )["distance_m"],
            1035.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "dependent_parallel_approaches",
            )["distance_m"],
            915.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "independent_parallel_departures",
            )["distance_m"],
            760.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "segregated_parallel_operations",
                arrival_threshold_stagger_m=300.0,
            )["distance_m"],
            760.0,
        )
        self.assertIsNone(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Instrument (NI)",
            )
        )

    def test_easa_profile_smoke_checks(self):
        profile = get_ruleset_profile("easa_cs_adr_dsn_issue_7")
        self.assertEqual(profile.status, "draft")
        self.assertEqual(profile.capability_status("ols.airport_wide"), "partial")
        self.assertEqual(profile.classify_runway_type("Precision Approach CAT I"), "PA_I")
        easa_strip = profile.strip_parameters(3, "PA_I", 45.0)
        self.assertEqual(easa_strip["overall_width"], 280.0)
        self.assertEqual(easa_strip["overall_width_ref"], easa_strip["easa_overall_width_ref"])
        self.assertEqual(easa_strip["graded_width_ref"], easa_strip["easa_graded_width_ref"])
        self.assertEqual(easa_strip["extension_length_ref"], easa_strip["easa_extension_length_ref"])
        easa_resa = profile.resa_parameters(3, "PA_I", "NI")
        self.assertEqual(easa_resa["length"], 240.0)
        self.assertEqual(easa_resa["applicability_ref"], easa_resa["easa_applicability_ref"])
        self.assertEqual(easa_resa["length_ref"], easa_resa["easa_length_ref"])
        self.assertEqual(easa_resa["width_ref"], easa_resa["easa_width_ref"])
        self.assertEqual(profile.threshold_marking_params(45.0), (12, 1.8))
        self.assertEqual(profile.runway_edge_spacing_for_end("Non-Precision Approach (NPA)"), 60.0)
        self.assertEqual(profile.ihs_base_height(), 45.0)
        self.assertEqual(profile.ols_parameters(3, "Precision Approach CAT I", "APPROACH")[0]["start_width"], 280.0)
        self.assertEqual(profile.ols_parameters(3, "Precision Approach CAT I", "Inner Approach")["width"], 120.0)
        self.assertEqual(profile.ols_parameters(3, None, "Take-off climb")["final_width"], 1200.0)
        self.assertEqual(
            profile.taxiway_separation_offset(3, "C", "Precision Approach CAT I")["offset_m"],
            158.0,
        )

    def test_easa_physical_strip_references_distinguish_npa_from_precision(self):
        profile = get_ruleset_profile("easa_cs_adr_dsn_issue_7")

        npa_strip = profile.strip_parameters(3, "NPA", 45.0)
        self.assertEqual(npa_strip["overall_width"], 280.0)
        self.assertEqual(npa_strip["overall_width_ref"], "CS ADR-DSN.B.160(b)(1) Code 3 non-precision approach")

        precision_strip = profile.strip_parameters(3, "PA_I", 45.0)
        self.assertEqual(precision_strip["overall_width"], 280.0)
        self.assertEqual(precision_strip["overall_width_ref"], "CS ADR-DSN.B.160(a)(1) Code 3 precision approach")

        non_instrument_strip = profile.strip_parameters(3, "NI", 45.0)
        self.assertEqual(non_instrument_strip["overall_width"], 150.0)
        self.assertEqual(non_instrument_strip["overall_width_ref"], "CS ADR-DSN.B.160(c)(1) Code 3 non-instrument")

    def test_easa_physical_traceability_is_operational_grade_for_verified_items(self):
        traceability = easa_physical_data.get_physical_traceability()
        self.assertEqual(traceability["source_publication"], "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7")

        expected_items = {
            "strip_length": "CS ADR-DSN.B.155",
            "strip_overall_width": "CS ADR-DSN.B.160",
            "strip_graded_width": "CS ADR-DSN.B.175",
            "resa_applicability": "CS ADR-DSN.C.210",
            "resa_dimensions": "CS ADR-DSN.C.215",
        }
        for item_key, source in expected_items.items():
            with self.subTest(item_key=item_key):
                item = traceability["items"][item_key]
                self.assertEqual(item["source"], source)
                self.assertEqual(item["status"], "operational_verified")

    def test_easa_taxiway_traceability_and_table_d1_values_are_operational_grade(self):
        traceability = easa_taxiway.get_taxiway_traceability()
        self.assertEqual(traceability["source_publication"], "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7")

        expected_items = {
            "taxiway_runway_separation": "CS ADR-DSN.D.260 Table D-1",
            "taxiway_to_taxiway_separation": "CS ADR-DSN.D.260 Table D-1",
            "taxiway_object_separation": "CS ADR-DSN.D.260 Table D-1",
            "stand_taxilane_to_stand_taxilane_separation": "CS ADR-DSN.D.260 Table D-1",
            "stand_taxilane_object_separation": "CS ADR-DSN.D.260 Table D-1",
            "parallel_non_instrument_runways": "CS ADR-DSN.B.050",
            "parallel_instrument_runways": "CS ADR-DSN.B.055",
        }
        for item_key, source in expected_items.items():
            with self.subTest(item_key=item_key):
                item = traceability["items"][item_key]
                self.assertEqual(item["source"], source)
                self.assertEqual(item["status"], "operational_verified")

        expected_runway_taxiway_offsets = {
            (1, "A", "INSTR"): 77.5,
            (2, "A", "INSTR"): 77.5,
            (1, "B", "INSTR"): 82.0,
            (2, "B", "INSTR"): 82.0,
            (3, "B", "INSTR"): 152.0,
            (1, "C", "INSTR"): 88.0,
            (2, "C", "INSTR"): 88.0,
            (3, "C", "INSTR"): 158.0,
            (4, "C", "INSTR"): 158.0,
            (3, "D", "INSTR"): 166.0,
            (4, "D", "INSTR"): 166.0,
            (3, "E", "INSTR"): 172.5,
            (4, "E", "INSTR"): 172.5,
            (3, "F", "INSTR"): 180.0,
            (4, "F", "INSTR"): 180.0,
            (1, "A", "NI"): 37.5,
            (2, "A", "NI"): 47.5,
            (1, "B", "NI"): 42.0,
            (2, "B", "NI"): 52.0,
            (3, "B", "NI"): 87.0,
            (1, "C", "NI"): 48.0,
            (2, "C", "NI"): 58.0,
            (3, "C", "NI"): 93.0,
            (4, "C", "NI"): 93.0,
            (3, "D", "NI"): 101.0,
            (4, "D", "NI"): 101.0,
            (3, "E", "NI"): 107.5,
            (4, "E", "NI"): 107.5,
            (3, "F", "NI"): 115.0,
            (4, "F", "NI"): 115.0,
        }
        self.assertEqual(set(easa_taxiway.TAXIWAY_RUNWAY_SEPARATION_PARAMS), set(expected_runway_taxiway_offsets))
        for key, expected_offset in expected_runway_taxiway_offsets.items():
            with self.subTest(key=key):
                params = easa_taxiway.TAXIWAY_RUNWAY_SEPARATION_PARAMS[key]
                self.assertEqual(params["offset_m"], expected_offset)
                self.assertEqual(params["ref"], easa_taxiway.EASA_TAXIWAY_SEPARATION_REF)

        expected_by_letter = {
            "taxiway_to_taxiway": (
                easa_taxiway.TAXIWAY_TO_TAXIWAY_SEPARATION_PARAMS,
                {"A": 23.0, "B": 32.0, "C": 44.0, "D": 63.0, "E": 76.0, "F": 91.0},
            ),
            "taxiway_object": (
                easa_taxiway.TAXIWAY_OBJECT_SEPARATION_PARAMS,
                {"A": 15.5, "B": 20.0, "C": 26.0, "D": 37.0, "E": 43.5, "F": 51.0},
            ),
            "stand_taxilane_to_stand_taxilane": (
                easa_taxiway.STAND_TAXILANE_TO_STAND_TAXILANE_SEPARATION_PARAMS,
                {"A": 19.5, "B": 28.5, "C": 40.5, "D": 59.5, "E": 72.5, "F": 87.5},
            ),
            "stand_taxilane_object": (
                easa_taxiway.STAND_TAXILANE_OBJECT_SEPARATION_PARAMS,
                {"A": 12.0, "B": 16.5, "C": 22.5, "D": 33.5, "E": 40.0, "F": 47.5},
            ),
        }
        for table_name, (actual_params, expected_offsets) in expected_by_letter.items():
            with self.subTest(table_name=table_name):
                self.assertEqual(set(actual_params), set(expected_offsets))
            for code_letter, expected_offset in expected_offsets.items():
                with self.subTest(table_name=table_name, code_letter=code_letter):
                    self.assertEqual(actual_params[code_letter]["offset_m"], expected_offset)
                    self.assertEqual(actual_params[code_letter]["ref"], easa_taxiway.EASA_TAXIWAY_SEPARATION_REF)

    def test_easa_taxiway_and_parallel_runway_smoke_checks(self):
        profile = get_ruleset_profile("easa_cs_adr_dsn_issue_7")
        taxiway_offset = profile.taxiway_separation_offset(2, "A", "Non-Instrument (NI)")
        self.assertEqual(taxiway_offset["offset_m"], 47.5)
        self.assertEqual(taxiway_offset["ref"], "CS ADR-DSN.D.260 Table D-1")
        self.assertEqual(profile.taxiway_to_taxiway_separation("F")["offset_m"], 91.0)
        self.assertEqual(profile.taxiway_object_separation("D")["offset_m"], 37.0)
        self.assertEqual(profile.stand_taxilane_to_stand_taxilane_separation("B")["offset_m"], 28.5)
        self.assertEqual(profile.stand_taxilane_object_separation("E")["offset_m"], 40.0)
        self.assertIsNone(profile.parallel_runway_separation())
        non_instrument_parallel = profile.parallel_runway_separation(
            1,
            4,
            "Non-Instrument (NI)",
            "Non-Instrument (NI)",
            "simultaneous",
        )
        self.assertEqual(non_instrument_parallel["distance_m"], 210.0)
        self.assertEqual(non_instrument_parallel["ref"], "CS ADR-DSN.B.050")
        self.assertEqual(
            profile.parallel_runway_separation(
                1,
                2,
                "Non-Instrument (NI)",
                "Non-Instrument (NI)",
            )["distance_m"],
            150.0,
        )
        self.assertIsNone(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Instrument (NI)",
            )
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "independent_parallel_approaches",
            )["distance_m"],
            1035.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "dependent_parallel_approaches",
            )["distance_m"],
            915.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "independent_parallel_departures",
            )["distance_m"],
            760.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "segregated_parallel_operations",
                arrival_threshold_stagger_m=300.0,
            ),
            {
                "distance_m": 700.0,
                "ref": "CS ADR-DSN.B.055",
                "condition": "Parallel instrument runways intended for segregated parallel operations.",
                "higher_code_number": 4,
                "operation_type": "segregated_parallel_operations",
                "base_distance_m": 760.0,
                "threshold_stagger_m": 300.0,
                "stagger_adjustment_m": -60.0,
                "notes": (
                    "Other combinations of minimum distances should account for ATM and operational aspects. "
                    "Guidance on procedures and facilities for simultaneous operations is in ICAO PANS-ATM "
                    "Doc 4444 Chapter 6, PANS-OPS Doc 8168, and ICAO Doc 9643 SOIR."
                ),
            },
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "segregated_parallel_operations",
                arrival_threshold_stagger_m=-150.0,
            )["distance_m"],
            790.0,
        )
        self.assertEqual(
            profile.parallel_runway_separation(
                3,
                4,
                "Precision Approach CAT I",
                "Non-Precision Approach (NPA)",
                "segregated_parallel_operations",
                arrival_threshold_stagger_m=3000.0,
            )["distance_m"],
            300.0,
        )

    def test_easa_ols_traceability_marks_j_tables_verified_and_interpretations_visible(self):
        traceability = easa_ols_surfaces.get_ols_traceability()
        self.assertEqual(traceability["source_publication"], "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7")

        expected_verified_items = {
            "approach_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "inner_approach_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "inner_transitional_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "balked_landing_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "inner_horizontal_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "conical_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "transitional_surface": "CS ADR-DSN.J.470/J.475/J.480 Table J-1",
            "take_off_climb_surface": "CS ADR-DSN.J.485 Table J-2",
        }
        for item_key, source in expected_verified_items.items():
            with self.subTest(item_key=item_key):
                item = traceability["items"][item_key]
                self.assertEqual(item["source"], source)
                self.assertEqual(item["status"], "operational_verified")

        self.assertEqual(traceability["items"]["outer_horizontal_surface"]["status"], "guidance_only")
        self.assertEqual(traceability["items"]["pa_cat_i_ofz_family_applicability"]["status"], "interpretive")

    def test_easa_ols_table_j1_approach_values_are_regression_checked(self):
        expected_approach_sections = {
            (1, "NI"): [
                {"length": 1600.0, "slope": 0.05, "divergence": 0.10, "start_dist_from_thr": 30.0, "start_width": 60.0},
            ],
            (2, "NI"): [
                {"length": 2500.0, "slope": 0.04, "divergence": 0.10, "start_dist_from_thr": 60.0, "start_width": 80.0},
            ],
            (3, "NI"): [
                {"length": 3000.0, "slope": 0.0333, "divergence": 0.10, "start_dist_from_thr": 60.0, "start_width": 150.0},
            ],
            (4, "NI"): [
                {"length": 3000.0, "slope": 0.025, "divergence": 0.10, "start_dist_from_thr": 60.0, "start_width": 150.0},
            ],
            (1, "NPA"): [
                {"length": 2500.0, "slope": 0.0333, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 140.0},
            ],
            (2, "NPA"): [
                {"length": 2500.0, "slope": 0.0333, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 140.0},
            ],
            (3, "NPA"): [
                {"length": 3000.0, "slope": 0.02, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 280.0},
                {"length": 3600.0, "slope": 0.025, "divergence": 0.15, "variable_length": True},
                {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "variable_length": True, "total_length": 15000.0},
            ],
            (4, "NPA"): [
                {"length": 3000.0, "slope": 0.02, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 280.0},
                {"length": 3600.0, "slope": 0.025, "divergence": 0.15, "variable_length": True},
                {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "variable_length": True, "total_length": 15000.0},
            ],
            (1, "PA_I"): [
                {"length": 3000.0, "slope": 0.025, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 140.0},
                {"length": 12000.0, "slope": 0.03, "divergence": 0.15, "total_length": 15000.0},
            ],
            (2, "PA_I"): [
                {"length": 3000.0, "slope": 0.025, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 140.0},
                {"length": 12000.0, "slope": 0.03, "divergence": 0.15, "total_length": 15000.0},
            ],
            (3, "PA_I"): [
                {"length": 3000.0, "slope": 0.02, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 280.0},
                {"length": 3600.0, "slope": 0.025, "divergence": 0.15, "variable_length": True},
                {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "variable_length": True, "total_length": 15000.0},
            ],
            (4, "PA_I"): [
                {"length": 3000.0, "slope": 0.02, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 280.0},
                {"length": 3600.0, "slope": 0.025, "divergence": 0.15, "variable_length": True},
                {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "variable_length": True, "total_length": 15000.0},
            ],
            (3, "PA_II_III"): [
                {"length": 3000.0, "slope": 0.02, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 280.0},
                {"length": 3600.0, "slope": 0.025, "divergence": 0.15, "variable_length": True},
                {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "variable_length": True, "total_length": 15000.0},
            ],
            (4, "PA_II_III"): [
                {"length": 3000.0, "slope": 0.02, "divergence": 0.15, "start_dist_from_thr": 60.0, "start_width": 280.0},
                {"length": 3600.0, "slope": 0.025, "divergence": 0.15, "variable_length": True},
                {"length": 8400.0, "slope": 0.0, "divergence": 0.15, "variable_length": True, "total_length": 15000.0},
            ],
        }
        self.assertEqual(set(easa_ols_surfaces.APPROACH_PARAMS), set(expected_approach_sections))
        for key, expected_sections in expected_approach_sections.items():
            actual_sections = easa_ols_surfaces.APPROACH_PARAMS[key]
            self.assertEqual(len(actual_sections), len(expected_sections), key)
            for index, expected_section in enumerate(expected_sections):
                with self.subTest(key=key, section=index):
                    actual_section = actual_sections[index]
                    for field, expected_value in expected_section.items():
                        self.assertEqual(actual_section[field], expected_value)
                    self.assertIn("Table J-1", actual_section["ref"])

    def test_easa_ols_table_j1_surface_values_are_regression_checked(self):
        expected_conical = {
            (1, "NI"): 35.0,
            (2, "NI"): 55.0,
            (3, "NI"): 75.0,
            (4, "NI"): 100.0,
            (1, "NPA"): 60.0,
            (2, "NPA"): 60.0,
            (3, "NPA"): 75.0,
            (4, "NPA"): 100.0,
            (1, "PA_I"): 60.0,
            (2, "PA_I"): 60.0,
            (3, "PA_I"): 100.0,
            (4, "PA_I"): 100.0,
            (3, "PA_II_III"): 100.0,
            (4, "PA_II_III"): 100.0,
        }
        self.assertEqual(set(easa_ols_surfaces.CONICAL_PARAMS), set(expected_conical))
        for key, expected_height in expected_conical.items():
            with self.subTest(table="conical", key=key):
                params = easa_ols_surfaces.CONICAL_PARAMS[key]
                self.assertEqual(params["slope"], 0.05)
                self.assertEqual(params["height_extent_agl"], expected_height)

        expected_ihs_radius = {
            (1, "NI"): 2000.0,
            (2, "NI"): 2500.0,
            (3, "NI"): 4000.0,
            (4, "NI"): 4000.0,
            (1, "NPA"): 3500.0,
            (2, "NPA"): 3500.0,
            (3, "NPA"): 4000.0,
            (4, "NPA"): 4000.0,
            (1, "PA_I"): 3500.0,
            (2, "PA_I"): 3500.0,
            (3, "PA_I"): 4000.0,
            (4, "PA_I"): 4000.0,
            (3, "PA_II_III"): 4000.0,
            (4, "PA_II_III"): 4000.0,
        }
        self.assertEqual(set(easa_ols_surfaces.IHS_PARAMS), set(expected_ihs_radius))
        for key, expected_radius in expected_ihs_radius.items():
            with self.subTest(table="ihs", key=key):
                params = easa_ols_surfaces.IHS_PARAMS[key]
                self.assertEqual(params["height_agl"], 45.0)
                self.assertEqual(params["radius"], expected_radius)

        expected_transitional_slope = {
            (1, "NI"): 0.20,
            (2, "NI"): 0.20,
            (3, "NI"): 0.143,
            (4, "NI"): 0.143,
            (1, "NPA"): 0.20,
            (2, "NPA"): 0.20,
            (3, "NPA"): 0.143,
            (4, "NPA"): 0.143,
            (1, "PA_I"): 0.143,
            (2, "PA_I"): 0.143,
            (3, "PA_I"): 0.143,
            (4, "PA_I"): 0.143,
            (3, "PA_II_III"): 0.143,
            (4, "PA_II_III"): 0.143,
        }
        self.assertEqual(set(easa_ols_surfaces.TRANSITIONAL_PARAMS), set(expected_transitional_slope))
        for key, expected_slope in expected_transitional_slope.items():
            with self.subTest(table="transitional", key=key):
                self.assertEqual(easa_ols_surfaces.TRANSITIONAL_PARAMS[key]["slope"], expected_slope)

    def test_easa_ols_table_j1_precision_ofz_values_are_regression_checked(self):
        expected_inner_approach = {
            (1, "PA_I"): {"width": 90.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.025, "code_letter_f_width": None},
            (2, "PA_I"): {"width": 90.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.025, "code_letter_f_width": None},
            (3, "PA_I"): {"width": 120.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.02, "code_letter_f_width": 140.0},
            (4, "PA_I"): {"width": 120.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.02, "code_letter_f_width": 140.0},
            (3, "PA_II_III"): {"width": 120.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.02, "code_letter_f_width": 140.0},
            (4, "PA_II_III"): {"width": 120.0, "start_dist_from_thr": 60.0, "length": 900.0, "slope": 0.02, "code_letter_f_width": 140.0},
        }
        self.assertEqual(set(easa_ols_surfaces.INNER_APPROACH_PARAMS), set(expected_inner_approach))
        for key, expected_fields in expected_inner_approach.items():
            with self.subTest(table="inner_approach", key=key):
                for field, expected_value in expected_fields.items():
                    self.assertEqual(easa_ols_surfaces.INNER_APPROACH_PARAMS[key][field], expected_value)

        expected_inner_transitional = {
            (1, "PA_I"): 0.40,
            (2, "PA_I"): 0.40,
            (3, "PA_I"): 0.333,
            (4, "PA_I"): 0.333,
            (3, "PA_II_III"): 0.333,
            (4, "PA_II_III"): 0.333,
        }
        self.assertEqual(set(easa_ols_surfaces.INNER_TRANSITIONAL_PARAMS), set(expected_inner_transitional))
        for key, expected_slope in expected_inner_transitional.items():
            with self.subTest(table="inner_transitional", key=key):
                self.assertEqual(easa_ols_surfaces.INNER_TRANSITIONAL_PARAMS[key]["slope"], expected_slope)

        expected_balked_landing = {
            (1, "PA_I"): {"width": 90.0, "start_dist_from_thr": None, "divergence": 0.10, "slope": 0.04, "code_letter_f_width": None},
            (2, "PA_I"): {"width": 90.0, "start_dist_from_thr": None, "divergence": 0.10, "slope": 0.04, "code_letter_f_width": None},
            (3, "PA_I"): {"width": 120.0, "start_dist_from_thr": 1800.0, "divergence": 0.10, "slope": 0.0333, "code_letter_f_width": 140.0},
            (4, "PA_I"): {"width": 120.0, "start_dist_from_thr": 1800.0, "divergence": 0.10, "slope": 0.0333, "code_letter_f_width": 140.0},
            (3, "PA_II_III"): {"width": 120.0, "start_dist_from_thr": 1800.0, "divergence": 0.10, "slope": 0.0333, "code_letter_f_width": 140.0},
            (4, "PA_II_III"): {"width": 120.0, "start_dist_from_thr": 1800.0, "divergence": 0.10, "slope": 0.0333, "code_letter_f_width": 140.0},
        }
        self.assertEqual(set(easa_ols_surfaces.BALKED_LANDING_PARAMS), set(expected_balked_landing))
        for key, expected_fields in expected_balked_landing.items():
            with self.subTest(table="balked_landing", key=key):
                for field, expected_value in expected_fields.items():
                    self.assertEqual(easa_ols_surfaces.BALKED_LANDING_PARAMS[key][field], expected_value)

    def test_easa_ols_table_j2_takeoff_climb_values_are_regression_checked(self):
        expected_tocs = {
            1: {"inner_edge_width": 60.0, "inner_edge_width_clearway": 150.0, "origin_offset": 30.0, "divergence": 0.10, "final_width": 380.0, "length": 1600.0, "slope": 0.05},
            2: {"inner_edge_width": 80.0, "inner_edge_width_clearway": 150.0, "origin_offset": 60.0, "divergence": 0.10, "final_width": 580.0, "length": 2500.0, "slope": 0.04},
            3: {"inner_edge_width": 180.0, "inner_edge_width_clearway": 180.0, "origin_offset": 60.0, "divergence": 0.125, "final_width": 1200.0, "final_width_turning": 1800.0, "length": 15000.0, "slope": 0.02},
            4: {"inner_edge_width": 180.0, "inner_edge_width_clearway": 180.0, "origin_offset": 60.0, "divergence": 0.125, "final_width": 1200.0, "final_width_turning": 1800.0, "length": 15000.0, "slope": 0.02},
        }
        self.assertEqual(set(easa_ols_surfaces.TOCS_PARAMS), set(expected_tocs))
        for key, expected_fields in expected_tocs.items():
            with self.subTest(key=key):
                actual_params = easa_ols_surfaces.TOCS_PARAMS[key]
                for field, expected_value in expected_fields.items():
                    self.assertEqual(actual_params[field], expected_value)
                self.assertIn("Table J-2", actual_params["ref"])

        self.assertEqual(easa_ols_surfaces.get_tocs_params(1, clearway_provided=True)["inner_edge_width"], 150.0)
        self.assertEqual(easa_ols_surfaces.get_tocs_params(3, turning_track_gt_15_deg=True)["final_width"], 1800.0)
        self.assertEqual(easa_ols_surfaces.get_tocs_params(3)["slope_reduced_guidance"], 0.016)
        with self.assertLogs("rulesets.easa.ols_surfaces", level="WARNING"):
            self.assertIsNone(easa_ols_surfaces.get_tocs_params(5))

    def test_easa_marking_traceability_marks_verified_and_interpretive_items(self):
        traceability = easa_markings.get_marking_traceability()
        self.assertEqual(traceability["source_publication"], "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7")

        expected_statuses = {
            "runway_centreline_marking_width": ("CS ADR-DSN.L.530", "operational_verified"),
            "threshold_marking_stripe_count": ("CS ADR-DSN.L.535", "operational_verified"),
            "threshold_marking_representative_stripe_width": ("CS ADR-DSN.L.535", "interpretive"),
            "aiming_point_marking_table": ("CS ADR-DSN.L.540 Table L-1", "operational_verified"),
            "aiming_point_non_instrument_policy": ("CS ADR-DSN.L.540", "interpretive"),
            "touchdown_zone_pair_counts": ("CS ADR-DSN.L.545", "operational_verified"),
            "touchdown_zone_offsets": ("CS ADR-DSN.L.545", "derived_verified"),
            "runway_holding_position_marking": ("CS ADR-DSN.L.575", "accepted_unsupported"),
        }
        for item_key, (source, status) in expected_statuses.items():
            with self.subTest(item_key=item_key):
                item = traceability["items"][item_key]
                self.assertEqual(item["source"], source)
                self.assertEqual(item["status"], status)

    def test_easa_marking_centreline_and_threshold_values_are_regression_checked(self):
        expected_thresholds = {
            18.0: (4, 1.8),
            23.0: (6, 1.8),
            30.0: (8, 1.8),
            45.0: (12, 1.8),
            60.0: (16, 1.8),
        }
        self.assertEqual(easa_markings.THRESHOLD_MARKING_PARAMS_BY_WIDTH, expected_thresholds)
        for runway_width, expected_params in expected_thresholds.items():
            with self.subTest(runway_width=runway_width):
                self.assertEqual(easa_markings.threshold_marking_params(runway_width), expected_params)

        self.assertEqual(easa_markings.threshold_marking_params(30.005), (8, 1.8))
        self.assertIsNone(easa_markings.threshold_marking_params(40.0))
        self.assertEqual(easa_markings.centreline_marking_width(4, "Non-Precision Approach (NPA)", "Non-Instrument (NI)"), 0.45)
        self.assertEqual(easa_markings.centreline_marking_width(2, "Non-Precision Approach (NPA)", "Non-Instrument (NI)"), 0.3)
        self.assertEqual(easa_markings.centreline_marking_width(3, "Precision Approach CAT I", "Non-Instrument (NI)"), 0.45)
        self.assertEqual(easa_markings.centreline_marking_width(3, "Precision Approach CAT II/III", "Precision Approach CAT I"), 0.9)

    def test_easa_marking_aiming_point_values_are_regression_checked(self):
        expected_aiming_point_rules = (
            (800.0, 150.0, 30.0, 4.0, 6.0, "CS ADR-DSN.L.540 Table L-1"),
            (1200.0, 250.0, 30.0, 6.0, 9.0, "CS ADR-DSN.L.540 Table L-1"),
            (2400.0, 300.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
            (None, 400.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
        )
        self.assertEqual(easa_markings.AIMING_POINT_RULES, expected_aiming_point_rules)
        self.assertEqual(
            easa_markings.aiming_point_rule(45.0, 700.0, "Precision Approach CAT I"),
            (150.0, 30.0, 4.0, 6.0, "CS ADR-DSN.L.540 Table L-1"),
        )
        self.assertEqual(
            easa_markings.aiming_point_rule(45.0, 800.0, "Precision Approach CAT I"),
            (250.0, 30.0, 6.0, 9.0, "CS ADR-DSN.L.540 Table L-1"),
        )
        self.assertEqual(
            easa_markings.aiming_point_rule(45.0, 1200.0, "Non-Precision Approach (NPA)"),
            (300.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
        )
        self.assertEqual(
            easa_markings.aiming_point_rule(45.0, 2400.0, "Non-Precision Approach (NPA)"),
            (400.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 Table L-1"),
        )
        self.assertEqual(
            easa_markings.aiming_point_rule(30.0, 1800.0, "Non-Instrument (NI)"),
            (300.0, 45.0, 9.0, 18.0, "CS ADR-DSN.L.540 (default)"),
        )
        self.assertIsNone(easa_markings.aiming_point_rule(23.0, 1800.0, "Non-Instrument (NI)"))

    def test_easa_marking_touchdown_zone_and_holding_values_are_regression_checked(self):
        expected_touchdown_zone_rules = (
            (900.0, [300.0]),
            (1200.0, [150.0, 450.0]),
            (1500.0, [150.0, 450.0, 600.0]),
            (2400.0, [150.0, 450.0, 600.0, 750.0]),
            (None, [150.0, 300.0, 600.0, 750.0, 900.0, 1050.0]),
        )
        self.assertEqual(easa_markings.TOUCHDOWN_ZONE_OFFSET_RULES, expected_touchdown_zone_rules)
        self.assertEqual(easa_markings.touchdown_zone_offsets(899.9), [300.0])
        self.assertEqual(easa_markings.touchdown_zone_offsets(900.0), [150.0, 450.0])
        self.assertEqual(easa_markings.touchdown_zone_offsets(1200.0), [150.0, 450.0, 600.0])
        self.assertEqual(easa_markings.touchdown_zone_offsets(1500.0), [150.0, 450.0, 600.0, 750.0])
        self.assertEqual(easa_markings.touchdown_zone_offsets(2400.0), [150.0, 300.0, 600.0, 750.0, 900.0, 1050.0])
        self.assertIsNone(easa_markings.runway_holding_position_rule(3, "Precision Approach CAT I"))

    def test_easa_lighting_traceability_marks_verified_and_fallback_items(self):
        traceability = easa_lighting.get_lighting_traceability()
        self.assertEqual(traceability["source_publication"], "EASA Easy Access Rules for Aerodromes, CS-ADR-DSN Issue 7")

        expected_statuses = {
            "runway_edge_lights": ("CS ADR-DSN.M.675", "operational_verified"),
            "threshold_lights": ("CS ADR-DSN.M.680", "operational_verified_with_interpretive_width_floor"),
            "threshold_wing_bar_lights": ("CS ADR-DSN.M.680", "operational_verified"),
            "runway_end_lights": ("CS ADR-DSN.M.685", "operational_verified_with_interpretive_width_floor"),
            "simple_approach_lighting": ("CS ADR-DSN.M.626", "operational_verified"),
            "precision_approach_cat_i_lighting": ("CS ADR-DSN.M.630", "operational_verified"),
            "precision_approach_cat_ii_iii_lighting": ("CS ADR-DSN.M.635", "operational_verified"),
            "runway_centreline_lights": ("CS ADR-DSN.M.690", "operational_verified_with_applicability_policy"),
            "touchdown_zone_lights": ("CS ADR-DSN.M.695", "operational_verified_with_nominal_gauge"),
            "temporary_displaced_threshold_lights": ("compatibility fallback", "mos_derived_fallback"),
            "approach_profile_selection": (
                "CS ADR-DSN.M.626; CS ADR-DSN.M.630; CS ADR-DSN.M.635",
                "interpretive",
            ),
        }
        for item_key, (source, status) in expected_statuses.items():
            with self.subTest(item_key=item_key):
                item = traceability["items"][item_key]
                self.assertEqual(item["source"], source)
                self.assertEqual(item["status"], status)

    def test_easa_lighting_runway_light_values_are_regression_checked(self):
        self.assertEqual(easa_lighting.RUNWAY_EDGE_INSTRUMENT_SPACING_M, 60.0)
        self.assertEqual(easa_lighting.RUNWAY_EDGE_NON_INSTRUMENT_SPACING_M, 100.0)
        self.assertEqual(easa_lighting.runway_edge_spacing_for_end("Non-Precision Approach (NPA)"), 60.0)
        self.assertEqual(easa_lighting.runway_edge_spacing_for_end("Precision Approach CAT I"), 60.0)
        self.assertEqual(easa_lighting.runway_edge_spacing_for_end("Non-Instrument (NI)"), 100.0)
        self.assertEqual(easa_lighting.runway_edge_start_offset_for_end("Precision Approach CAT I"), 60.0)
        self.assertEqual(easa_lighting.runway_edge_start_offset_for_end("Non-Instrument (NI)"), 0.0)
        self.assertEqual(easa_lighting.runway_edge_start_offset_for_end("Non-Instrument (NI)", True), 100.0)

        self.assertEqual(easa_lighting.PRECISION_THRESHOLD_MAX_SPACING_M, 3.0)
        self.assertEqual(easa_lighting.NON_PRECISION_THRESHOLD_MIN_LIGHTS, 6)
        self.assertEqual(easa_lighting.threshold_light_count_for_end("Non-Precision Approach (NPA)", 45.0), 6)
        self.assertEqual(easa_lighting.threshold_light_count_for_end("Precision Approach CAT I", 45.0), 16)
        self.assertEqual(easa_lighting.threshold_light_count_for_end("Precision Approach CAT I", 18.0), 11)
        self.assertEqual(easa_lighting.THRESHOLD_WING_BAR_LIGHTS_PER_SIDE, 5)
        self.assertEqual(easa_lighting.THRESHOLD_WING_BAR_EXTEND_M, 10.0)
        self.assertEqual(easa_lighting.THRESHOLD_WING_BAR_SPACING_M, 2.5)

        self.assertEqual(easa_lighting.RUNWAY_END_MIN_LIGHTS, 6)
        self.assertEqual(easa_lighting.CAT_III_RUNWAY_END_MAX_SPACING_M, 6.0)
        self.assertEqual(easa_lighting.runway_end_light_count_for_end("Precision Approach CAT II/III", 45.0), 8)
        self.assertEqual(easa_lighting.runway_end_light_count_for_end("Precision Approach CAT I", 45.0), 6)

    def test_easa_lighting_approach_and_centreline_values_are_regression_checked(self):
        self.assertEqual(easa_lighting.SALS_DESIGN_LENGTH_M, 420.0)
        self.assertEqual(easa_lighting.SALS_STANDARD_SPACING_M, 60.0)
        self.assertEqual(easa_lighting.SALS_ENHANCED_SPACING_M, 30.0)
        self.assertEqual(easa_lighting.SALS_CROSSBAR_DISTANCE_M, 300.0)
        self.assertEqual(easa_lighting.SALS_CROSSBAR_LENGTH_NARROW_M, 18.0)
        self.assertEqual(easa_lighting.SALS_CROSSBAR_LENGTH_STANDARD_M, 30.0)

        self.assertEqual(easa_lighting.PRECISION_APPROACH_DESIGN_LENGTH_M, 900.0)
        self.assertEqual(easa_lighting.PRECISION_APPROACH_MIN_FULL_LENGTH_M, 720.0)
        self.assertEqual(
            [
                easa_lighting.PRECISION_APPROACH_POINT_A_M,
                easa_lighting.PRECISION_APPROACH_POINT_B_M,
                easa_lighting.PRECISION_APPROACH_POINT_C_M,
                easa_lighting.PRECISION_APPROACH_POINT_D_M,
                easa_lighting.PRECISION_APPROACH_POINT_E_M,
            ],
            [150.0, 300.0, 450.0, 600.0, 750.0],
        )
        self.assertEqual(easa_lighting.PRECISION_CROSSBAR_LENGTH_M, 30.0)
        self.assertEqual(easa_lighting.CAT_II_III_SIDE_ROW_INNER_SPACING_M, 18.0)
        self.assertEqual(easa_lighting.CAT_II_III_SIDE_ROW_HALF_INNER_SPACING_M, 9.0)
        self.assertEqual(easa_lighting.CAT_II_III_POINT_B_CROSSBAR_HALF_WIDTH_M, 15.0)
        self.assertEqual(easa_lighting.CAT_II_III_CROSSBAR_MAX_SPACING_M, 2.7)
        self.assertEqual(easa_lighting.CAT_II_III_SIDE_ROWS_TO_M, 270.0)

        self.assertEqual(easa_lighting.RUNWAY_CENTRELINE_DEFAULT_SPACING_M, 15.0)
        self.assertEqual(easa_lighting.RUNWAY_CENTRELINE_LOW_VIS_SPACING_M, 30.0)
        self.assertEqual(easa_lighting.RUNWAY_CENTRELINE_MAX_OFFSET_M, 0.6)
        self.assertEqual(easa_lighting.RUNWAY_CENTRELINE_RED_ZONE_M, 300.0)
        self.assertEqual(easa_lighting.RUNWAY_CENTRELINE_ALTERNATING_ZONE_M, 900.0)
        self.assertTrue(easa_lighting.runway_centreline_required("Non-Instrument (NI)", "Precision Approach CAT II/III"))
        self.assertTrue(easa_lighting.runway_centreline_required("Non-Instrument (NI)", "Non-Instrument (NI)", True))
        self.assertFalse(easa_lighting.runway_centreline_required("Non-Instrument (NI)", "Non-Instrument (NI)", False))
        self.assertTrue(easa_lighting.runway_centreline_recommended("Non-Instrument (NI)", "Non-Instrument (NI)", 60.0))
        self.assertEqual(easa_lighting.runway_centreline_spacing(True), 15.0)
        self.assertEqual(easa_lighting.runway_centreline_spacing(False), 30.0)

    def test_easa_lighting_tdz_and_profile_values_are_regression_checked(self):
        self.assertEqual(easa_lighting.TDZ_LENGTH_M, 900.0)
        self.assertEqual(easa_lighting.TDZ_ROW_SPACING_M, 60.0)
        self.assertEqual(easa_lighting.TDZ_BARRETTE_LIGHTS, 3)
        self.assertEqual(easa_lighting.TDZ_BARRETTE_SPACING_M, 1.5)
        self.assertEqual(easa_lighting.TDZ_BARRETTE_LENGTH_MIN_M, 3.0)
        self.assertEqual(easa_lighting.TDZ_BARRETTE_LENGTH_MAX_M, 4.5)
        self.assertEqual(easa_lighting.TDZ_INNER_OFFSET_M, 9.0)
        self.assertEqual(easa_lighting.temp_displaced_threshold_lights_per_side(30.0), 3)
        self.assertEqual(easa_lighting.temp_displaced_threshold_lights_per_side(45.0), 5)

        cat_ii_iii = easa_lighting.approach_profile_for_end("Precision Approach CAT II/III")
        self.assertEqual(cat_ii_iii["length_m"], 900.0)
        self.assertEqual(cat_ii_iii["crossbars_m"], [150.0, 300.0, 450.0, 600.0, 750.0])
        self.assertEqual(cat_ii_iii["side_rows_to_m"], 270.0)
        self.assertEqual(cat_ii_iii["ref_easa"], "CS ADR-DSN.M.635")

        cat_i = easa_lighting.approach_profile_for_end("Precision Approach CAT I")
        self.assertEqual(cat_i["length_m"], 900.0)
        self.assertEqual(cat_i["approach_type"], "cat_i")
        self.assertEqual(cat_i["ref_easa"], "CS ADR-DSN.M.630")

        sals = easa_lighting.approach_profile_for_end("Non-Precision Approach (NPA)")
        self.assertEqual(sals["system"], "Simple Approach Lighting System")
        self.assertEqual(sals["length_m"], 420.0)
        self.assertEqual(sals["crossbars_m"], [300.0])
        self.assertEqual(sals["ref_easa"], "CS ADR-DSN.M.626")

    def test_annex14_profile_scaffold_smoke_checks(self):
        current_profile = get_ruleset_profile("icao_annex14_vol1_current_ols")
        self.assertEqual(current_profile.protected_airspace_model, "annex14_current_ols")
        self.assertEqual(current_profile.capability_status("ols.obstacle_free_surfaces"), "unsupported")
        self.assertEqual(current_profile.capability_status("oes.horizontal"), "unsupported")

        profile = get_ruleset_profile("icao_annex14_vol1_modernised_ofs_oes")
        self.assertEqual(profile.status, "draft")
        self.assertEqual(profile.protected_airspace_model, "annex14_modernised_ofs_oes")
        self.assertEqual(profile.capability_status("classification.reference_code"), "partial")
        self.assertEqual(profile.capability_status("classification.design_group"), "partial")
        self.assertEqual(profile.capability_status("oes.airport_wide"), "partial")
        self.assertEqual(profile.capability_status("oes.horizontal"), "supported")
        self.assertEqual(profile.capability_status("oes.straight_in_instrument_approach"), "supported")
        self.assertEqual(profile.capability_status("oes.precision_approach"), "supported")
        self.assertEqual(profile.capability_status("oes.instrument_departure"), "supported")
        self.assertEqual(profile.capability_status("oes.take_off_climb"), "supported")
        self.assertEqual(profile.capability_status("obstacle_limitation.requirements"), "supported")
        self.assertEqual(profile.capability_status("obstacle_limitation.surface_establishment"), "supported")
        self.assertEqual(profile.classify_runway_type("Precision Approach CAT I"), "PA_I")
        self.assertEqual(profile.precision_type_codes(), {"PA_I", "PA_II_III"})
        self.assertEqual(profile.code_number(799.9)["code_number"], 1)
        self.assertEqual(profile.code_number(800.0)["code_number"], 2)
        self.assertEqual(profile.code_number(1800.0)["code_number"], 4)
        self.assertEqual(profile.code_letter(14.9)["code_letter"], "A")
        self.assertEqual(profile.code_letter(15.0)["code_letter"], "B")
        self.assertEqual(profile.code_letter(65.0)["code_letter"], "F")
        self.assertIsNone(profile.code_letter(80.0))
        self.assertEqual(
            profile.design_group(
                wingspan_m=20.0,
                indicated_airspeed_at_threshold_kmh=161.0,
            )["design_group"],
            "I",
        )
        adg_example = profile.design_group(
            wingspan_m=52.0,
            indicated_airspeed_at_threshold_kmh=224.0,
        )
        self.assertEqual(adg_example["design_group"], "IV")
        self.assertEqual(adg_example["applicable_from"], "2030-11-21")
        self.assertIsNone(profile.oes_parameters(design_group="ADG_III", surface_type="approach"))
        self.assertIsNone(profile.ols_parameters(3, "Precision Approach CAT I", "APPROACH"))
        self.assertEqual(profile.capability_status("ols.runway_approach"), "partial")
        self.assertEqual(
            profile.approach_surface_parameters(
                "I",
                "Non-Instrument (NI)",
                runway_width_m=30.0,
            )["inner_edge_length_m"],
            80.0,
        )
        self.assertEqual(
            profile.approach_surface_parameters(
                "I",
                "Non-Instrument (NI)",
                runway_width_m=30.1,
            )["inner_edge_length_m"],
            100.0,
        )
        self.assertEqual(
            profile.approach_surface_parameters(
                "IIA",
                "Non-Instrument (NI)",
                runway_width_m=45.0,
            )["inner_edge_length_m"],
            100.0,
        )
        self.assertEqual(
            profile.approach_surface_parameters(
                "IIA",
                "Non-Instrument (NI)",
                runway_width_m=45.1,
            )["inner_edge_length_m"],
            110.0,
        )
        self.assertEqual(
            profile.approach_surface_parameters(
                "IIC",
                "Precision Approach CAT I",
                runway_width_m=30.0,
            )["inner_edge_length_m"],
            140.0,
        )
        self.assertEqual(
            profile.approach_surface_parameters(
                "V",
                "Precision Approach CAT I",
            )["length_m"],
            4500.0,
        )
        self.assertAlmostEqual(
            profile.approach_surface_parameters(
                "I",
                "Non-Instrument (NI)",
                slope=0.04,
            )["length_m"],
            2000.0,
        )
        self.assertAlmostEqual(
            profile.approach_surface_parameters(
                "III",
                "Precision Approach CAT I",
                obstacle_clearance_height_m=180.0,
            )["length_m"],
            180.0 / 0.0333,
        )
        self.assertEqual(profile.transitional_surface_parameters()["slope"], 0.20)
        self.assertEqual(
            profile.transitional_surface_parameters()["upper_edge_height_above_highest_threshold_m"],
            60.0,
        )
        self.assertEqual(profile.ols_parameters(3, "Precision Approach CAT I", "transitional")["ref"], "Annex 14 Vol I 4.2.2")
        self.assertEqual(
            profile.inner_approach_surface_parameters("I", "Non-Instrument (NI)")["inner_edge_length_m"],
            60.0,
        )
        self.assertEqual(
            profile.inner_approach_surface_parameters("IIA", "Non-Instrument (NI)")["length_m"],
            1125.0,
        )
        self.assertEqual(
            profile.inner_approach_surface_parameters("I", "Non-Precision Approach (NPA)")["inner_edge_length_m"],
            80.0,
        )
        self.assertEqual(
            profile.inner_approach_surface_parameters("I", "Precision Approach CAT I")["inner_edge_length_m"],
            90.0,
        )
        self.assertEqual(
            profile.inner_approach_surface_parameters(
                "V",
                "Precision Approach CAT I",
                code_letter_f_without_digital_avionics=True,
            )["inner_edge_length_m"],
            140.0,
        )
        self.assertAlmostEqual(
            profile.inner_approach_surface_parameters(
                "I",
                "Non-Instrument (NI)",
                approach_surface_slope=0.025,
            )["length_m"],
            1800.0,
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("I", "Non-Instrument (NI)")["configuration"],
            "vertical_then_inclined",
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("I", "Non-Instrument (NI)")["vertical_section_height_m"],
            6.0,
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("I", "Non-Instrument (NI)")["length_rule"],
            "to_end_of_strip",
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("IIC", "Non-Instrument (NI)")["vertical_section_height_m"],
            8.4,
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("IIC", "Non-Precision Approach (NPA)")["vertical_section_height_m"],
            5.0,
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("III", "Non-Precision Approach (NPA)")["length_m"],
            1800.0,
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("V", "Precision Approach CAT I")["configuration"],
            "precision_single_section",
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("V", "Precision Approach CAT I")["slope"],
            0.333,
        )
        self.assertEqual(
            profile.inner_transitional_surface_parameters("V", "Precision Approach CAT I")["length_rule"],
            "per_4_2_4_3",
        )
        self.assertEqual(
            profile.balked_landing_surface_parameters("I")["distance_rule"],
            "end_of_strip",
        )
        self.assertEqual(
            profile.balked_landing_surface_parameters("I")["inner_edge_length_m"],
            90.0,
        )
        self.assertEqual(
            profile.balked_landing_surface_parameters("III")["distance_from_threshold_m"],
            1800.0,
        )
        self.assertEqual(
            profile.balked_landing_surface_parameters("III")["distance_rule"],
            "1800_m_or_end_of_runway_whichever_is_less",
        )
        self.assertEqual(
            profile.balked_landing_surface_parameters("III")["slope"],
            0.0333,
        )
        self.assertEqual(
            profile.balked_landing_surface_parameters(
                "V",
                code_letter_f_without_digital_avionics=True,
            )["inner_edge_length_m"],
            140.0,
        )
        self.assertEqual(profile.capability_status("ols.obstacle_free_surfaces"), "supported")
        npa_ofs = profile.obstacle_free_surfaces("IV", "Non-Precision Approach (NPA)")
        self.assertEqual(npa_ofs["status"], "data_capture_complete")
        self.assertEqual([surface["surface"] for surface in npa_ofs["groups"]["general"]], ["approach", "transitional"])
        self.assertEqual(
            [surface["surface"] for surface in npa_ofs["groups"]["inner"]],
            ["inner_approach", "inner_transitional"],
        )
        precision_ofs = profile.obstacle_free_surfaces(
            "V",
            "Precision Approach CAT I",
            code_letter_f_without_digital_avionics=True,
        )
        self.assertEqual(
            [surface["surface"] for surface in precision_ofs["groups"]["inner"]],
            ["inner_approach", "inner_transitional", "balked_landing"],
        )
        self.assertEqual(precision_ofs["groups"]["inner"][0]["inner_edge_length_m"], 140.0)
        self.assertEqual(precision_ofs["groups"]["inner"][2]["inner_edge_length_m"], 140.0)
        self.assertEqual(
            profile.oes.surface_families(),
            (
                "horizontal",
                "straight_in_instrument_approach",
                "precision_approach",
                "instrument_departure",
                "take_off_climb",
            ),
        )
        self.assertEqual(profile.horizontal_surface_parameters("I")["radius_m"], 3350.0)
        self.assertEqual(profile.horizontal_surface_parameters("IIA")["height_above_aerodrome_elevation_m"], 45.0)
        self.assertEqual(profile.horizontal_surface_parameters("IIB")["radius_m"], 5350.0)
        self.assertEqual(profile.horizontal_surface_parameters("IIC")["height_above_aerodrome_elevation_m"], 90.0)
        self.assertEqual(profile.oes_parameters(design_group="IV", surface_type="horizontal")["radius_m"], 10750.0)
        horizontal_package = profile.horizontal_surfaces(["I", "IIA", "IIB", "V"])
        self.assertEqual([surface["design_group"] for surface in horizontal_package["surfaces"]], ["I-IIA", "IIB", "V"])
        straight_in = profile.straight_in_instrument_approach_surface_parameters()
        self.assertEqual(straight_in["lower_section"]["height_above_aerodrome_elevation_m"], 45.0)
        self.assertEqual(straight_in["lower_section"]["horizontal_surface"]["radius_m"], 3350.0)
        self.assertEqual(straight_in["upper_section"]["height_above_aerodrome_elevation_m"], 60.0)
        self.assertEqual(straight_in["upper_section"]["shorter_side_length_m"], 7410.0)
        self.assertEqual(straight_in["upper_section"]["longer_side_length_from_threshold_or_thresholds_m"], 5350.0)
        precision_approach = profile.precision_approach_surface_parameters()
        self.assertEqual(precision_approach["ref"], "Annex 14 Vol I Table 4-12")
        self.assertEqual(precision_approach["components"]["approach"]["distance_from_threshold_m"], 60.0)
        self.assertEqual(precision_approach["components"]["approach"]["inner_edge_length_m"], 300.0)
        self.assertEqual(precision_approach["components"]["approach"]["sections"][0]["length_m"], 3000.0)
        self.assertEqual(precision_approach["components"]["approach"]["sections"][1]["length_m"], 9600.0)
        self.assertEqual(precision_approach["components"]["missed_approach"]["distance_after_threshold_m"], 900.0)
        self.assertEqual(precision_approach["components"]["missed_approach"]["sections"][0]["divergence"], 0.1748)
        self.assertEqual(precision_approach["components"]["missed_approach"]["sections"][1]["divergence"], 0.25)
        self.assertEqual(precision_approach["components"]["transitional"]["upper_edge_height_above_threshold_m"], 300.0)
        self.assertEqual(precision_approach["components"]["transitional"]["slope"], 0.143)
        self.assertEqual(profile.oes_parameters(surface_type="precision approach")["surface"], "precision_approach")
        instrument_departure = profile.instrument_departure_surface_parameters()
        self.assertEqual(instrument_departure["inner_edge_length_m"], 300.0)
        self.assertEqual(instrument_departure["inner_edge_elevation_offset_m"], 5.0)
        self.assertEqual(instrument_departure["slope"], 0.025)
        self.assertEqual(instrument_departure["sections"][0]["length_m"], 3500.0)
        self.assertEqual(instrument_departure["sections"][0]["divergence"], 0.268)
        self.assertEqual(instrument_departure["sections"][1]["length_m"], 8300.0)
        self.assertEqual(instrument_departure["sections"][1]["divergence"], 0.578)
        self.assertEqual(profile.oes_parameters(surface_type="instrument departure")["surface"], "instrument_departure")
        light_takeoff = profile.take_off_climb_surface_parameters(
            "IIA",
            max_certificated_takeoff_mass_kg=5700.0,
        )
        self.assertEqual(light_takeoff["mass_category"], "up_to_5700_kg")
        self.assertEqual(light_takeoff["distance_from_runway_end_m"], 60.0)
        self.assertEqual(light_takeoff["final_width_m"], 580.0)
        self.assertEqual(light_takeoff["slope"], 0.04)
        self.assertIsNone(
            profile.take_off_climb_surface_parameters(
                "IIC",
                max_certificated_takeoff_mass_kg=5700.0,
            )
        )
        heavy_takeoff = profile.take_off_climb_surface_parameters("IV", max_certificated_takeoff_mass_kg=5700.1)
        self.assertEqual(heavy_takeoff["mass_category"], "above_5700_kg")
        self.assertEqual(heavy_takeoff["inner_edge_length_m"], 180.0)
        self.assertEqual(heavy_takeoff["final_width_m"], 1800.0)
        self.assertEqual(heavy_takeoff["slope"], 0.02)
        reduced_slope_takeoff = profile.take_off_climb_surface_parameters(
            "V",
            max_certificated_takeoff_mass_kg=5700.1,
            slope=0.016,
        )
        self.assertAlmostEqual(reduced_slope_takeoff["length_m"], 12500.0)
        self.assertEqual(reduced_slope_takeoff["length_adjustment_ref"], "Annex 14 Vol I 4.3.6.9")
        self.assertEqual(profile.oes_parameters(design_group="I", surface_type="take off climb")["surface"], "take_off_climb")
        ofs_requirements = profile.obstacle_free_surface_requirements()
        self.assertEqual(
            ofs_requirements["inner_surfaces"]["fixed_objects"]["rule"],
            "not_permitted_above_surface",
        )
        self.assertIn(
            "frangible",
            ofs_requirements["general_surfaces"]["permitted_objects"]["requirements"],
        )
        self.assertEqual(
            ofs_requirements["general_surfaces"]["existing_obstacles"]["retention_rule"],
            "permitted_only_after_aeronautical_study",
        )
        oes_requirements = profile.obstacle_evaluation_surface_requirements()
        self.assertEqual(
            oes_requirements["penetrating_obstacles"]["rule"],
            "permitted_only_after_aeronautical_study",
        )
        self.assertEqual(
            profile.obstacle_limitation_requirements("OES")["family"],
            "obstacle_evaluation_surfaces",
        )
        self.assertEqual(
            profile.obstacle_free_surface_establishment("NPA")["surfaces"],
            ["approach", "transitional", "inner_approach", "inner_transitional"],
        )
        self.assertEqual(
            profile.obstacle_free_surface_establishment("PA_I")["surfaces"],
            ["approach", "transitional", "inner_approach", "inner_transitional", "balked_landing"],
        )
        self.assertEqual(
            profile.obstacle_evaluation_surface_establishment("precision_approach")["surfaces"],
            ["precision_approach", "specific_oes"],
        )
        self.assertEqual(
            profile.obstacle_evaluation_surface_establishment("take off operations")["surfaces"],
            ["take_off_climb", "specific_oes"],
        )
        self.assertEqual(
            profile.surface_establishment_requirements()["obstacle_evaluation_surfaces"]["overlap_rule"],
            "each_individual_oes_must_be_considered_when_surfaces_overlap",
        )
        self.assertIsNone(profile.strip_parameters(3, "PA_I", 45.0))
        self.assertIsNone(profile.parallel_runway_separation(3, 4, "Precision Approach CAT I", "Precision Approach CAT I"))
        self.assertFalse(profile.runway_type_supports_agl("Precision Approach CAT I"))

    def test_mos139_adapter_matches_ruleset_agl_helpers(self):
        profile = get_ruleset_profile("mos139_2019")
        runway_type = "Precision Approach CAT I"
        for constant_name in [
            "MOS_REF_RUNWAY_EDGE",
            "RUNWAY_EDGE_INSTRUMENT_SPACING_M",
            "RUNWAY_LIGHTING_MIN_WIDTH_M",
            "PRECISION_THRESHOLD_MAX_SPACING_M",
            "RUNWAY_CENTRELINE_MAX_OFFSET_M",
            "TDZ_LENGTH_M",
            "TDZ_MARKING_LENGTH_M",
            "LIGHT_COLOUR_VARIABLE_WHITE",
            "LIGHT_COLOUR_FLASHING_WHITE",
        ]:
            self.assertEqual(profile.agl_value(constant_name), getattr(lighting, constant_name))
        self.assertEqual(
            profile.runway_type_supports_agl(runway_type),
            lighting.runway_type_supports_agl(runway_type),
        )
        self.assertEqual(profile.runway_is_precision(runway_type), lighting.runway_is_precision(runway_type))
        self.assertEqual(
            profile.runway_edge_spacing_for_end("Non-Precision Approach (NPA)"),
            lighting.runway_edge_spacing_for_end("Non-Precision Approach (NPA)"),
        )
        self.assertEqual(
            profile.threshold_light_count_for_end(runway_type, 45.0),
            lighting.threshold_light_count_for_end(runway_type, 45.0),
        )
        self.assertEqual(
            profile.runway_end_light_count_for_end("Precision Approach CAT II/III", 45.0),
            lighting.runway_end_light_count_for_end("Precision Approach CAT II/III", 45.0),
        )
        self.assertEqual(
            profile.temp_displaced_threshold_lights_per_side(30.0),
            lighting.temp_displaced_threshold_lights_per_side(30.0),
        )
        self.assertEqual(
            profile.runway_centreline_required("Non-Instrument (NI)", "Precision Approach CAT II/III", False),
            lighting.runway_centreline_required("Non-Instrument (NI)", "Precision Approach CAT II/III", False),
        )
        self.assertEqual(
            profile.runway_centreline_recommended("Precision Approach CAT I", "Non-Instrument (NI)", 60.0),
            lighting.runway_centreline_recommended("Precision Approach CAT I", "Non-Instrument (NI)", 60.0),
        )
        self.assertEqual(profile.runway_centreline_spacing(True), lighting.runway_centreline_spacing(True))
        self.assertEqual(
            profile.approach_profile_for_end("Precision Approach CAT II/III"),
            lighting.approach_profile_for_end("Precision Approach CAT II/III"),
        )
        self.assertEqual(
            profile.approach_profile_for_end("Non-Instrument (NI)"),
            lighting.approach_profile_for_end("Non-Instrument (NI)"),
        )

    def test_legacy_dimension_shims_forward_to_mos139_sources(self):
        self.assertEqual(
            legacy_ols_dimensions.get_runway_type_abbr("Precision Approach CAT I"),
            classification.get_runway_type_abbr("Precision Approach CAT I"),
        )
        self.assertEqual(
            legacy_agl_dimensions.RUNWAY_LIGHTING_MIN_WIDTH_M,
            lighting.RUNWAY_LIGHTING_MIN_WIDTH_M,
        )
        self.assertEqual(
            legacy_agl_dimensions.approach_profile_for_end("Precision Approach CAT II/III"),
            lighting.approach_profile_for_end("Precision Approach CAT II/III"),
        )

    def test_registry_has_ui_profiles(self):
        profiles = list(iter_ruleset_profiles())
        self.assertGreaterEqual(len(profiles), 1)
        self.assertEqual(profiles[0].display_name, "MOS139 (current)")


if __name__ == "__main__":
    unittest.main()
