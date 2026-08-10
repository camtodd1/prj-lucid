"""QGIS smoke test for source-backed EASA visual-aid generation."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

from qgis.core import QgsCoordinateReferenceSystem, QgsPointXY, QgsProject

from rulesets.easa.profile import EASA_PROFILE
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder


class EasaVisualAidsQgisTests(unittest.TestCase):
    def test_easa_agl_generation_uses_source_backed_rules(self):
        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))

        builder = object.__new__(SafeguardingBuilder)
        builder.ruleset = EASA_PROFILE
        builder.output_mode = "memory"
        builder.translator = None
        builder._run_log = None
        builder.tr = lambda value: value

        runway = {
            "short_name": "09/27",
            "original_index": 1,
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(2000.0, 0.0),
            "width": 45.0,
            "arc_num": 3,
            "type1": "Precision Approach CAT I",
            "type2": "Precision Approach CAT I",
            "thr_displaced_1": 0.0,
            "thr_displaced_2": 0.0,
            "stopway1_len": 50.0,
            "stopway2_len": 25.0,
        }
        options = {
            ("__options__", "runway_end_lights"): True,
            ("__options__", "threshold_wing_bars"): True,
            ("__options__", "stopway_lights"): True,
            ("__options__", "centreline_lights"): True,
            ("__options__", "centreline_low_visibility"): True,
            ("__options__", "cat_i_tdz_lights"): True,
            (1, "primary"): {"length_m": 900.0, "spacing_m": 30.0},
            (1, "reciprocal"): {"length_m": 900.0, "spacing_m": 30.0},
        }
        captured = {"features": []}
        builder._create_and_add_layer = (
            lambda *args, **kwargs: captured["features"].extend(args[4]) or True
        )

        self.assertTrue(
            builder._create_agl_layer_for_runway(
                runway,
                [runway],
                None,
                threshold_inset_m=0.0,
                centreline_offset_m=0.0,
                default_approach_spacing_m=30.0,
                approach_rows=options,
            )
        )

        features = captured["features"]
        self.assertGreater(len(features), 0)
        refs = {str(feature.attribute("ref_mos")) for feature in features}
        self.assertIn("CS ADR-DSN.M.705", refs)
        self.assertTrue(any(ref.startswith("CS ADR-DSN.M.630") for ref in refs), refs)
        self.assertTrue(any(ref.startswith("CS ADR-DSN.M.675") for ref in refs), refs)
        self.assertTrue(all("Part 139 MOS" not in ref for ref in refs))


if __name__ == "__main__":
    unittest.main()
