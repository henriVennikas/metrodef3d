import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from metrodef3d import (
    METADATA_SCHEMA_VERSION,
    PIXEL_SCALE_SCHEMA_VERSION,
    RECIPE_SCHEMA_VERSION,
    VISIBLE_DEFECT_SCHEMA_VERSION,
    __version__,
)
from metrodef3d.errors import RenderError
from metrodef3d.export import build_metadata
from metrodef3d.geometry import (
    _filter_intersecting_width_whiskers,
    capture_bounds,
    construct_scene,
    visible_defect_for_capture,
)
from metrodef3d.camera import resolve_cameras
from metrodef3d.illumination import resolve_lighting
from metrodef3d.material import resolve_material
from metrodef3d.pipeline import _output_plan, _parallel_work_ranges, generate, generate_many
from metrodef3d.recipe import load_recipe
from metrodef3d.render import build_blender_script, render_image


class PipelineTests(unittest.TestCase):
    def test_generate_writes_image_and_metadata(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        with tempfile.TemporaryDirectory() as tmp:
            image_path, metadata_path = generate(recipe, Path(tmp))
            self.assertTrue(image_path.exists())
            self.assertGreater(image_path.stat().st_size, 0)
            self.assertEqual(image_path, Path(tmp) / "img" / "12345.ppm")
            self.assertEqual(metadata_path, Path(tmp) / "json" / "12345.json")
            self.assertTrue((Path(tmp) / "yaml" / "12345.yaml").exists())
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["defect"]["type"], "crack")
            self.assertEqual(metadata["schema"]["name"], "metrodef3d.metadata")
            self.assertEqual(metadata["schema"]["version"], METADATA_SCHEMA_VERSION)
            self.assertEqual(metadata["generator"]["name"], "metrodef3d")
            self.assertEqual(metadata["generator"]["version"], __version__)
            self.assertEqual(metadata["generator"]["recipe_schema_version"], RECIPE_SCHEMA_VERSION)
            self.assertEqual(metadata["generator"]["metadata_schema_version"], METADATA_SCHEMA_VERSION)
            self.assertEqual(metadata["generator"]["visible_defect_schema_version"], VISIBLE_DEFECT_SCHEMA_VERSION)
            self.assertEqual(metadata["generator"]["pixel_scale_schema_version"], PIXEL_SCALE_SCHEMA_VERSION)
            self.assertIn("git_commit", metadata["generator"])
            self.assertIn("centerline_length", metadata["defect"]["measurands"])
            self.assertEqual(metadata["outputs"]["captures"][0]["capture_id"], "default")
            self.assertEqual(metadata["outputs"]["recipe_yaml"], str(Path(tmp) / "yaml" / "12345.yaml"))
            self.assertIn("visible_defect", metadata["outputs"]["captures"][0])
            self.assertEqual(
                metadata["outputs"]["captures"][0]["visible_defect"]["schema"]["version"],
                VISIBLE_DEFECT_SCHEMA_VERSION,
            )
            self.assertLessEqual(
                metadata["outputs"]["captures"][0]["visible_defect"]["measurands"]["centerline_length"],
                metadata["defect"]["measurands"]["centerline_length"],
            )

    def test_generation_is_deterministic(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            _, left_meta = generate(recipe, Path(left))
            _, right_meta = generate(recipe, Path(right))
            left_data = json.loads(left_meta.read_text(encoding="utf-8"))
            right_data = json.loads(right_meta.read_text(encoding="utf-8"))
            self.assertEqual(left_data["seeds"], right_data["seeds"])
            self.assertEqual(left_data["defect"], right_data["defect"])
            self.assertEqual(left_data["surface"], right_data["surface"])

    def test_generate_many_writes_seed_variants(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        with tempfile.TemporaryDirectory() as tmp:
            results = generate_many(recipe, Path(tmp), count=3)
            self.assertEqual(len(results), 3)
            seeds = []
            centers = []
            for image_path, metadata_path in results:
                self.assertTrue(image_path.exists())
                self.assertTrue(metadata_path.exists())
                self.assertEqual(image_path.parent.name, "img")
                self.assertEqual(metadata_path.parent.name, "json")
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                seeds.append(metadata["run"]["seed"])
                centers.append(metadata["defect"]["center"])
            self.assertEqual(seeds, [12345, 12346, 12347])
            self.assertEqual(len({tuple(center) for center in centers}), 3)

    def test_perspective_capture_metadata_clips_visible_defect_to_camera(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        resolved = resolve_lighting(resolve_cameras(recipe.data))
        constructed = construct_scene(resolved)
        outputs = []
        for capture in resolved["captures"]:
            outputs.append(
                {
                    "capture_id": capture["id"],
                    "image_path": Path("img") / capture["id"] / "12345.jpg",
                    "camera": capture["camera"],
                    "lighting": capture["lighting"],
                }
            )
        metadata = build_metadata(
            resolved,
            recipe.path,
            constructed,
            outputs,
            Path("json/12345.json"),
            Path("yaml/12345.yaml"),
            Path("runs/test"),
        )
        captures = metadata["outputs"]["captures"]
        self.assertEqual(captures[0]["visible_defect"]["visible"], True)
        self.assertIn(captures[1]["visible_defect"]["visible"], {True, False})
        self.assertEqual(captures[1]["visible_defect"]["clip_model"], "camera_frustum")
        self.assertIsNotNone(captures[1]["visible_defect"]["measurands"]["centerline_length"])

    def test_simple_track_constructs_from_perspective_capture_bounds(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_simple.yaml"))
        resolved = resolve_lighting(resolve_cameras(recipe.data))
        constructed = construct_scene(resolved)
        bounds = capture_bounds(resolved["captures"][0]["camera"])
        center = constructed.defect["center"]
        self.assertLess(bounds["x_min"], bounds["x_max"])
        self.assertLess(bounds["y_min"], bounds["y_max"])
        self.assertGreaterEqual(center[0], bounds["x_min"] + 0.2 * (bounds["x_max"] - bounds["x_min"]))
        self.assertLessEqual(center[0], bounds["x_min"] + 0.8 * (bounds["x_max"] - bounds["x_min"]))
        visible = visible_defect_for_capture(constructed.defect, resolved["captures"][0]["camera"])
        self.assertEqual(visible["camera_type"], "perspective")
        self.assertEqual(visible["clip_model"], "camera_frustum")

    def test_metadata_prefers_render_visible_defect_sidecar(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        resolved = resolve_lighting(resolve_cameras(recipe.data))
        constructed = construct_scene(resolved)
        sidecar = {
            "visible": False,
            "clip_model": "blender_camera_view",
            "camera_type": "perspective",
            "centerline": [],
            "left_boundary": [],
            "right_boundary": [],
            "width_profile": [],
            "depth_profile": [],
            "source_profile": [],
            "measurands": {
                "centerline_length": 0.0,
                "max_width": 0.0,
                "mean_width": 0.0,
                "max_depth": 0.0,
                "crack_area": 0.0,
                "point_count": 0,
            },
        }
        metadata = build_metadata(
            resolved,
            recipe.path,
            constructed,
            [
                {
                    "capture_id": "perspective-area",
                    "image_path": Path("img/perspective-area/12345.jpg"),
                    "camera": resolved["captures"][1]["camera"],
                    "lighting": resolved["captures"][1]["lighting"],
                    "visible_defect": sidecar,
                    "visible_defect_path": Path("visible_defect/perspective-area/12345.json"),
                }
            ],
            Path("json/12345.json"),
            Path("yaml/12345.yaml"),
            Path("runs/test"),
        )
        capture = metadata["outputs"]["captures"][0]
        self.assertEqual(capture["visible_defect"], sidecar)
        self.assertEqual(capture["visible_defect_sidecar"], "visible_defect/perspective-area/12345.json")

    def test_lighting_presets_resolve_repeatably_per_seed(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        left = resolve_lighting(resolve_cameras(recipe.data))
        right = resolve_lighting(resolve_cameras(recipe.data))
        self.assertEqual(left["captures"][0]["lighting"], right["captures"][0]["lighting"])
        self.assertEqual(
            left["captures"][0]["lighting"]["preset_id"],
            left["captures"][1]["lighting"]["preset_id"],
        )
        self.assertEqual(left["captures"][0]["lighting"]["selection_mode"], "seeded_random")

    def test_material_pitting_resolves_repeatably_and_varies_by_seed(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        left = resolve_material(recipe.data)
        right = resolve_material(recipe.data)
        self.assertEqual(left["material"]["concrete_texture"], right["material"]["concrete_texture"])
        resolved = left["material"]["concrete_texture"]["pitting_variation_resolved"]
        self.assertEqual(resolved["selection_mode"], "seeded_random")
        self.assertIn(resolved["variant_id"], {"none", "subtle", "moderate", "strong"})

        variants = set()
        multipliers = set()
        for seed in range(12345, 12365):
            variant_data = dict(recipe.data)
            variant_data["run"] = dict(recipe.data["run"])
            variant_data["run"]["seed"] = seed
            texture = resolve_material(variant_data)["material"]["concrete_texture"]
            variants.add(texture["pitting_variation_resolved"]["variant_id"])
            multipliers.add(texture["pitting_variation_resolved"]["multiplier"])
        self.assertGreater(len(variants), 1)
        self.assertGreater(len(multipliers), 1)

    def test_surface_roughness_resolves_repeatably_and_scales_displacement(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        left = resolve_material(recipe.data)
        right = resolve_material(recipe.data)
        self.assertEqual(left["material"]["concrete_texture"], right["material"]["concrete_texture"])
        resolved = left["material"]["concrete_texture"]["surface_roughness_variation_resolved"]
        self.assertEqual(resolved["selection_mode"], "seeded_random")
        self.assertIn(
            resolved["variant_id"],
            {"polished", "honed", "light_texture", "cast_texture", "rough_cast"},
        )

        variants = set()
        cloudy_strengths = set()
        pitting_strengths = set()
        for seed in range(12345, 12385):
            variant_data = dict(recipe.data)
            variant_data["run"] = dict(recipe.data["run"])
            variant_data["run"]["seed"] = seed
            texture = resolve_material(variant_data)["material"]["concrete_texture"]
            roughness = texture["surface_roughness_variation_resolved"]
            variants.add(roughness["variant_id"])
            cloudy_strengths.add(texture["cloudy_displacement_strength"])
            pitting_strengths.add(texture["pitting_modulation_strength"])
        self.assertGreater(len(variants), 1)
        self.assertGreater(len(cloudy_strengths), 1)
        self.assertGreater(len(pitting_strengths), 1)

        polished_data = copy.deepcopy(recipe.data)
        polished_texture = polished_data["material"]["concrete_texture"]
        polished_texture["surface_roughness_variation"]["choices"] = [
            {
                "id": "polished",
                "weight": 1.0,
                "displacement_multiplier_range": [0.0, 0.0],
                "pitting_multiplier_range": [0.0, 0.0],
            }
        ]
        polished = resolve_material(polished_data)["material"]["concrete_texture"]
        self.assertEqual(polished["cloudy_displacement_strength"], 0.0)
        self.assertEqual(polished["pitting_coarse_depth"], 0.0)
        self.assertEqual(polished["pitting_fine_depth"], 0.0)
        self.assertEqual(polished["pitting_modulation_strength"], 0.0)

    def test_material_aggregate_resolves_repeatably_and_varies_by_seed(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        left = resolve_material(recipe.data)
        right = resolve_material(recipe.data)
        self.assertEqual(left["material"]["concrete_texture"], right["material"]["concrete_texture"])
        resolved = left["material"]["concrete_texture"]["aggregate_variation_resolved"]
        self.assertEqual(resolved["selection_mode"], "seeded_random")
        self.assertIn(resolved["variant_id"], {"none", "sparse", "moderate"})

        variants = set()
        active_scales = set()
        for seed in range(12345, 12365):
            variant_data = dict(recipe.data)
            variant_data["run"] = dict(recipe.data["run"])
            variant_data["run"]["seed"] = seed
            texture = resolve_material(variant_data)["material"]["concrete_texture"]
            variants.add(texture["aggregate_variation_resolved"]["variant_id"])
            if texture["aggregate_variation_resolved"]["enabled"]:
                active_scales.add(texture["aggregate_variation_resolved"]["scale"])
        self.assertGreater(len(variants), 1)
        self.assertGreater(len(active_scales), 1)

    def test_multitone_surface_family_jitters_colors_repeatably(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))

        colors_by_seed = {}
        positions_by_seed = {}
        for seed in (12349, 12350):
            variant_data = dict(recipe.data)
            variant_data["run"] = dict(recipe.data["run"])
            variant_data["run"]["seed"] = seed
            left = resolve_material(variant_data)["material"]["concrete_texture"]
            right = resolve_material(variant_data)["material"]["concrete_texture"]
            self.assertEqual(left, right)
            self.assertEqual(left["surface_family_variation_resolved"]["variant_id"], "multitone_weathered")
            self.assertIn("color_jitter", left["surface_family_variation_resolved"])
            colors_by_seed[seed] = [stop["color"] for stop in left["base_color_ramp"]]
            positions_by_seed[seed] = [stop["position"] for stop in left["base_color_ramp"]]
            self.assertEqual(positions_by_seed[seed][0], 0.0)
            self.assertEqual(positions_by_seed[seed][-1], 1.0)
            self.assertEqual(positions_by_seed[seed], sorted(positions_by_seed[seed]))

        self.assertNotEqual(colors_by_seed[12349], colors_by_seed[12350])
        self.assertNotEqual(positions_by_seed[12349], positions_by_seed[12350])

    def test_camera_variation_resolves_repeatably_per_seed(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        left = resolve_cameras(recipe.data)
        right = resolve_cameras(recipe.data)
        self.assertEqual(left["captures"][0]["camera"], right["captures"][0]["camera"])
        self.assertGreaterEqual(left["captures"][0]["camera"]["fov_mm"], 50.0)
        self.assertLessEqual(left["captures"][0]["camera"]["fov_mm"], 150.0)
        self.assertEqual(left["captures"][0]["camera"]["fov_mm"], left["captures"][1]["camera"]["fov_mm"])
        self.assertIn("lens_model", left["captures"][1]["camera"])
        self.assertIn("camera_variation", left["captures"][1]["camera"])
        variation = left["captures"][1]["camera"]["camera_variation"]
        self.assertEqual(variation["tilt_azimuth_degrees_range"], [0.0, 360.0])
        self.assertGreaterEqual(variation["azimuth_degrees"], 0.0)
        self.assertLessEqual(variation["azimuth_degrees"], 360.0)
        self.assertGreaterEqual(variation["roll_degrees"], -180.0)
        self.assertLessEqual(variation["roll_degrees"], 180.0)

    def test_camera_orientation_varies_between_seeds(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_simple.yaml"))
        first = dict(recipe.data)
        first["run"] = dict(first["run"])
        first["run"]["seed"] = 12345
        second = dict(recipe.data)
        second["run"] = dict(second["run"])
        second["run"]["seed"] = 12346

        first_camera = resolve_cameras(first)["captures"][0]["camera"]
        second_camera = resolve_cameras(second)["captures"][0]["camera"]

        self.assertNotEqual(
            first_camera["camera_variation"]["azimuth_degrees"],
            second_camera["camera_variation"]["azimuth_degrees"],
        )
        self.assertNotEqual(first_camera["roll_degrees"], second_camera["roll_degrees"])

    def test_parallel_work_ranges_cover_seed_indices_once(self):
        ranges = _parallel_work_ranges(10, 3)
        self.assertEqual(ranges, [(0, 4), (4, 3), (7, 3)])
        indices = []
        for start, count in ranges:
            indices.extend(range(start, start + count))
        self.assertEqual(indices, list(range(10)))

    def test_partial_shadow_occluders_are_seeded_geometry(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        first = dict(recipe.data)
        first["run"] = dict(first["run"])
        first["run"]["seed"] = 12350
        second = dict(recipe.data)
        second["run"] = dict(second["run"])
        second["run"]["seed"] = 12351
        left = resolve_lighting(resolve_cameras(first))["captures"][0]["lighting"]
        repeat = resolve_lighting(resolve_cameras(first))["captures"][0]["lighting"]
        right = resolve_lighting(resolve_cameras(second))["captures"][0]["lighting"]
        self.assertEqual(left["preset_id"], "sunny_partial_shadow")
        self.assertEqual(left["shadow_occluders"], repeat["shadow_occluders"])
        self.assertNotEqual(left["shadow_occluders"], right["shadow_occluders"])
        self.assertEqual(left["shadow_occluders"][0]["type"], "polygon")
        self.assertGreaterEqual(len(left["shadow_occluders"][0]["vertices"]), 6)
        self.assertIn("direction_variation", left["lights"][0])

    def test_generated_crack_center_uses_capture_margins(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        constructed = construct_scene(recipe.data)
        bounds = capture_bounds(recipe.data["captures"][0]["camera"])
        center = constructed.defect["center"]
        self.assertGreaterEqual(center[0], bounds["x_min"] + 0.2 * (bounds["x_max"] - bounds["x_min"]))
        self.assertLessEqual(center[0], bounds["x_min"] + 0.8 * (bounds["x_max"] - bounds["x_min"]))
        self.assertGreaterEqual(center[1], bounds["y_min"] + 0.2 * (bounds["y_max"] - bounds["y_min"]))
        self.assertLessEqual(center[1], bounds["y_min"] + 0.8 * (bounds["y_max"] - bounds["y_min"]))

    def test_visible_defect_is_clipped_to_capture_bounds(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        recipe.data["defect"].pop("length_distribution")
        constructed = construct_scene(recipe.data)
        visible = visible_defect_for_capture(constructed.defect, recipe.data["captures"][0]["camera"])
        self.assertEqual(visible["clip_model"], "camera_frustum")
        self.assertTrue(visible["visible"])
        self.assertLess(
            visible["measurands"]["centerline_length"],
            constructed.defect["measurands"]["centerline_length"],
        )
        self.assertGreaterEqual(len(visible["centerline"]), 2)

    def test_crack_random_walk_does_not_turn_back_or_self_intersect(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        for seed in range(12345, 12355):
            recipe.data["run"]["seed"] = seed
            constructed = construct_scene(recipe.data)
            points = [(point[0], point[1]) for point in constructed.defect["centerline"]]
            overall = (points[-1][0] - points[0][0], points[-1][1] - points[0][1])
            overall_length = math.hypot(overall[0], overall[1])
            direction = (overall[0] / overall_length, overall[1] / overall_length)
            for left, right in zip(points, points[1:]):
                step = (right[0] - left[0], right[1] - left[1])
                self.assertGreater(step[0] * direction[0] + step[1] * direction[1], 0.0)
            for first_index in range(len(points) - 1):
                for second_index in range(first_index + 2, len(points) - 1):
                    if first_index == 0 and second_index == len(points) - 2:
                        continue
                    self.assertFalse(
                        _segments_intersect(
                            points[first_index],
                            points[first_index + 1],
                            points[second_index],
                            points[second_index + 1],
                        )
                    )

    def test_crack_width_varies_between_seed_instances(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        multipliers = []
        max_widths = []
        for seed in range(12345, 12355):
            recipe.data["run"]["seed"] = seed
            constructed = construct_scene(recipe.data)
            params = constructed.defect["construction_parameters"]
            multipliers.append(params["width_multiplier"])
            max_widths.append(constructed.defect["measurands"]["max_width"])
        self.assertGreater(max(multipliers) - min(multipliers), 0.5)
        self.assertGreater(max(max_widths) - min(max_widths), 0.4)

    def test_crack_width_profile_uses_smooth_field(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        constructed = construct_scene(recipe.data)
        params = constructed.defect["construction_parameters"]["width_variation"]
        self.assertEqual(params["field_model"], "fbm_1d")
        self.assertEqual(params["secondary_field_frequency_multiplier"], 9.0)
        self.assertEqual(params["edge_jitter_field_frequency_multiplier"], 34.0)
        self.assertGreater(params["edge_jitter_field_amplitude"], 0.0)
        self.assertLess(params["secondary_field_amplitude"], params["field_amplitude"])
        widths = constructed.defect["width_profile"]
        diffs = [abs(right - left) for left, right in zip(widths, widths[1:])]
        self.assertLess(max(diffs), constructed.defect["measurands"]["max_width"] * 0.45)
        self.assertGreater(max(widths) - min(widths), 0.5)

    def test_default_skeleton_step_is_metrological(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        constructed = construct_scene(recipe.data)
        params = constructed.defect["construction_parameters"]
        self.assertAlmostEqual(params["skeleton_step"], 0.2)
        self.assertLessEqual(params["actual_skeleton_step"], 0.2)
        self.assertEqual(params["kink_interval_model"], "multi_scale_random_distance")
        self.assertEqual(params["micro_kink_min_interval"], 0.35)
        self.assertEqual(params["micro_kink_max_interval"], 1.6)
        self.assertEqual(params["micro_kink_degrees"], 8.0)
        self.assertEqual(params["major_kink_interval_model"], "random_distance")
        self.assertEqual(params["segments"], constructed.defect["measurands"]["point_count"])

    def test_width_profile_stabilizes_offset_boundary(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        recipe.data["run"]["seed"] = 12351
        constructed = construct_scene(recipe.data)
        stabilization = constructed.defect["construction_parameters"]["width_variation"]["boundary_stabilization"]
        self.assertTrue(stabilization["enabled"])
        self.assertEqual(stabilization["remaining_boundary_intersections"], 0)

    def test_simple_track_rejects_intersecting_width_whiskers_without_choke(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_simple.yaml"))
        recipe.data["run"]["seed"] = 12345
        resolved = resolve_lighting(resolve_cameras(recipe.data))
        constructed = construct_scene(resolved)
        stabilization = constructed.defect["construction_parameters"]["width_variation"]["boundary_stabilization"]
        self.assertEqual(stabilization["model"], "width_whisker_intersection_rejection")
        self.assertEqual(stabilization["remaining_boundary_intersections"], 0)
        self.assertNotIn("local_reductions", stabilization)

    def test_width_whisker_rejection_removes_self_intersecting_turns(self):
        points = [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 0.2, 0.0],
            [0.0, 0.2, 0.0],
        ]
        widths = [0.8, 0.8, 0.8, 0.8]

        accepted_points, accepted_widths, stabilization = _filter_intersecting_width_whiskers(points, widths, 1.0)

        self.assertEqual(len(accepted_points), len(accepted_widths))
        self.assertLess(len(accepted_points), len(points))
        self.assertGreater(stabilization["rejected_point_count"], 0)
        self.assertEqual(stabilization["remaining_boundary_intersections"], 0)

    def test_split_displacement_crack_uses_one_moving_side(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_split.yaml"))
        resolved = resolve_lighting(resolve_cameras(recipe.data))
        constructed = construct_scene(resolved)
        defect = constructed.defect
        self.assertEqual(defect["construction_parameters"]["construction_model"], "split_displacement")
        opening = defect["construction_parameters"]["opening_model"]
        self.assertIn(opening["type"], {"hinged", "rigid_offset"})
        self.assertIn(
            opening["physical_model"],
            {"surface_split_rigid_body_offset", "surface_split_hinged_symmetric"},
        )
        self.assertEqual(opening["moving_side"], "both")
        self.assertEqual(max(defect["left_opening_profile"]), opening["half_offset"])
        self.assertEqual(max(defect["right_opening_profile"]), opening["half_offset"])
        self.assertEqual(defect["measurands"]["max_width"], opening["rigid_offset"])
        self.assertLessEqual(defect["measurands"]["max_width"], opening["max_opening"])
        self.assertEqual(defect["construction_parameters"]["length_sampling"]["mode"], "through_surface")
        self.assertIn(
            opening["width_model"],
            {"constant_along_centerline", "hinged_power_profile_along_centerline"},
        )
        if opening["physical_model"] == "surface_split_hinged_symmetric":
            self.assertEqual(min(defect["width_profile"]), 0.0)
        self.assertEqual(len(defect["station_profile"]), defect["measurands"]["point_count"])
        self.assertEqual(len(defect["left_boundary"]), defect["measurands"]["point_count"])
        self.assertEqual(len(defect["right_boundary"]), defect["measurands"]["point_count"])
        self.assertEqual(len(defect["measurement_profile"]), defect["measurands"]["point_count"])
        self.assertGreater(defect["measurands"]["crack_area"], 0.0)
        sample = defect["measurement_profile"][len(defect["measurement_profile"]) // 2]
        self.assertIn("station", sample)
        self.assertIn("width", sample)
        self.assertIn("left_boundary", sample)
        self.assertIn("right_boundary", sample)

    def test_split_displacement_wide_seed_stabilizes_inner_turn_offsets(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_split.yaml"))
        recipe.data["run"]["seed"] = 12352
        resolved = resolve_lighting(resolve_cameras(recipe.data))
        constructed = construct_scene(resolved)
        defect = constructed.defect
        opening = defect["construction_parameters"]["opening_model"]
        self.assertIn(
            opening["physical_model"],
            {"surface_split_rigid_body_offset", "surface_split_hinged_symmetric"},
        )
        self.assertGreater(opening["rigid_offset"], 0.0)
        self.assertLessEqual(defect["measurands"]["max_width"], opening["max_opening"])
        length_sampling = defect["construction_parameters"]["length_sampling"]
        self.assertFalse(length_sampling["endpoint_extension"]["enabled"])
        walk_span = length_sampling["walk_span"]
        self.assertTrue(walk_span["enabled"])
        self.assertTrue(walk_span["start_half"]["crossed_expanded_bounds"])
        self.assertTrue(walk_span["end_half"]["crossed_expanded_bounds"])
        bounds = constructed.surface["bounds"]
        first = defect["centerline"][0]
        last = defect["centerline"][-1]
        self.assertFalse(bounds["x_min"] <= first[0] <= bounds["x_max"] and bounds["y_min"] <= first[1] <= bounds["y_max"])
        self.assertFalse(bounds["x_min"] <= last[0] <= bounds["x_max"] and bounds["y_min"] <= last[1] <= bounds["y_max"])

    def test_length_distribution_prefers_across_view_cracks(self):
        recipe = load_recipe(Path("examples/cracked_plane.yaml"))
        modes = []
        lengths = []
        references = []
        for seed in range(12345, 12445):
            recipe.data["run"]["seed"] = seed
            constructed = construct_scene(recipe.data)
            sampling = constructed.defect["construction_parameters"]["length_sampling"]
            modes.append(sampling["mode"])
            lengths.append(constructed.defect["construction_parameters"]["target_length"])
            references.append(sampling["reference_length"])
        self.assertGreater(modes.count("across_view"), modes.count("one_end_visible"))
        self.assertGreater(modes.count("one_end_visible"), modes.count("contained"))
        self.assertGreater(min(lengths), 10.0)
        for mode, length, reference in zip(modes, lengths, references):
            if mode == "across_view":
                self.assertGreaterEqual(length, reference * 1.08)
            if mode == "contained":
                self.assertLessEqual(length, reference * 0.45)

    def test_blender_script_contains_constructed_geometry(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        constructed = construct_scene(recipe.data)
        scene = {
            "surface": constructed.surface,
            "defect": constructed.defect,
            "seeds": constructed.seeds,
        }
        script = build_blender_script(
            recipe.data,
            recipe.data["captures"][0],
            scene,
            Path("render.jpg"),
            Path("setup.blend"),
        )
        self.assertIn("known_cracked_surface_block", script)
        self.assertIn("make_block_with_crack_hole", script)
        self.assertIn("explicit_ribbon_crack_hole", script)
        self.assertIn("separate_loose_crack_bodies", script)
        self.assertIn("known_cracked_surface_body_", script)
        self.assertIn("\"left\"", script)
        self.assertIn("\"right\"", script)
        self.assertIn("debug_crack_skeleton_points_connected", script)
        self.assertIn("debug_crack_skeleton_station_markers", script)
        self.assertIn("debug_crack_left_truth_boundary", script)
        self.assertIn("debug_crack_right_truth_boundary", script)
        self.assertNotIn("constructed_crack_cut", script)
        self.assertNotIn("crack_cutting_prism", script)
        self.assertNotIn("top_loop_vertex_indices", script)
        self.assertIn("Concrete broad noise", script)
        self.assertIn("concrete surface rough texture", script)
        self.assertIn("Concrete broad noise.001", script)
        self.assertIn("concrete surface cloudy texture", script)
        self.assertIn("Concrete pore noise A", script)
        self.assertIn("dark blemishes", script)
        self.assertIn("Concrete pore noise B", script)
        self.assertIn("bright blemishes", script)
        self.assertIn("Concrete final mix", script)
        self.assertIn("seed_node.label = \"SEED\"", script)
        self.assertIn("noise.noise_dimensions = str(texture.get(\"noise_dimensions\", \"4D\"))", script)
        self.assertIn("pit_noise_coarse", script)
        self.assertIn("pitting_coarse_depth", script)
        self.assertIn("pitting_modulation_strength", script)
        self.assertIn("Aggregate Voronoi mask", script)
        self.assertIn("Concrete aggregate material mix", script)
        self.assertIn("aggregate_enabled", script)
        self.assertIn("render_only_crack_debris", script)
        self.assertIn("render_only_crack_edge_falloff", script)
        self.assertIn("subsurface_crack_edge_falloff", script)
        self.assertIn("metrodef3d_truth_affecting", script)
        self.assertIn("texcoord.outputs[\"Object\"]", script)
        self.assertIn("texture.get(\"mapping_scale\", 0.001)", script)
        self.assertIn("mapping.inputs[\"Scale\"].default_value", script)
        self.assertIn("world_to_camera_view", script)
        self.assertIn("visible_defect_from_blender_camera", script)
        self.assertIn("blender_camera_view", script)
        self.assertIn("segment_fraction_for_point", script)
        self.assertIn("centerline_pixels", script)
        self.assertIn("visible_polygon_pixels", script)
        self.assertIn("write_nominal_surface_pixel_scale", script)
        self.assertIn("scale_x_mm_per_px.npy", script)
        self.assertIn("camera_ray_to_nominal_z0_plane", script)
        self.assertIn("top_right = frame[0]", script)
        self.assertIn("bottom_right = frame[1]", script)
        self.assertIn("bottom_left = frame[2]", script)
        self.assertIn("top_left = frame[3]", script)
        self.assertIn("bpy.context.scene.world.use_nodes = True", script)
        self.assertIn("background_node.inputs[\"Color\"].default_value", script)
        self.assertIn("bpy.context.view_layer.update()", script)
        self.assertNotIn("concrete_texture_space", script)
        self.assertNotIn("texcoord.outputs[\"Generated\"]", script)
        self.assertNotIn("crack_void_material", script)
        self.assertNotIn("constructed_crack_opening", script)
        self.assertNotIn("constructed_crack_boolean_void", script)
        self.assertIn("cam.data.type = \"ORTHO\"", script)
        self.assertIn("BLEND_PATH", script)
        self.assertIn("setup.blend", script)
        self.assertIn("bpy.ops.render.render", script)

    def test_blender_script_supports_obfuscated_render_variants(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        constructed = construct_scene(recipe.data)
        scene = {
            "surface": constructed.surface,
            "defect": constructed.defect,
            "seeds": constructed.seeds,
        }
        capture = recipe.data["captures"][1]
        variant = capture["render_variants"][0]
        script = build_blender_script(
            recipe.data,
            capture,
            scene,
            Path("render.jpg"),
            Path("setup.blend"),
            Path("visible.json"),
            variant,
        )
        self.assertIn("render_variant", script)
        self.assertIn("add_obfuscated_surface_texture", script)
        self.assertIn("colorful_noise", script)
        self.assertIn("noise.outputs[\"Color\"]", script)
        self.assertIn("first_socket(noise.outputs, (\"Factor\", \"Fac\"))", script)
        self.assertNotIn("Obfuscation color ramp", script)
        self.assertIn("Obfuscation SEED", script)

    def test_blender_script_supports_physically_sized_photographic_texture(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_simple.yaml"))
        recipe.data["material"] = {
            "surface_color": "#d8d2c8",
            "crack_color": "#181513",
            "roughness": 0.65,
            "texture_model": "photographic",
            "photographic_texture": {
                "path": "/tmp/concrete.jpg",
                "physical_width_mm": 200.0,
                "physical_height_mm": 200.0,
                "center_mm": [0.0, 0.0],
                "extension": "CLIP",
            },
        }
        constructed = construct_scene(recipe.data)
        scene = {
            "surface": constructed.surface,
            "defect": constructed.defect,
            "seeds": constructed.seeds,
        }
        script = build_blender_script(
            recipe.data,
            recipe.data["captures"][0],
            scene,
            Path("render.jpg"),
            Path("setup.blend"),
        )
        self.assertIn("add_photographic_texture", script)
        self.assertIn("ShaderNodeTexImage", script)
        self.assertIn("photographic_texture_coordinates", script)
        self.assertIn('float(texture["physical_width_mm"])', script)
        self.assertIn('float(texture["physical_height_mm"])', script)
        self.assertIn("/tmp/concrete.jpg", script)

    def test_blender_recipe_has_multiple_capture_passes(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        self.assertEqual(recipe.data["render"]["image_format"], "jpg")
        self.assertEqual([capture["id"] for capture in recipe.data["captures"]], ["overhead-area", "perspective-area"])
        self.assertEqual(recipe.data["captures"][0]["camera"]["orthographic_scale"], 150.0)
        self.assertEqual(recipe.data["captures"][0]["lighting"]["type"], "preset_random")
        self.assertEqual(recipe.data["captures"][1]["camera"]["type"], "perspective")
        self.assertAlmostEqual(recipe.data["captures"][1]["camera"]["fov_degrees"], 17.061531)
        self.assertNotIn("orthographic_scale", recipe.data["captures"][1]["camera"])
        self.assertEqual(recipe.data["captures"][1]["lighting"], recipe.data["captures"][0]["lighting"])
        self.assertEqual(
            [variant["output_id"] for variant in recipe.data["captures"][1]["render_variants"]],
            ["perspective-area-colorful", "perspective-area-bw"],
        )

    def test_output_plan_places_perspective_render_variants_in_parallel_folders(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        plan = _output_plan(recipe.data, Path("runs/test"))
        variants = plan["captures"]["perspective-area"]["variants"]
        self.assertEqual(
            variants["colorful"]["image"],
            Path("runs/test/img/perspective-area-colorful/12345.jpg"),
        )
        self.assertEqual(
            variants["bw"]["visible_defect"],
            Path("runs/test/visible_defect/perspective-area/12345.json"),
        )
        self.assertEqual(
            variants["bw"]["pixel_scale"],
            Path("runs/test/pixel_scale/perspective-area/12345.npz"),
        )
        self.assertEqual(plan["captures"]["__batch__"]["blend"], Path("runs/test/blend/12345.blend"))
        self.assertEqual(plan["captures"]["__batch__"]["blender_script"], Path("runs/test/blender_script/12345.py"))

    def test_simple_track_output_plan_is_perspective_only(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender_simple.yaml"))
        plan = _output_plan(recipe.data, Path("runs/test"))
        self.assertEqual(set(plan["captures"].keys()), {"perspective-area", "__batch__"})
        self.assertEqual(plan["captures"]["perspective-area"]["image"], Path("runs/test/img/12345.jpg"))
        self.assertEqual(
            plan["captures"]["perspective-area"]["visible_defect"],
            Path("runs/test/visible_defect/12345.json"),
        )
        self.assertEqual(plan["captures"]["perspective-area"]["pixel_scale"], Path("runs/test/pixel_scale/12345.npz"))
        self.assertNotIn("variants", plan["captures"]["perspective-area"])

    def test_blender_backend_fails_clearly_when_executable_missing(self):
        recipe = load_recipe(Path("examples/cracked_plane_blender.yaml"))
        recipe.data["render"]["executable"] = "definitely-missing-blender-executable"
        constructed = construct_scene(recipe.data)
        scene = {
            "surface": constructed.surface,
            "defect": constructed.defect,
            "seeds": constructed.seeds,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RenderError, "Blender executable not found"):
                render_image(recipe.data, scene, Path(tmp))


if __name__ == "__main__":
    unittest.main()


def _segments_intersect(a, b, c, d):
    def orientation(p, q, r):
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    return o1 * o2 < 0.0 and o3 * o4 < 0.0
