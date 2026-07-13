import tempfile
import unittest
from pathlib import Path

from metrodef3d.errors import RecipeError
from metrodef3d.recipe import load_recipe


class RecipeTests(unittest.TestCase):
    def test_example_recipe_loads(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        self.assertEqual(recipe.data["defect"]["type"], "crack")

    def test_blender_recipe_loads(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        self.assertEqual(recipe.data["render"]["backend"], "blender")
        self.assertEqual(recipe.data["render"]["image_format"], "jpg")
        self.assertEqual(recipe.data["surface"]["width"], 250.0)
        self.assertEqual(recipe.data["render"]["block_depth"], 1000.0)
        self.assertEqual(recipe.data["render"]["world_color"], [0.0, 0.0, 0.0])
        self.assertEqual(recipe.data["defect"]["construction_model"], "ribbon_fbm_width")
        self.assertEqual(recipe.data["defect"]["path_control_step"], 1.9)
        self.assertEqual(recipe.data["defect"]["path_jaggedness"]["micro_min_interval"], 0.04)
        self.assertEqual(recipe.data["defect"]["path_jaggedness"]["micro_degrees"], 18.0)
        self.assertEqual(recipe.data["defect"]["path_jaggedness"]["minor_degrees"], 12.0)
        self.assertEqual(recipe.data["defect"]["path_jaggedness"]["major_min_interval"], 45.0)
        self.assertEqual(recipe.data["defect"]["path_jaggedness"]["major_degrees"], 20.0)
        self.assertEqual(recipe.data["defect"]["width_variation"]["field_amplitude"], 1.8)
        self.assertEqual(recipe.data["defect"]["width_variation"]["secondary_field_amplitude"], 0.55)
        self.assertEqual(recipe.data["defect"]["width_variation"]["edge_jitter_field_amplitude"], 0.38)
        self.assertEqual(recipe.data["material"]["concrete_texture"]["noise_dimensions"], "4D")
        self.assertEqual(recipe.data["material"]["concrete_texture"]["noise_scale"], 2.8)
        self.assertEqual(recipe.data["material"]["concrete_texture"]["pitting_coarse_depth"], -10.0)
        self.assertEqual(recipe.data["material"]["concrete_texture"]["pitting_fine_depth"], -5.0)
        self.assertTrue(recipe.data["material"]["concrete_texture"]["pitting_variation"]["enabled"])
        self.assertEqual(
            [choice["id"] for choice in recipe.data["material"]["concrete_texture"]["pitting_variation"]["choices"]],
            ["none", "subtle", "moderate", "strong"],
        )
        self.assertTrue(recipe.data["material"]["concrete_texture"]["surface_roughness_variation"]["enabled"])
        self.assertEqual(
            [
                choice["id"]
                for choice in recipe.data["material"]["concrete_texture"]["surface_roughness_variation"]["choices"]
            ],
            ["polished", "honed", "light_texture", "cast_texture", "rough_cast"],
        )
        self.assertTrue(recipe.data["material"]["concrete_texture"]["aggregate_variation"]["enabled"])
        self.assertEqual(
            [choice["id"] for choice in recipe.data["material"]["concrete_texture"]["aggregate_variation"]["choices"]],
            ["none", "sparse", "moderate"],
        )
        self.assertEqual(recipe.data["render"]["render_detail"]["crack_edge_falloff"]["max_width_fraction"], 0.2)
        self.assertEqual(recipe.data["render"]["render_detail"]["crack_debris"]["probability"], 0.95)
        self.assertEqual(recipe.data["captures"][0]["camera"]["type"], "orthographic")
        self.assertEqual(recipe.data["captures"][0]["camera"]["orthographic_scale"], 150.0)
        self.assertEqual(recipe.data["captures"][0]["lighting"]["type"], "preset_random")

    def test_simple_blender_recipe_loads(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_simple.yaml"))
        self.assertEqual(recipe.data["run"]["id"], "cracked-plane-blender-simple")
        self.assertEqual(recipe.data["render"]["backend"], "blender")
        self.assertEqual(recipe.data["render"]["image_format"], "jpg")
        self.assertEqual(recipe.data["defect"]["construction_model"], "ribbon_fbm_width")
        self.assertEqual(recipe.data["defect"]["width_variation"]["min_multiplier"], 0.75)
        self.assertEqual(recipe.data["defect"]["width_variation"]["max_multiplier"], 1.35)
        self.assertEqual(recipe.data["defect"]["width_variation"]["field_amplitude"], 0.55)
        self.assertEqual(recipe.data["defect"]["width_variation"]["secondary_field_amplitude"], 0.16)
        self.assertEqual(recipe.data["defect"]["width_variation"]["edge_jitter_field_amplitude"], 0.1)
        self.assertFalse(recipe.data["render"]["render_detail"]["crack_edge_falloff"]["enabled"])
        self.assertFalse(recipe.data["render"]["render_detail"]["crack_debris"]["enabled"])
        self.assertEqual(len(recipe.data["captures"]), 1)
        self.assertEqual(recipe.data["captures"][0]["id"], "perspective-area")
        self.assertEqual(recipe.data["captures"][0]["camera"]["type"], "perspective")
        self.assertNotIn("render_variants", recipe.data["captures"][0])

    def test_split_blender_recipe_loads(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_split.yaml"))
        self.assertEqual(recipe.data["render"]["backend"], "blender")
        self.assertEqual(recipe.data["defect"]["construction_model"], "split_displacement")
        self.assertEqual(recipe.data["defect"]["opening_model"]["max_opening_min"], 0.3)
        self.assertEqual(recipe.data["defect"]["opening_model"]["max_opening_max"], 3.0)
        self.assertEqual(recipe.data["render"]["render_detail"]["crack_edge_falloff"]["max_width_fraction"], 0.2)

    def test_invalid_recipe_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("run:\n  id: bad\n", encoding="utf-8")
            with self.assertRaisesRegex(RecipeError, "Missing required recipe key: surface"):
                load_recipe(path)


if __name__ == "__main__":
    unittest.main()
