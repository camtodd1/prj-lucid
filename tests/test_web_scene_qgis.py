"""Run with QGIS Python: python -m unittest tests.test_web_scene_qgis."""
import math
import unittest
from types import SimpleNamespace
from qgis.core import QgsApplication, QgsGeometry
from core.web_scene import candidate_mesh

APP = QgsApplication([], False)
APP.initQgis()


class SceneTests(unittest.TestCase):
    def test_planar_elevations_and_hole(self):
        footprint = QgsGeometry.fromWkt('Polygon ((1000 2000,1100 2000,1100 2100,1000 2100,1000 2000),(1020 2020,1020 2040,1040 2040,1040 2020,1020 2020))')
        candidate = SimpleNamespace(footprint=footprint, model='plane', surface_id='plane', elevation_at_xy=lambda p: 50 + .1*(p.x()-1000))
        values = candidate_mesh(candidate, (1000,2000))
        area = 0
        for i in range(0,len(values),9):
            a,b,c=[values[j:j+3] for j in (i,i+3,i+6)]
            area += abs((b[0]-a[0])*(c[2]-a[2])-(c[0]-a[0])*(b[2]-a[2]))/2
            for x,z,y in (a,b,c):
                self.assertAlmostEqual(z,50+.1*x)
        self.assertAlmostEqual(area,9600,places=2)

    def test_curved_surface_has_interior_heights(self):
        candidate=SimpleNamespace(footprint=QgsGeometry.fromWkt('Polygon ((0 0,100 0,100 100,0 100,0 0))'),model='conical',surface_id='curve',elevation_at_xy=lambda p: 50+.05*math.hypot(p.x(),p.y()))
        values=candidate_mesh(candidate,(0,0),spacing=25)
        self.assertGreater(len(values),18)
        for i in range(0,len(values),3):
            x,z,y=values[i:i+3]
            self.assertAlmostEqual(z,50+.05*math.hypot(x,y),places=5)

    def test_missing_height_rejected(self):
        candidate=SimpleNamespace(footprint=QgsGeometry.fromWkt('Polygon ((0 0,10 0,0 10,0 0))'),model='plane',surface_id='missing',elevation_at_xy=lambda p: None)
        with self.assertRaisesRegex(ValueError,'missing elevation'):
            candidate_mesh(candidate,(0,0))

    def test_export_is_offline_escaped_and_never_overwrites(self):
        import tempfile
        from pathlib import Path
        from qgis.core import QgsCoordinateReferenceSystem
        from core.web_scene import export_scene
        candidate=SimpleNamespace(footprint=QgsGeometry.fromWkt('Polygon ((0 0,10 0,0 10,0 0))'),model='plane',surface_id='test',surface_type='Approach',metadata={},elevation_at_xy=lambda p: 100)
        engines={'OLS':SimpleNamespace(candidates=[candidate])}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.html'
            export_scene(engines,QgsCoordinateReferenceSystem('EPSG:32631'),str(path),'</script><script>bad</script>')
            html=path.read_text()
            self.assertNotIn('<script>bad</script>',html)
            self.assertNotIn('<script src=',html)
            self.assertNotIn('/*SCENE*/',html)
            self.assertIn('Permission is hereby granted',html)
            with self.assertRaises(FileExistsError):
                export_scene(engines,QgsCoordinateReferenceSystem('EPSG:32631'),str(path))
            with self.assertRaisesRegex(ValueError,'metres'):
                export_scene(engines,QgsCoordinateReferenceSystem('EPSG:4326'),str(path))

    def test_terrain_nodata_is_not_filled(self):
        from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle
        from core.web_scene import terrain_mesh
        crs=QgsCoordinateReferenceSystem('EPSG:32631')
        provider=SimpleNamespace(sample=lambda point,band: (12, point.x()>0))
        dem=SimpleNamespace(crs=lambda:crs,dataProvider=lambda:provider)
        values=terrain_mesh(dem,crs,QgsRectangle(0,0,20,20),(0,0),resolution=2)
        self.assertTrue(values)
        self.assertTrue(all(values[i]>0 for i in range(0,len(values),3)))
        self.assertTrue(all(values[i]==12 for i in range(1,len(values),3)))

    def test_rotated_bounded_approach_preserves_boundary_coordinates(self):
        # Tessellator float32 coordinates must not move endpoints outside the
        # evaluator's micrometre boundary tolerance.
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from safeguarding_builder.guidelines.controlling_ols_engine import axis_elevation_evaluator
        from qgis.core import QgsPointXY
        start = QgsPointXY(432123.123456, 5812345.654321)
        angle = math.radians(17.3)
        ux, uy = math.sin(angle), math.cos(angle)
        points = [QgsPointXY(start.x()+ux*d+uy*w, start.y()+uy*d-ux*w)
                  for d,w in ((0,-150),(3000,-600),(3000,600),(0,150),(0,-150))]
        candidate = SimpleNamespace(footprint=QgsGeometry.fromPolygonXY([points]),
                                    model='axis',surface_id='APP:17:S1',
                                    elevation_at_xy=axis_elevation_evaluator(start,17.3,80,.02,3000))
        values = candidate_mesh(candidate,(430000,5810000))
        self.assertEqual(len(values),18)
        self.assertAlmostEqual(min(values[1::3]),80,places=6)
        self.assertAlmostEqual(max(values[1::3]),140,places=6)
