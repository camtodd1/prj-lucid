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
            "type1": "Precision Approach CAT II/III",
            "type2": "Precision Approach CAT II/III",
            "thr_displaced_1": 100.0,
            "thr_displaced_2": 0.0,
            "stopway1_len": 100.0,
            "stopway2_len": 100.0,
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
            )
        )

        features = captured["features"]
        self.assertGreater(len(features), 0)
        refs = {str(feature.attribute("ref_mos")) for feature in features}
        light_types = {str(feature.attribute("light_type")) for feature in features}
        self.assertIn("CS ADR-DSN.M.705", refs)
        self.assertTrue(any(ref.startswith("CS ADR-DSN.M.635") for ref in refs), refs)
        self.assertTrue(any(ref.startswith("CS ADR-DSN.M.675") for ref in refs), refs)
        self.assertTrue(all("Part 139 MOS" not in ref for ref in refs))
        self.assertTrue(
            {
                "Runway End",
                "Threshold Wing Bar",
                "RTIL",
                "Stopway Edge",
                "Stopway End",
                "Runway Centreline",
                "TDZ Barrette",
            }
            <= light_types,
            light_types,
        )
        self.assertNotIn("Temporary Displaced Threshold", light_types)


if __name__ == "__main__":
    unittest.main()
