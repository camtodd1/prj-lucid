import sys
import unittest
from pathlib import Path

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.family_modules import FAMILY_LIGHTING
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder
from safeguarding_builder.rulesets.easa.profile import EASA_PROFILE


class FamilyGenerationCommitTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.builder = object.__new__(SafeguardingBuilder)
        self.builder.translator = None

    def tearDown(self):
        QgsProject.instance().clear()

    @staticmethod
    def layer(name, module_id=""):
        layer = QgsVectorLayer("Point?crs=EPSG:28355", name, "memory")
        if module_id:
            layer.setCustomProperty("safeguarding_builder/module_id", module_id)
        QgsProject.instance().addMapLayer(layer, False)
        return layer

    def test_successful_family_commit_replaces_only_owned_layers(self):
        root = QgsProject.instance().layerTreeRoot()
        main = root.addGroup("YTEST Safeguarding Builder")
        infrastructure = main.addGroup("02 Aerodrome Infrastructure")
        agl = infrastructure.addGroup("Airfield Ground Lighting")
        old_agl = self.layer("Old AGL", FAMILY_LIGHTING)
        old_agl_id = old_agl.id()
        agl.addLayer(old_agl)
        physical = infrastructure.addGroup("Physical Geometry")
        unrelated = self.layer("Runway Pavement")
        physical.addLayer(unrelated)

        stage = root.addGroup("stage")
        stage_infrastructure = stage.addGroup("02 Aerodrome Infrastructure")
        stage_agl = stage_infrastructure.addGroup("Airfield Ground Lighting")
        new_agl = self.layer("New AGL", FAMILY_LIGHTING)
        stage_agl.addLayer(new_agl)

        moved = self.builder._commit_family_stage(
            stage,
            main,
            FAMILY_LIGHTING,
            "signature",
            "run-id",
        )

        self.assertEqual(moved, 1)
        self.assertIsNone(QgsProject.instance().mapLayer(old_agl_id))
        self.assertIs(QgsProject.instance().mapLayer(unrelated.id()), unrelated)
        self.assertIs(QgsProject.instance().mapLayer(new_agl.id()), new_agl)
        committed_agl = main.findGroup("Airfield Ground Lighting")
        self.assertIsNotNone(committed_agl.findLayer(new_agl.id()))

    def test_empty_stage_keeps_previous_family_outputs(self):
        root = QgsProject.instance().layerTreeRoot()
        main = root.addGroup("YTEST Safeguarding Builder")
        infrastructure = main.addGroup("02 Aerodrome Infrastructure")
        agl = infrastructure.addGroup("Airfield Ground Lighting")
        old_agl = self.layer("Old AGL", FAMILY_LIGHTING)
        agl.addLayer(old_agl)
        stage = root.addGroup("stage")

        moved = self.builder._commit_family_stage(
            stage,
            main,
            FAMILY_LIGHTING,
            "signature",
            "run-id",
        )

        self.assertEqual(moved, 0)
        self.assertIs(QgsProject.instance().mapLayer(old_agl.id()), old_agl)

    def test_lighting_family_generates_owned_layers_and_replaces_prior_run(self):
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        root = project.layerTreeRoot()
        main = root.addGroup("YTST Safeguarding Builder")
        infrastructure = main.addGroup("02 Aerodrome Infrastructure")
        physical = infrastructure.addGroup("Physical Geometry")
        unrelated = self.layer("Runway Pavement")
        physical.addLayer(unrelated)

        self.builder.tr = lambda value: value
        self.builder._run_log = None
        self.builder.output_mode = "memory"
        self.builder.output_path = None
        self.builder.output_format_driver = None
        self.builder.output_format_extension = None
        self.builder.output_filename_prefix = ""
        self.builder.ruleset = EASA_PROFILE
        self.builder.baseline_ols_ruleset = EASA_PROFILE
        self.builder.comparison_ols_ruleset = None
        self.builder.protected_airspace_ruleset = EASA_PROFILE
        self.builder.protected_airspace_policy = "ruleset_aligned"
        self.builder.style_map = {}
        self.builder.successfully_generated_layers = []
        self.builder._active_generation_module_id = FAMILY_LIGHTING
        self.builder._active_generation_signature = "first-signature"
        self.builder._active_generation_run_id = "first-run"

        runway = {
            "original_index": 1,
            "designator_num": 9,
            "suffix": "",
            "thr_point": QgsPointXY(0.0, 0.0),
            "rec_thr_point": QgsPointXY(2000.0, 0.0),
            "width": 45.0,
            "arc_num": 3,
            "type1": "Precision Approach CAT I",
            "type2": "Precision Approach CAT I",
            "thr_displaced_1": 0.0,
            "thr_displaced_2": 0.0,
            "stopway1_len": 0.0,
            "stopway2_len": 0.0,
        }
        options = {
            "enabled": True,
            "runway_end_lights": True,
            "threshold_wing_bars": True,
            "approach_lighting": [],
        }

        first_stage = root.addGroup("first-stage")
        self.assertTrue(
            self.builder._run_lighting_family(
                first_stage,
                {"runways": [runway], "agl_options": options},
            )
        )
        first_count = self.builder._commit_family_stage(
            first_stage,
            main,
            FAMILY_LIGHTING,
            "first-signature",
            "first-run",
        )
        self.assertGreater(first_count, 0)
        first_ids = {
            node.layerId()
            for node in main.findLayers()
            if node.layer().customProperty("safeguarding_builder/module_id")
            == FAMILY_LIGHTING
        }

        self.builder.successfully_generated_layers = []
        self.builder._active_generation_signature = "second-signature"
        self.builder._active_generation_run_id = "second-run"
        second_stage = root.addGroup("second-stage")
        self.assertTrue(
            self.builder._run_lighting_family(
                second_stage,
                {"runways": [runway], "agl_options": options},
            )
        )
        second_count = self.builder._commit_family_stage(
            second_stage,
            main,
            FAMILY_LIGHTING,
            "second-signature",
            "second-run",
        )

        self.assertEqual(second_count, first_count)
        self.assertTrue(first_ids.isdisjoint(project.mapLayers()))
        self.assertIs(project.mapLayer(unrelated.id()), unrelated)
        self.assertEqual(
            main.customProperty(
                "safeguarding_builder/modules/lighting/signature"
            ),
            "second-signature",
        )


if __name__ == "__main__":
    unittest.main()
