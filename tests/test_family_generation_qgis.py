import json
import sys
import unittest
from pathlib import Path

from qgis.PyQt import QtWidgets
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE.parent))

from safeguarding_builder.core.family_modules import (
    FAMILY_AIRPORT,
    FAMILY_CNS,
    FAMILY_EXTERNAL,
    FAMILY_LIGHTING,
    FAMILY_RUNWAYS,
)
from safeguarding_builder.core import output_structure
from safeguarding_builder.frameworks.registry import get_framework_profile
from safeguarding_builder.safeguarding_builder import SafeguardingBuilder
from safeguarding_builder.safeguarding_builder_dialog import SafeguardingBuilderDialog
from safeguarding_builder.rulesets.easa.profile import EASA_PROFILE


class FamilyGenerationCommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

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
        stage_agl = stage.addGroup(output_structure.AIRFIELD_GROUND_LIGHTING)
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
        committed_agl = main.findGroup(output_structure.AIRFIELD_GROUND_LIGHTING)
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

    def test_family_run_migrates_legacy_reference_group_name(self):
        root = QgsProject.instance().layerTreeRoot()
        main = root.addGroup("YBAS Safeguarding Builder")
        legacy = main.addGroup(output_structure.LEGACY_REFERENCE_DATA)
        legacy_layer = self.layer("YBAS ARP")
        legacy.addLayer(legacy_layer)
        legacy_infrastructure = main.addGroup(
            output_structure.LEGACY_AERODROME_INFRASTRUCTURE
        )
        legacy_agl = legacy_infrastructure.addGroup("Airfield Ground Lighting")
        agl_layer = self.layer("YBAS AGL")
        legacy_agl.addLayer(agl_layer)
        main.addGroup(output_structure.LEGACY_RUNWAY_PROTECTION)
        main.addGroup(output_structure.LEGACY_CNS_TECHNICAL_SAFEGUARDING)
        main.addGroup(output_structure.LEGACY_EXTERNAL_SAFEGUARDING)

        resolved = self.builder._family_main_group(root, "YBAS")

        self.assertIs(resolved, main)
        self.assertIsNone(main.findGroup(output_structure.LEGACY_REFERENCE_DATA))
        renamed = main.findGroup(output_structure.REFERENCE_DATA)
        self.assertIsNotNone(renamed)
        self.assertIsNotNone(renamed.findLayer(legacy_layer.id()))
        for legacy_name in (
            output_structure.LEGACY_AERODROME_INFRASTRUCTURE,
            output_structure.LEGACY_RUNWAY_PROTECTION,
            output_structure.LEGACY_CNS_TECHNICAL_SAFEGUARDING,
            output_structure.LEGACY_EXTERNAL_SAFEGUARDING,
        ):
            self.assertIsNone(main.findGroup(legacy_name))
        self.assertIsNotNone(main.findGroup(output_structure.AERODROME_INFRASTRUCTURE))
        self.assertIsNotNone(main.findGroup(output_structure.RUNWAY_PROTECTION_AND_SEPARATION))
        self.assertIsNotNone(main.findGroup(output_structure.CNS_TECHNICAL_SAFEGUARDING))
        self.assertIsNotNone(main.findGroup(output_structure.EXTERNAL_SAFEGUARDING))
        promoted_agl = main.findGroup(output_structure.AIRFIELD_GROUND_LIGHTING)
        self.assertIsNotNone(promoted_agl.findLayer(agl_layer.id()))

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
        self.builder.icao_code = "YBAS"
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
            "centreline_low_visibility": True,
            "cat_i_centreline_lights": True,
            "cat_i_tdz_lights": True,
        }

        first_stage = root.addGroup("first-stage")
        self.assertTrue(
            self.builder._run_lighting_family(
                first_stage,
                {"runways": [runway], "agl_options": options},
            )
        )
        staged_agl = first_stage.findGroup(output_structure.AIRFIELD_GROUND_LIGHTING)
        runway_group = staged_agl.findGroup("Runway 09/27")
        self.assertIsNotNone(runway_group)
        self.assertGreater(len(runway_group.findLayers()), 1)
        generated_light_types = {node.name() for node in runway_group.findLayers()}
        self.assertIn("Threshold Wing Bar", generated_light_types)
        self.assertNotIn("Runway Centreline", generated_light_types)
        self.assertNotIn("TDZ Barrette", generated_light_types)
        for layer_node in runway_group.findLayers():
            light_types = {
                str(feature.attribute("light_type"))
                for feature in layer_node.layer().getFeatures()
            }
            self.assertEqual(light_types, {layer_node.name()})
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

    def test_runway_family_creates_physical_geometry_from_dialog_inputs(self):
        fixture_path = WORKSPACE / "tests" / "fixtures" / "ols" / "ybas_1rwy_single.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:28353"))
        dialog = SafeguardingBuilderDialog()
        self.addCleanup(dialog.deleteLater)
        dialog._airport_lookup_timer.stop()
        dialog._apply_loaded_payload(payload)
        dialog._airport_lookup_timer.stop()
        input_data = dialog.get_all_input_data("runways")
        self.assertIsNotNone(input_data)

        self.builder.plugin_dir = str(WORKSPACE)
        self.builder._run_log = None
        self.builder.tr = lambda value: value
        self.builder.successfully_generated_layers = []
        self.builder._active_generation_module_id = FAMILY_RUNWAYS
        self.builder._active_generation_signature = "signature"
        self.builder._active_generation_run_id = "run-id"
        self.builder.output_filename_prefix = ""
        self.builder._configure_family_generation_context(input_data)
        self.assertEqual(self.builder._active_generation_module_id, FAMILY_RUNWAYS)
        stage = project.layerTreeRoot().addGroup("runway-stage")

        self.assertTrue(
            self.builder._run_runways_family(stage, input_data, project.crs())
        )
        physical = stage.findGroup(output_structure.PHYSICAL_GEOMETRY)
        self.assertIsNotNone(physical)
        self.assertIn("YBAS Runway Pavement", {node.name() for node in physical.findLayers()})
        self.assertEqual(
            stage.findGroup(output_structure.EXTERNAL_SAFEGUARDING).findLayers(),
            [],
        )
        self.assertEqual(
            {
                str(node.layer().customProperty("safeguarding_builder/module_id") or "")
                for node in physical.findLayers()
            },
            {FAMILY_RUNWAYS},
        )

        main = project.layerTreeRoot().addGroup("YBAS Safeguarding Builder")
        committed = self.builder._commit_family_stage(
            stage,
            main,
            FAMILY_RUNWAYS,
            "signature",
            "run-id",
        )
        self.assertGreater(committed, 0)
        committed_physical = main.findGroup(output_structure.PHYSICAL_GEOMETRY)
        self.assertIsNotNone(committed_physical)
        self.assertIn(
            "YBAS Runway Pavement",
            {node.name() for node in committed_physical.findLayers()},
        )

    def test_airport_family_does_not_generate_met_layers(self):
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:28353"))
        self.builder.tr = lambda value: value
        self.builder._run_log = None
        self.builder.output_mode = "memory"
        self.builder.icao_code = "YBAS"
        self.builder.ruleset = EASA_PROFILE
        self.builder.baseline_ols_ruleset = EASA_PROFILE
        self.builder.comparison_ols_ruleset = None
        self.builder.protected_airspace_ruleset = EASA_PROFILE
        self.builder.protected_airspace_policy = "ruleset_aligned"
        self.builder.framework = get_framework_profile()
        self.builder.safeguarding_options = {}
        self.builder.style_map = {}
        self.builder.successfully_generated_layers = []
        self.builder._active_generation_module_id = FAMILY_AIRPORT
        self.builder._active_generation_signature = "signature"
        self.builder._active_generation_run_id = "run-id"
        stage = project.layerTreeRoot().addGroup("airport-stage")
        arp = QgsPointXY(500000.0, 7000000.0)
        met = QgsPointXY(500100.0, 7000100.0)

        self.assertTrue(
            self.builder._run_airport_family(
                stage,
                {
                    "icao_code": "YBAS",
                    "arp_point": arp,
                    "arp_easting": arp.x(),
                    "arp_northing": arp.y(),
                    "arp_elevation": 95.0,
                    "met_point": met,
                },
                project.crs(),
            )
        )

        technical = stage.findGroup(output_structure.CNS_TECHNICAL_SAFEGUARDING)
        station = technical.findGroup(output_structure.METEOROLOGICAL_STATION)
        self.assertIsNone(station)
        self.assertEqual(
            stage.findGroup(output_structure.EXTERNAL_SAFEGUARDING).findLayers(),
            [],
        )

    def test_cns_family_routes_source_facilities_to_technical_safeguarding(self):
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:28353"))
        self.builder.tr = lambda value: value
        self.builder.icao_code = "YBAS"
        self.builder._run_log = None
        self.builder.output_mode = "memory"
        self.builder.style_map = {}
        self.builder._active_generation_module_id = FAMILY_CNS
        self.builder._active_generation_signature = "signature"
        self.builder._active_generation_run_id = "run-id"
        self.builder.framework = get_framework_profile()
        self.builder.baseline_ols_ruleset = EASA_PROFILE
        self.builder.comparison_ols_ruleset = None
        self.builder.protected_airspace_ruleset = EASA_PROFILE
        self.builder.protected_airspace_policy = "ruleset_aligned"
        self.builder.safeguarding_options = {}
        self.builder.successfully_generated_layers = []
        captured = {}
        self.builder.create_cns_source_facility_layer = (
            lambda _data, _icao, group: captured.setdefault("source_group", group)
        )
        self.builder.process_cns_building_restricted_areas = (
            lambda *_args, **_kwargs: True
        )
        stage = project.layerTreeRoot().addGroup("cns-stage")

        self.assertTrue(
            self.builder._run_cns_family(
                stage,
                {
                    "met_point": QgsPointXY(500100.0, 7000100.0),
                    "cns_facilities": [{"id": "VOR-1"}],
                    "ils_bra_installations": [],
                },
                project.crs(),
            )
        )

        source_group = captured["source_group"]
        self.assertEqual(source_group.name(), output_structure.CNS_TECHNICAL_FACILITIES)
        self.assertEqual(
            source_group.parent().name(),
            output_structure.CNS_TECHNICAL_SAFEGUARDING,
        )
        station = stage.findGroup(output_structure.METEOROLOGICAL_STATION)
        self.assertEqual(
            {node.name() for node in station.findLayers()},
            {
                "MET Station Location",
                "MET Instrument Enclosure",
                "MET Buffer Zone",
                "MET Obstacle Buffer Zone",
            },
        )
        self.assertTrue(
            all(
                node.layer().customProperty("safeguarding_builder/module_id")
                == FAMILY_CNS
                for node in station.findLayers()
            )
        )

    def test_airport_replacement_preserves_cns_owned_met_outputs(self):
        main = QgsProject.instance().layerTreeRoot().addGroup(
            "YBAS Safeguarding Builder"
        )
        technical = main.addGroup(output_structure.CNS_TECHNICAL_SAFEGUARDING)
        met_group = technical.addGroup(output_structure.METEOROLOGICAL_STATION)
        met_layer = self.layer("MET Station Location")
        met_layer.setCustomProperty(
            "safeguarding_style_key",
            "MET Station Location",
        )
        met_group.addLayer(met_layer)
        self.builder._remove_family_outputs(main, FAMILY_AIRPORT)

        self.assertIs(QgsProject.instance().mapLayer(met_layer.id()), met_layer)
        self.assertIsNotNone(technical.findGroup(output_structure.METEOROLOGICAL_STATION))

    def test_cns_replacement_removes_legacy_met_outputs(self):
        main = QgsProject.instance().layerTreeRoot().addGroup(
            "YBAS Safeguarding Builder"
        )
        technical = main.addGroup(output_structure.CNS_TECHNICAL_SAFEGUARDING)
        met_group = technical.addGroup(output_structure.METEOROLOGICAL_STATION)
        met_layer = self.layer("MET Station Location")
        met_layer_id = met_layer.id()
        met_group.addLayer(met_layer)

        self.builder._remove_family_outputs(main, FAMILY_CNS)

        self.assertIsNone(QgsProject.instance().mapLayer(met_layer_id))
        self.assertIsNone(technical.findGroup(output_structure.METEOROLOGICAL_STATION))

    def test_external_family_generates_only_external_safeguarding_layers(self):
        fixture_path = WORKSPACE / "tests" / "fixtures" / "ols" / "ybas_1rwy_single.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:28353"))
        dialog = SafeguardingBuilderDialog()
        self.addCleanup(dialog.deleteLater)
        dialog._airport_lookup_timer.stop()
        dialog._apply_loaded_payload(payload)
        dialog._airport_lookup_timer.stop()
        input_data = dialog.get_all_input_data(FAMILY_EXTERNAL)
        self.assertIsNotNone(input_data)

        self.builder.plugin_dir = str(WORKSPACE)
        self.builder._run_log = None
        self.builder.tr = lambda value: value
        self.builder.successfully_generated_layers = []
        self.builder._active_generation_module_id = FAMILY_EXTERNAL
        self.builder._active_generation_signature = "signature"
        self.builder._active_generation_run_id = "run-id"
        self.builder.output_filename_prefix = ""
        self.builder._configure_family_generation_context(input_data)
        stage = project.layerTreeRoot().addGroup("external-stage")

        self.assertTrue(
            self.builder._run_external_family(stage, input_data, project.crs())
        )
        external = stage.findGroup(output_structure.EXTERNAL_SAFEGUARDING)
        self.assertGreater(len(external.findLayers()), 0)
        self.assertTrue(
            all(
                node.layer().customProperty("safeguarding_builder/module_id")
                == FAMILY_EXTERNAL
                for node in external.findLayers()
            )
        )
        for group_name in (
            output_structure.REFERENCE_DATA,
            output_structure.AERODROME_INFRASTRUCTURE,
            output_structure.RUNWAY_PROTECTION_AND_SEPARATION,
        ):
            self.assertEqual(stage.findGroup(group_name).findLayers(), [])

    def test_generate_all_setup_preserves_terrain_and_airport_map_groups(self):
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        main = root.addGroup("YBAS Safeguarding Builder")
        terrain = main.addGroup(output_structure.TERRAIN_ANALYSIS)
        terrain_layer = self.layer("Terrain clearance")
        terrain.addLayer(terrain_layer)
        airport_map = main.addGroup(output_structure.IMPORTED_AIRPORT_MAP)
        map_layer = self.layer("Runways")
        airport_map.addLayer(map_layer)

        rebuilt = self.builder._setup_main_group(
            root,
            "YBAS Safeguarding Builder",
            project,
        )
        self.builder.framework = get_framework_profile()
        self.builder.baseline_ols_ruleset = EASA_PROFILE
        self.builder.comparison_ols_ruleset = None
        self.builder.protected_airspace_ruleset = EASA_PROFILE
        self.builder.protected_airspace_policy = "ruleset_aligned"
        self.builder._create_output_layer_groups(rebuilt, agl_enabled=True)

        self.assertEqual(
            [child.name() for child in rebuilt.children()],
            list(output_structure.SECTION_ORDER[:-1]),
        )
        self.assertIsNotNone(
            rebuilt.findGroup(output_structure.TERRAIN_ANALYSIS).findLayer(
                terrain_layer.id()
            )
        )
        self.assertIsNotNone(
            rebuilt.findGroup(output_structure.IMPORTED_AIRPORT_MAP).findLayer(
                map_layer.id()
            )
        )


if __name__ == "__main__":
    unittest.main()
