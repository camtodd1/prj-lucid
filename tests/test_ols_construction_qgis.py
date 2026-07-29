"""QGIS geometry checks for ruleset-owned nominated OLS tracks."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path
from types import MethodType

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsCoordinateReferenceSystem,
    QgsLayerTreeGroup,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)

from guidelines.ols_guideline import OlsGuidelineMixin
from guidelines.controlling_ols_engine import ControllingOlsCandidate
from rulesets.annex14.profile import (
    ANNEX14_CURRENT_OLS_PROFILE,
    ANNEX14_MODERNISED_OFS_OES_PROFILE,
)
from rulesets.cap168.profile import CAP168_PROFILE
from rulesets.easa.profile import EASA_PROFILE
from rulesets.mos139.profile import MOS139_PROFILE
from rulesets.ols_construction import (
    OlsConstructionContext,
    OlsRunwayContext,
    OlsRunwayEndContext,
)

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder  # noqa: E402


class TrackHarness(OlsGuidelineMixin):
    def __init__(self, context):
        self.ols_construction_context = context

    @staticmethod
    def tr(value):
        return value

    @staticmethod
    def _create_polygon_from_corners(corners, _label):
        ring = list(corners) + [corners[0]]
        return QgsGeometry.fromPolygonXY([ring])

    @staticmethod
    def get_active_protected_airspace_ruleset():
        return CAP168_PROFILE


class CandidateTrackHarness(TrackHarness):
    def __init__(self, context):
        super().__init__(context)
        self.contour_intervals = {}
        self._contour_interval_ruleset_role = "baseline"
        self.candidates = []
        self.registered_contours = []

    def _register_controlling_ols_candidate(self, candidate):
        self.candidates.append(candidate)

    def _register_controlling_ols_contour(self, surface_id, surface_type, feature, source_layer):
        self.registered_contours.append((surface_id, surface_type, feature, source_layer))


def cap_context(track_wkt: str) -> OlsConstructionContext:
    primary = OlsRunwayEndContext(
        direction="primary",
        designator="09",
        threshold_point=QgsPointXY(0.0, 0.0),
        threshold_elevation_m=100.0,
        runway_end_elevation_m=100.0,
        approach_type="Precision Approach CAT I",
        classified_type="PA_I",
        approach_track_type="curved",
        approach_track_wkt=track_wkt,
    )
    reciprocal = OlsRunwayEndContext(
        direction="reciprocal",
        designator="27",
        threshold_point=QgsPointXY(2000.0, 0.0),
        threshold_elevation_m=101.0,
        runway_end_elevation_m=101.0,
        approach_type="Precision Approach CAT I",
        classified_type="PA_I",
    )
    runway = OlsRunwayContext(
        runway_id="09/27",
        original_index=1,
        arc_number=3,
        arc_letter="C",
        width_m=45.0,
        physical_length_m=2000.0,
        threshold_length_m=2000.0,
        primary_threshold_point=primary.threshold_point,
        reciprocal_threshold_point=reciprocal.threshold_point,
        primary_physical_end_point=primary.threshold_point,
        reciprocal_physical_end_point=reciprocal.threshold_point,
        strip_parameters={"overall_width": 280.0},
        ends=(primary, reciprocal),
        generation_data={"original_index": 1},
    )
    return OlsConstructionContext(
        ruleset_id=CAP168_PROFILE.id,
        runways=(runway,),
        arp_point=QgsPointXY(1000.0, 500.0),
    )


class OlsConstructionQgisTests(unittest.TestCase):
    def test_annex14_transition_features_are_repeated_under_each_runway_end(self):
        builder = object.__new__(SafeguardingBuilder)
        fields = QgsFields()
        fields.append(QgsField("surface", QVariant.String))
        fields.append(QgsField("end_desig", QVariant.String))

        def feature(surface, end_desig):
            item = QgsFeature(fields)
            item.setAttributes([surface, end_desig])
            return item

        shared_transitional = feature("transitional", "")
        shared_inner_transitional = feature("inner_transitional", "")
        end_16_transitional = feature("transitional", "16")
        end_34_transitional = feature("transitional", "34")
        runway_wide_horizontal = feature("horizontal", "")
        features = [
            shared_transitional,
            shared_inner_transitional,
            end_16_transitional,
            end_34_transitional,
            runway_wide_horizontal,
        ]

        end_16 = builder._annex14_features_for_end(features, "16")
        end_34 = builder._annex14_features_for_end(features, "34")

        self.assertIn(shared_transitional, end_16)
        self.assertIn(shared_transitional, end_34)
        self.assertIn(shared_inner_transitional, end_16)
        self.assertIn(shared_inner_transitional, end_34)
        self.assertIn(end_16_transitional, end_16)
        self.assertNotIn(end_34_transitional, end_16)
        self.assertNotIn(runway_wide_horizontal, end_16)
        self.assertEqual(
            builder._annex14_runway_label_for_surface(
                "transitional",
                "16",
                "16/34",
            ),
            "16",
        )

    @staticmethod
    def _easa_generation_fixture():
        primary = OlsRunwayEndContext(
            direction="primary",
            designator="09",
            threshold_point=QgsPointXY(0.0, 0.0),
            threshold_elevation_m=100.0,
            runway_end_elevation_m=100.0,
            approach_type="Non-Precision Approach (NPA)",
            classified_type="NPA",
            clearway_length_m=200.0,
        )
        reciprocal = OlsRunwayEndContext(
            direction="reciprocal",
            designator="27",
            threshold_point=QgsPointXY(3000.0, 0.0),
            threshold_elevation_m=101.0,
            runway_end_elevation_m=101.0,
            approach_type="Non-Precision Approach (NPA)",
            classified_type="NPA",
        )
        runway = OlsRunwayContext(
            runway_id="09/27",
            original_index=1,
            arc_number=3,
            arc_letter="C",
            width_m=45.0,
            physical_length_m=3000.0,
            threshold_length_m=3000.0,
            primary_threshold_point=primary.threshold_point,
            reciprocal_threshold_point=reciprocal.threshold_point,
            primary_physical_end_point=primary.threshold_point,
            reciprocal_physical_end_point=reciprocal.threshold_point,
            strip_parameters={
                "overall_width": 280.0,
                "graded_width": 150.0,
                "extension_length": 60.0,
            },
            ends=(primary, reciprocal),
            generation_data={"original_index": 1},
        )
        context = OlsConstructionContext(
            ruleset_id=EASA_PROFILE.id,
            runways=(runway,),
            reference_elevation_datum_m=123.0,
            arp_point=QgsPointXY(1500.0, 500.0),
        )
        builder = object.__new__(SafeguardingBuilder)
        builder.ruleset = EASA_PROFILE
        builder.baseline_ols_ruleset = EASA_PROFILE
        builder.protected_airspace_ruleset = EASA_PROFILE
        builder.ols_construction_context = context
        builder.translator = None
        builder.contour_intervals = {}
        builder._contour_interval_ruleset_role = "baseline"
        return builder, runway, primary, context

    def test_easa_approach_and_tocs_generate_source_referenced_valid_geometry(self):
        builder, runway, primary, _context = self._easa_generation_fixture()
        runway_data = {
            "short_name": "09/27",
            "original_index": 1,
            "arc_num": "3",
            "type1": "Non-Precision Approach (NPA)",
            "type2": "Non-Precision Approach (NPA)",
            "thr_point": runway.primary_threshold_point,
            "rec_thr_point": runway.reciprocal_threshold_point,
            "thr_displaced_1": 0.0,
            "thr_displaced_2": 0.0,
            "calculated_strip_dims": dict(runway.strip_parameters),
        }
        rwy_params = builder._get_runway_parameters(
            runway.primary_threshold_point,
            runway.reciprocal_threshold_point,
        )
        self.assertIsNotNone(rwy_params)

        approach_features, approach_contours = builder._generate_approach_surface(
            runway_data,
            rwy_params,
            3,
            primary.approach_type,
            primary.threshold_point,
            rwy_params["azimuth_r_p"],
            primary.designator,
            primary.threshold_elevation_m,
            direction=primary.direction,
        )
        self.assertEqual(
            [feature.attribute("len_m") for feature in approach_features],
            [3000.0, 320.0, 11680.0],
        )
        self.assertTrue(all(feature.geometry().isGeosValid() for feature in approach_features))
        self.assertTrue(
            all(str(feature.attribute("ref_mos")).startswith("CS ADR-DSN.J.") for feature in approach_features)
        )
        self.assertGreater(len(approach_contours), 0)

        tocs_feature, tocs_contours = builder._generate_tocs(
            runway_data,
            rwy_params,
            3,
            None,
            runway.reciprocal_threshold_point,
            primary.clearway_length_m,
            rwy_params["azimuth_p_r"],
            primary.designator,
            primary.threshold_elevation_m,
            direction=primary.direction,
        )
        self.assertIsNotNone(tocs_feature)
        self.assertTrue(tocs_feature.geometry().isGeosValid())
        self.assertEqual(tocs_feature.attribute("origin_offset"), 200.0)
        self.assertEqual(tocs_feature.attribute("len_m"), 15000.0)
        self.assertIn("CS ADR-DSN.J.485", tocs_feature.attribute("ref_mos"))
        self.assertGreater(len(tocs_contours), 0)

    def test_easa_airport_wide_and_cat23_ofz_geometry_is_source_referenced(self):
        builder, runway, _primary, context = self._easa_generation_fixture()
        runway_data = {
            "short_name": "09/27",
            "original_index": 1,
            "arc_num": "3",
            "arc_let": "C",
            "type1": "Precision Approach CAT II/III",
            "type2": "Precision Approach CAT II/III",
            "thr_point": runway.primary_threshold_point,
            "rec_thr_point": runway.reciprocal_threshold_point,
            "thr_displaced_1": 0.0,
            "thr_displaced_2": 0.0,
            "threshold_elev_1": 100.0,
            "threshold_elev_2": 101.0,
            "runway_end_elev_1": 100.0,
            "runway_end_elev_2": 101.0,
            "width": 45.0,
            "clearway1_len": 200.0,
            "clearway2_len": 0.0,
            "calculated_strip_dims": dict(runway.strip_parameters),
        }
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        captured = []

        def capture_layer(self, _geometry_type, layer_id, _layer_name, _fields, features, _group, _style):
            captured.append((layer_id, list(features)))
            return object()

        builder._create_and_add_layer = MethodType(capture_layer, builder)
        builder._generate_transitional_features = MethodType(
            lambda self, _runways, _elevation, _crs: ([], []), builder
        )
        group = QgsLayerTreeGroup("EASA OLS")
        self.assertTrue(
            builder._generate_airport_wide_ols(
                [runway_data], group, context.reference_elevation_datum_m, "TEST"
            )
        )

        generated = {
            feature.attribute("surface"): feature
            for _layer_id, features in captured
            for feature in features
            if feature.fields().indexFromName("surface") != -1
            and feature.attribute("surface") in {"IHS", "Conical", "OHS"}
        }
        self.assertTrue({"IHS", "Conical", "OHS"}.issubset(generated))
        self.assertTrue(all(feature.geometry().isGeosValid() for feature in generated.values()))
        self.assertTrue(str(generated["IHS"].attribute("ref_mos")).startswith("CS ADR-DSN.J."))
        self.assertTrue(str(generated["Conical"].attribute("ref_mos")).startswith("CS ADR-DSN.J."))
        self.assertEqual(generated["OHS"].attribute("ref_mos"), "GM1 ADR-DSN.H.410")
        self.assertEqual(generated["OHS"].attribute("applicability"), "guidance_only")

        cat23_ofz = EASA_PROFILE.ols_parameters(3, "PA_II_III", "BalkedLanding")
        bls_result = builder._generate_baulked_landing_surface(
            runway_data,
            builder._get_runway_parameters(runway.primary_threshold_point, runway.reciprocal_threshold_point),
            runway.primary_threshold_point,
            builder._get_runway_parameters(runway.primary_threshold_point, runway.reciprocal_threshold_point)[
                "azimuth_p_r"
            ],
            {**cat23_ofz, "applicability": "required"},
            "09",
            168.0,
            strip_end_distance_from_thr=3060.0,
        )
        self.assertIsNotNone(bls_result)
        self.assertTrue(bls_result[0].geometry().isGeosValid())
        self.assertTrue(str(bls_result[0].attribute("ref_mos")).startswith("CS ADR-DSN.J."))
        self.assertEqual(bls_result[0].attribute("applicability"), "required")

    def test_annex14_elevation_fallback_preserves_zero_threshold(self):
        builder = object.__new__(SafeguardingBuilder)

        elevations = builder._annex14_runway_end_elevations(
            {
                "threshold_elev_1": 0.0,
                "runway_end_elev_1": 9.0,
                "threshold_elev_2": "",
                "runway_end_elev_2": 5.0,
            }
        )

        self.assertEqual(elevations, (0.0, 5.0))

    def test_easa_controlling_candidate_provenance_is_flattened_for_output(self):
        builder = object.__new__(SafeguardingBuilder)
        builder.get_active_protected_airspace_ruleset = lambda: EASA_PROFILE
        candidate = ControllingOlsCandidate(
            surface_id="APP:09:09:S1",
            surface_type="Approach",
            footprint=QgsGeometry.fromRect(QgsRectangle(0.0, 0.0, 10.0, 10.0)),
            elevation_at_xy=lambda _point: 100.0,
            model="axis",
        )

        provenance = builder._controlling_candidate_provenance(candidate)

        self.assertIn("CS ADR-DSN.J.", provenance["source_ref"])
        self.assertEqual(provenance["source_status"], "operational_verified")
        self.assertIn("Issue 6 - Chapter H & J", provenance["source_extract"])
        self.assertEqual(len(provenance["source_hash"]), 64)

    def test_conventional_partition_is_exclusive_without_annex_optional_fields(self):
        fields = QgsFields(
            [
                QgsField("region_id", QVariant.Int),
                QgsField("surface_id", QVariant.String),
                QgsField("surface", QVariant.String),
            ]
        )

        def feature(surface_id, xmin, xmax):
            item = QgsFeature(fields)
            item.setAttributes([0, surface_id, "Approach"])
            item.setGeometry(
                QgsGeometry.fromRect(QgsRectangle(xmin, 0.0, xmax, 10.0))
            )
            return item

        builder = object.__new__(SafeguardingBuilder)
        partitioned = builder._partition_controlling_region_features(
            [feature("B", 5.0, 15.0), feature("A", 0.0, 10.0)]
        )
        self.assertEqual(len(partitioned), 2)
        self.assertLessEqual(
            partitioned[0].geometry().intersection(partitioned[1].geometry()).area(),
            1e-9,
        )
        self.assertAlmostEqual(
            QgsGeometry.unaryUnion([item.geometry() for item in partitioned]).area(),
            150.0,
            places=9,
        )

    def test_curved_track_builds_valid_variable_width_panels(self):
        harness = TrackHarness(cap_context("LINESTRING (0 0, -500 0, -1000 150, -1500 500)"))
        track, requested = harness._ols_nominated_track(
            {"original_index": 1}, "primary", "approach", QgsPointXY(0.0, 0.0), 1500.0
        )

        self.assertTrue(requested)
        self.assertIsNotNone(track)
        panels = harness._ols_track_corridor_parts(track, 60.0, 1200.0, 280.0, 640.0)
        self.assertGreater(len(panels), 5)
        union = QgsGeometry.unaryUnion([panel[0] for panel in panels])
        self.assertFalse(union.isEmpty())
        self.assertTrue(union.isGeosValid())
        self.assertGreater(union.area(), 280.0 * 1000.0)
        cross_section = harness._ols_track_cross_section(track, 600.0, 400.0)
        self.assertAlmostEqual(cross_section.length(), 400.0, delta=0.01)

    def test_curved_approach_transitional_is_triangulated_and_contours_match_planes(self):
        harness = CandidateTrackHarness(
            cap_context("LINESTRING (0 0, -500 0, -1000 150, -1500 500)")
        )
        track, requested = harness._ols_nominated_track(
            {"original_index": 1},
            "primary",
            "approach",
            QgsPointXY(0.0, 0.0),
            1500.0,
        )
        self.assertTrue(requested)
        self.assertIsNotNone(track)
        edge_parts = harness._ols_track_corridor_edge_parts(
            track,
            60.0,
            1000.0,
            280.0,
            580.0,
            max_segment_m=200.0,
        )["L"]
        transitional_fields = QgsFields(
            [
                QgsField("rwy_name", QVariant.String),
                QgsField("surface", QVariant.String),
                QgsField("end_desig", QVariant.String),
                QgsField("section_desc", QVariant.String),
                QgsField("elev_m", QVariant.Double),
                QgsField("height_agl", QVariant.Double),
                QgsField("side", QVariant.String),
                QgsField("slope_perc", QVariant.Double),
                QgsField("ref_mos", QVariant.String),
            ]
        )
        contour_fields = harness._get_transitional_contour_fields()
        features, contours, sequence = harness._generate_nominated_track_transitional_triangles(
            edge_parts,
            100.0,
            0.025,
            145.0,
            0.143,
            transitional_fields,
            contour_fields,
            5.0,
            "09/27",
            "09",
            "L",
            1,
            "CAP 168 4.34-4.39",
            0,
        )

        self.assertGreater(len(features), len(edge_parts))
        self.assertEqual(sequence, len(features))
        self.assertEqual(len(harness.candidates), len(features))
        self.assertTrue(all(feature.geometry().isGeosValid() for feature in features))
        self.assertTrue(
            all(candidate.metadata.get("track_type") == "nominated" for candidate in harness.candidates)
        )
        candidates = {candidate.surface_id: candidate for candidate in harness.candidates}
        self.assertGreater(len(contours), 0)
        for contour in contours:
            surface_id = str(contour.attribute("surface_id") or "")
            candidate = candidates[surface_id]
            elevation = float(contour.attribute("contour_elev_am"))
            self.assertLessEqual(
                contour.geometry().difference(candidate.footprint).length(),
                1e-6,
            )
            for point in contour.geometry().asPolyline():
                self.assertAlmostEqual(
                    candidate.elevation_at_xy(QgsPointXY(point)),
                    elevation,
                    delta=0.001,
                )

    def test_track_with_wrong_origin_is_blocked_instead_of_falling_back_to_aligned(self):
        harness = TrackHarness(cap_context("LINESTRING (100 100, -1000 100)"))
        track, requested = harness._ols_nominated_track(
            {"original_index": 1}, "primary", "approach", QgsPointXY(0.0, 0.0), 500.0
        )
        self.assertTrue(requested)
        self.assertIsNone(track)

    def test_builder_rebuilds_contexts_with_one_shared_design_strip(self):
        builder = object.__new__(SafeguardingBuilder)
        builder.translator = None
        builder.ruleset = MOS139_PROFILE
        builder.reference_elevation_datum = 130.0
        builder.arp_elevation_amsl = 120.0
        source = {
            "original_index": 1,
            "short_name": "09/27",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(2000.0, 0.0),
            "thr_displaced_1": 0.0,
            "thr_displaced_2": 0.0,
            "threshold_elev_1": 100.0,
            "threshold_elev_2": 105.0,
            "runway_end_elev_1": 100.0,
            "runway_end_elev_2": 105.0,
            "width": 45.0,
            "arc_num": 3,
            "arc_let": "C",
            "type1": "Precision Approach CAT I",
            "type2": "Non-Precision Approach (NPA)",
            "clearway1_len": 200.0,
            "clearway2_len": 100.0,
            "stopway1_len": 50.0,
            "stopway2_len": 25.0,
        }

        cap = builder._build_ols_construction_context(
            CAP168_PROFILE, [source], arp_point=QgsPointXY(1000.0, 500.0)
        )
        easa = builder._build_ols_construction_context(
            EASA_PROFILE, [source], arp_point=QgsPointXY(1000.0, 500.0)
        )
        annex_current = builder._build_ols_construction_context(
            ANNEX14_CURRENT_OLS_PROFILE,
            [source],
            arp_point=QgsPointXY(1000.0, 500.0),
        )
        annex_modernised = builder._build_ols_construction_context(
            ANNEX14_MODERNISED_OFS_OES_PROFILE,
            [source],
            arp_point=QgsPointXY(1000.0, 500.0),
        )

        self.assertEqual(cap.ruleset_id, CAP168_PROFILE.id)
        self.assertEqual(easa.ruleset_id, EASA_PROFILE.id)
        self.assertEqual(annex_current.ruleset_id, ANNEX14_CURRENT_OLS_PROFILE.id)
        self.assertEqual(
            annex_modernised.ruleset_id,
            ANNEX14_MODERNISED_OFS_OES_PROFILE.id,
        )
        self.assertEqual(cap.lowest_threshold_elevation_m, 100.0)
        self.assertEqual(cap.reference_elevation_datum_m, 130.0)
        self.assertIsNot(cap.runways[0].generation_data, easa.runways[0].generation_data)
        self.assertIsNot(
            cap.runways[0].generation_data,
            annex_current.runways[0].generation_data,
        )
        self.assertEqual(source["clearway1_len"], 200.0)
        shared_strips = [
            context.runways[0].strip_parameters
            for context in (cap, easa, annex_current, annex_modernised)
        ]
        self.assertTrue(
            all(strip["overall_width"] == 280.0 for strip in shared_strips)
        )
        self.assertTrue(
            all(
                strip["design_ruleset_id"] == MOS139_PROFILE.id
                for strip in shared_strips
            )
        )
        self.assertEqual(
            {
                strip.get("overall_width_ref")
                for strip in shared_strips
            },
            {shared_strips[0].get("overall_width_ref")},
        )
        for context in (cap, easa, annex_current, annex_modernised):
            self.assertEqual(
                context.options,
                {
                    "strip_input_policy": "shared_design_ruleset",
                    "design_ruleset_id": MOS139_PROFILE.id,
                    "design_ruleset_label": MOS139_PROFILE.display_name,
                },
            )
        self.assertEqual(
            sorted(end.clearway_length_m for end in annex_current.runways[0].ends),
            [100.0, 200.0],
        )
        self.assertEqual(
            annex_modernised.runways[0].generation_data[
                "_effective_clearway_specs"
            ]["ruleset_id"],
            ANNEX14_MODERNISED_OFS_OES_PROFILE.id,
        )
        self.assertEqual(
            sorted(end.clearway_length_m for end in annex_modernised.runways[0].ends),
            [100.0, 200.0],
        )

        blank_clearway_source = {
            **source,
            "clearway1_len": "",
            "clearway2_len": "",
        }
        mos = builder._build_ols_construction_context(
            MOS139_PROFILE,
            [blank_clearway_source],
            arp_point=QgsPointXY(1000.0, 500.0),
        )
        self.assertEqual(mos.runways[0].generation_data["clearway1_len"], "")
        self.assertGreater(mos.runways[0].ends[0].clearway_length_m, 0.0)

    def test_modernised_comparison_does_not_substitute_annex14_ni_strip(self):
        builder = object.__new__(SafeguardingBuilder)
        builder.translator = None
        builder.ruleset = MOS139_PROFILE
        builder.reference_elevation_datum = 100.0
        builder.arp_elevation_amsl = 100.0
        source = {
            "original_index": 1,
            "short_name": "09/27",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(1500.0, 0.0),
            "thr_displaced_1": 0.0,
            "thr_displaced_2": 0.0,
            "threshold_elev_1": 100.0,
            "threshold_elev_2": 100.0,
            "runway_end_elev_1": 100.0,
            "runway_end_elev_2": 100.0,
            "width": 30.0,
            "arc_num": 3,
            "arc_let": "C",
            "type1": "Non-Instrument (NI)",
            "type2": "Non-Instrument (NI)",
            "clearway1_len": 0.0,
            "clearway2_len": 0.0,
            "stopway1_len": 0.0,
            "stopway2_len": 0.0,
            "annex14_modernised": {"strip": {}},
        }

        builder._apply_shared_design_strips([source])
        baseline = builder._build_ols_construction_context(
            MOS139_PROFILE,
            [source],
            arp_point=QgsPointXY(750.0, 200.0),
        )
        future = builder._build_ols_construction_context(
            ANNEX14_MODERNISED_OFS_OES_PROFILE,
            [source],
            arp_point=QgsPointXY(750.0, 200.0),
        )

        self.assertEqual(baseline.runways[0].strip_parameters["overall_width"], 90.0)
        self.assertEqual(future.runways[0].strip_parameters["overall_width"], 90.0)
        self.assertEqual(
            source["annex14_modernised"]["strip"]["overall_width_m"],
            90.0,
        )
        self.assertEqual(
            source["annex14_modernised"]["strip"]["design_ruleset_id"],
            MOS139_PROFILE.id,
        )


if __name__ == "__main__":
    unittest.main()
