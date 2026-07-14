"""QGIS geometry checks for ruleset-owned nominated OLS tracks."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
)

from guidelines.ols_guideline import OlsGuidelineMixin
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

    def test_builder_rebuilds_cap_and_easa_contexts_without_cross_ruleset_state(self):
        builder = object.__new__(SafeguardingBuilder)
        builder.translator = None
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

        self.assertEqual(cap.ruleset_id, CAP168_PROFILE.id)
        self.assertEqual(easa.ruleset_id, EASA_PROFILE.id)
        self.assertEqual(cap.lowest_threshold_elevation_m, 100.0)
        self.assertEqual(cap.reference_elevation_datum_m, 130.0)
        self.assertIsNot(cap.runways[0].generation_data, easa.runways[0].generation_data)
        self.assertEqual(source["clearway1_len"], 200.0)
        self.assertNotEqual(
            cap.runways[0].strip_parameters.get("overall_width_ref"),
            easa.runways[0].strip_parameters.get("overall_width_ref"),
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


if __name__ == "__main__":
    unittest.main()
