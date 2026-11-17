"""Regression checks for component-aware preview references and schema version."""
import math
import unittest
from metrodef3d import VISIBLE_DEFECT_SCHEMA_VERSION
from metrodef3d.geometry import visible_defect_for_capture
from metrodef3d.render import BLENDER_SCRIPT_TEMPLATE

class ComponentReferenceTests(unittest.TestCase):
    def camera(self):
        return dict(type="perspective",position=[0,0,500],target=[0,0,0],resolution=[1024,1024],fov_degrees=math.degrees(2*math.atan(.1)),fov_mm=100)

    def defect(self,points):
        return dict(centerline=points,width_profile=[2.]*len(points),depth_profile=[1.]*len(points))

    def test_disconnected_preview_has_no_length_or_area_bridge(self):
        d=visible_defect_for_capture(self.defect([[-40,0,0],[0,70,0],[40,0,0]]),self.camera())
        length=2*math.hypot(40,70)*50/70
        self.assertEqual(len(d["component_ranges"]),2)
        self.assertAlmostEqual(d["measurands"]["centerline_length"],length,places=5)
        self.assertAlmostEqual(d["measurands"]["crack_area"],2*length,places=5)
        self.assertEqual(d["measurands"]["mean_width"],2.)
        self.assertEqual(d["schema"]["version"],2)

    def test_contiguous_preview_remains_one_component(self):
        d=visible_defect_for_capture(self.defect([[-40,0,0],[0,0,0],[40,0,0]]),self.camera())
        self.assertEqual(d["component_ranges"],[[0,3]])
        self.assertEqual(d["measurands"]["centerline_length"],80.)

    def test_empty_preview_zero_is_defined(self):
        d=visible_defect_for_capture(self.defect([[-40,70,0],[40,70,0]]),self.camera())
        self.assertFalse(d["visible"])
        self.assertEqual(d["component_ranges"],[])
        self.assertEqual(d["measurands"]["mean_width"],0.)
        self.assertTrue(d["measurand_validity"]["mean_width"])

if __name__=="__main__":unittest.main()
