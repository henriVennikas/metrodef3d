from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .errors import RecipeError
from . import simple_yaml


@dataclass(frozen=True)
class Recipe:
    path: Optional[Path]
    data: Dict[str, Any]


DEFAULT_CAMERA = {
    "type": "orthographic",
    "position": [0.0, 0.0, 500.0],
    "target": [0.0, 0.0, 0.0],
    "orthographic_scale": 150.0,
    "resolution": [1024, 1024],
}

DEFAULT_LIGHTING = {
    "type": "area",
    "position": [0.0, 0.0, 250.0],
    "energy": 2000000.0,
    "size": 150.0,
}


def load_recipe(path: Path) -> Recipe:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeError("Could not read recipe: " + str(path)) from exc

    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
    except ModuleNotFoundError:
        loaded = simple_yaml.loads(text)
    except Exception as exc:
        raise RecipeError("Could not parse YAML recipe: " + str(exc)) from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise RecipeError("Recipe must contain a top-level mapping.")
    loaded = normalize_recipe(loaded)
    recipe = Recipe(path=path, data=loaded)
    validate_recipe(recipe)
    return recipe


def normalize_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(data)
    if "camera" not in normalized:
        normalized["camera"] = dict(DEFAULT_CAMERA)
    else:
        normalized["camera"] = _merged_default(DEFAULT_CAMERA, normalized["camera"])
    normalized["camera"] = _camera_for_type(normalized["camera"])
    if "lighting" not in normalized:
        normalized["lighting"] = dict(DEFAULT_LIGHTING)
    else:
        normalized["lighting"] = _merged_default(DEFAULT_LIGHTING, normalized["lighting"])

    if "captures" not in normalized:
        normalized["captures"] = [
            {
                "id": "default",
                "camera": dict(normalized["camera"]),
                "lighting": dict(normalized["lighting"]),
            }
        ]
    else:
        captures = []
        for index, capture in enumerate(normalized["captures"]):
            if not isinstance(capture, Mapping):
                raise RecipeError("captures entries must be mappings.")
            capture_data = dict(capture)
            capture_data.setdefault("id", "capture-" + str(index + 1))
            capture_data["camera"] = _merged_default(DEFAULT_CAMERA, capture_data.get("camera", {}))
            capture_data["camera"] = _camera_for_type(capture_data["camera"])
            capture_data["lighting"] = _merged_default(DEFAULT_LIGHTING, capture_data.get("lighting", {}))
            captures.append(capture_data)
        normalized["captures"] = captures
        if captures:
            normalized["camera"] = dict(captures[0]["camera"])
            normalized["lighting"] = dict(captures[0]["lighting"])
    return normalized


def validate_recipe(recipe: Recipe) -> None:
    data = recipe.data
    _require_mapping(data, "recipe")

    _required(data, "run")
    _required(data, "surface")
    _required(data, "defect")
    _required(data, "material")
    _required(data, "render")
    _required(data, "captures")

    run = _mapping(data, "run")
    _string(run, "id")
    _int(run, "seed", minimum=0)

    surface = _mapping(data, "surface")
    _literal(surface, "type", {"plane"})
    _number(surface, "width", minimum=0.001)
    _number(surface, "height", minimum=0.001)
    _int(surface, "subdivisions_x", minimum=1)
    _int(surface, "subdivisions_y", minimum=1)

    defect = _mapping(data, "defect")
    _literal(defect, "type", {"crack"})
    if "construction_model" in defect:
        _literal(defect, "construction_model", {"ribbon_fbm_width", "split_displacement"})
    _number(defect, "length", minimum=10.0)
    if "length_distribution" in defect:
        _validate_length_distribution(_mapping(defect, "length_distribution"))
    _number(defect, "nominal_width", minimum=0.000001)
    _number(defect, "depth", minimum=0.000001)
    _number(defect, "roughness", minimum=0.0)
    if "skeleton_step" in defect:
        _number(defect, "skeleton_step", minimum=0.001)
    if "path_control_step" in defect:
        _number(defect, "path_control_step", minimum=0.001)
    if "path_jaggedness" in defect:
        path_jaggedness = _mapping(defect, "path_jaggedness")
        for key in (
            "heading_drift_degrees",
            "micro_min_interval",
            "micro_max_interval",
            "micro_degrees",
            "micro_sigma_degrees",
            "minor_min_interval",
            "minor_max_interval",
            "minor_degrees",
            "minor_sigma_degrees",
            "major_min_interval",
            "major_max_interval",
            "major_degrees",
            "major_sigma_degrees",
            "max_turn_degrees",
            "preferred_nudge_degrees",
        ):
            if key in path_jaggedness:
                _number(path_jaggedness, key, minimum=0.0)
        for prefix in ("micro", "minor", "major"):
            min_key = prefix + "_min_interval"
            max_key = prefix + "_max_interval"
            if min_key in path_jaggedness and max_key in path_jaggedness:
                if float(path_jaggedness[min_key]) > float(path_jaggedness[max_key]):
                    raise RecipeError("path_jaggedness." + min_key + " must be <= " + max_key + ".")
    if "segments" in defect:
        _int(defect, "segments", minimum=2)
    _optional_pair(defect, "center")
    if "width_variation" in defect:
        width_variation = _mapping(defect, "width_variation")
        _number(width_variation, "min_multiplier", minimum=0.001)
        _number(width_variation, "max_multiplier", minimum=0.001)
        min_multiplier = float(width_variation["min_multiplier"])
        max_multiplier = float(width_variation["max_multiplier"])
        if min_multiplier > max_multiplier:
            raise RecipeError("width_variation.min_multiplier must be <= max_multiplier.")
        if "field_amplitude" in width_variation:
            _number(width_variation, "field_amplitude", minimum=0.0, maximum=10.0)
        if "field_octaves" in width_variation:
            _int(width_variation, "field_octaves", minimum=1)
        if "field_base_frequency" in width_variation:
            _number(width_variation, "field_base_frequency", minimum=0.001)
        if "secondary_field_amplitude" in width_variation:
            _number(width_variation, "secondary_field_amplitude", minimum=0.0, maximum=10.0)
        if "secondary_field_octaves" in width_variation:
            _int(width_variation, "secondary_field_octaves", minimum=1)
        if "secondary_field_frequency_multiplier" in width_variation:
            _number(width_variation, "secondary_field_frequency_multiplier", minimum=1.0)
        if "edge_jitter_field_amplitude" in width_variation:
            _number(width_variation, "edge_jitter_field_amplitude", minimum=0.0, maximum=10.0)
        if "edge_jitter_field_octaves" in width_variation:
            _int(width_variation, "edge_jitter_field_octaves", minimum=1)
        if "edge_jitter_field_frequency_multiplier" in width_variation:
            _number(width_variation, "edge_jitter_field_frequency_multiplier", minimum=1.0)
        if "end_taper_fraction" in width_variation:
            _number(width_variation, "end_taper_fraction", minimum=0.001, maximum=0.5)
    if "opening_model" in defect:
        opening_model = _mapping(defect, "opening_model")
        if "type" in opening_model:
            _literal(opening_model, "type", {"hinged"})
        for key in (
            "min_opening",
            "max_opening_min",
            "max_opening_max",
            "contact_opening_max",
            "profile_exponent_min",
            "profile_exponent_max",
            "edge_jitter_amplitude",
            "vertical_offset_max",
            "hinge_probability",
        ):
            if key in opening_model:
                _number(opening_model, key, minimum=0.0)
        if "hinge_probability" in opening_model:
            _number(opening_model, "hinge_probability", minimum=0.0, maximum=1.0)

    _validate_camera(_mapping(data, "camera"))
    _validate_lighting(_mapping(data, "lighting"))

    captures = _required(data, "captures")
    if not isinstance(captures, list) or not captures:
        raise RecipeError("captures must be a non-empty list.")
    seen_capture_ids = set()
    for capture in captures:
        capture_map = _require_mapping(capture, "capture")
        capture_id = _string(capture_map, "id")
        if capture_id in seen_capture_ids:
            raise RecipeError("capture id must be unique: " + capture_id)
        seen_capture_ids.add(capture_id)
        _validate_camera(_mapping(capture_map, "camera"))
        _validate_lighting(_mapping(capture_map, "lighting"))
        if "render_variants" in capture_map:
            variants = capture_map["render_variants"]
            if not isinstance(variants, list):
                raise RecipeError("capture render_variants must be a list.")
            seen_variant_ids = set()
            for variant in variants:
                variant_map = _require_mapping(variant, "render_variant")
                variant_id = _string(variant_map, "id")
                if variant_id in seen_variant_ids:
                    raise RecipeError("render variant id must be unique within capture: " + variant_id)
                seen_variant_ids.add(variant_id)
                if "enabled" in variant_map and not isinstance(variant_map["enabled"], bool):
                    raise RecipeError("render variant enabled must be a boolean.")
                if "output_id" in variant_map:
                    _string(variant_map, "output_id")
                _literal(variant_map, "type", {"colorful_noise", "bw_noise"})
                if "seed_offset" in variant_map:
                    _int(variant_map, "seed_offset")
                if "texture" in variant_map:
                    texture = _mapping(variant_map, "texture")
                    for key in (
                        "mapping_scale",
                        "noise_scale",
                        "noise_detail",
                        "noise_roughness",
                        "noise_lacunarity",
                        "roughness",
                        "diffuse_roughness",
                        "coat_weight",
                        "coat_roughness",
                        "coat_ior",
                        "dark_value",
                        "mid_value",
                        "bright_value",
                        "seed_w",
                    ):
                        if key in texture:
                            _number(texture, key, minimum=0.0)
                    if "noise_dimensions" in texture:
                        _literal(texture, "noise_dimensions", {"1D", "2D", "3D", "4D"})
                    if "noise_normalize" in texture and not isinstance(texture["noise_normalize"], bool):
                        raise RecipeError("render variant texture noise_normalize must be a boolean.")

    material = _mapping(data, "material")
    _string(material, "surface_color")
    _string(material, "crack_color")
    _number(material, "roughness", minimum=0.0, maximum=1.0)
    if "texture_model" in material:
        _literal(material, "texture_model", {"none", "concrete_noise", "photographic"})
    if material.get("texture_model") == "photographic":
        photographic_texture = _mapping(material, "photographic_texture")
        _string(photographic_texture, "path")
        _number(photographic_texture, "physical_width_mm", minimum=0.001)
        _number(photographic_texture, "physical_height_mm", minimum=0.001)
        if "center_mm" in photographic_texture:
            _list_of_numbers(photographic_texture, "center_mm", 2)
        if "rotation_degrees" in photographic_texture:
            _number(photographic_texture, "rotation_degrees")
        if "interpolation" in photographic_texture:
            _literal(photographic_texture, "interpolation", {"Closest", "Linear", "Cubic", "Smart"})
        if "extension" in photographic_texture:
            _literal(photographic_texture, "extension", {"CLIP", "EXTEND", "REPEAT", "MIRROR"})
        if "color_space" in photographic_texture:
            _string(photographic_texture, "color_space")
    if "concrete_texture" in material:
        concrete_texture = _mapping(material, "concrete_texture")
        if "noise_dimensions" in concrete_texture:
            _literal(concrete_texture, "noise_dimensions", {"1D", "2D", "3D", "4D"})
        if "cloudy_noise_dimensions" in concrete_texture:
            _literal(concrete_texture, "cloudy_noise_dimensions", {"1D", "2D", "3D", "4D"})
        if "pore_noise_dimensions" in concrete_texture:
            _literal(concrete_texture, "pore_noise_dimensions", {"1D", "2D", "3D", "4D"})
        for key in (
            "noise_scale",
            "noise_detail",
            "noise_roughness",
            "noise_lacunarity",
            "noise_ramp_black",
            "noise_ramp_white",
            "cloudy_noise_scale",
            "cloudy_noise_detail",
            "cloudy_noise_roughness",
            "cloudy_noise_lacunarity",
            "cloudy_ramp_black",
            "cloudy_ramp_white",
            "voronoi_scale",
            "voronoi_ramp_white",
            "voronoi_roughness",
            "voronoi_randomness",
            "pore_noise_a_scale",
            "pore_noise_b_scale",
            "pore_noise_a_detail",
            "pore_noise_b_detail",
            "pore_noise_roughness",
            "pore_noise_lacunarity",
            "pore_mix_factor",
            "pore_ramp_a_black",
            "pore_ramp_a_white",
            "pore_ramp_b_white",
            "pore_ramp_b_black",
            "final_mix_factor",
            "mapping_scale",
            "base_from_min",
            "base_from_max",
            "base_to_min",
            "base_to_max",
            "base_color_mix_factor",
            "cloudy_displacement_strength",
            "pitting_coarse_scale",
            "pitting_coarse_detail",
            "pitting_coarse_roughness",
            "pitting_coarse_ramp_black",
            "pitting_fine_scale",
            "pitting_fine_detail",
            "pitting_fine_roughness",
            "pitting_fine_ramp_black",
            "pitting_modulation_scale",
            "pitting_modulation_detail",
            "pitting_modulation_roughness",
            "pitting_modulation_strength",
            "aggregate_scale",
            "aggregate_ramp_black",
            "aggregate_ramp_white",
            "aggregate_roughness",
            "seed_w",
        ):
            if key in concrete_texture:
                _number(concrete_texture, key, minimum=0.0)
        for key in (
            "noise_ramp_black_color",
            "noise_ramp_white_color",
            "pore_ramp_a_black_color",
            "pore_ramp_a_white_color",
            "pore_ramp_b_black_color",
            "pore_ramp_b_white_color",
        ):
            if key in concrete_texture:
                _string(concrete_texture, key)
        if "pore_noise_normalize" in concrete_texture and not isinstance(concrete_texture["pore_noise_normalize"], bool):
            raise RecipeError("pore_noise_normalize must be a boolean.")
        if "base_color_model" in concrete_texture:
            _literal(concrete_texture, "base_color_model", {"mix", "ramp"})
        if "base_color_ramp" in concrete_texture:
            _validate_color_ramp(concrete_texture["base_color_ramp"], "base_color_ramp")
        if "aggregate_enabled" in concrete_texture and not isinstance(concrete_texture["aggregate_enabled"], bool):
            raise RecipeError("aggregate_enabled must be a boolean.")
        if "aggregate_color" in concrete_texture:
            _string(concrete_texture, "aggregate_color")
        for key in ("pitting_coarse_depth", "pitting_fine_depth"):
            if key in concrete_texture:
                _number(concrete_texture, key)
        if "base_mix_color" in concrete_texture:
            _string(concrete_texture, "base_mix_color")
        if "surface_family_variation" in concrete_texture:
            surface_family_variation = _mapping(concrete_texture, "surface_family_variation")
            if "enabled" in surface_family_variation and not isinstance(surface_family_variation["enabled"], bool):
                raise RecipeError("surface_family_variation.enabled must be a boolean.")
            if "selection_key" in surface_family_variation:
                _string(surface_family_variation, "selection_key")
            if "choices" in surface_family_variation:
                choices = surface_family_variation["choices"]
                if not isinstance(choices, list) or not choices:
                    raise RecipeError("surface_family_variation.choices must be a non-empty list.")
                for choice in choices:
                    choice_map = _require_mapping(choice, "surface_family_variation choice")
                    _string(choice_map, "id")
                    if "weight" in choice_map:
                        _number(choice_map, "weight", minimum=0.0)
                    if "overrides" in choice_map and not isinstance(choice_map["overrides"], Mapping):
                        raise RecipeError("surface_family_variation choice overrides must be a mapping.")
        if "pitting_variation" in concrete_texture:
            pitting_variation = _mapping(concrete_texture, "pitting_variation")
            if "enabled" in pitting_variation and not isinstance(pitting_variation["enabled"], bool):
                raise RecipeError("pitting_variation.enabled must be a boolean.")
            if "selection_key" in pitting_variation:
                _string(pitting_variation, "selection_key")
            if "choices" in pitting_variation:
                choices = pitting_variation["choices"]
                if not isinstance(choices, list) or not choices:
                    raise RecipeError("pitting_variation.choices must be a non-empty list.")
                for choice in choices:
                    choice_map = _require_mapping(choice, "pitting_variation choice")
                    _string(choice_map, "id")
                    if "weight" in choice_map:
                        _number(choice_map, "weight", minimum=0.0)
                    multiplier_range = _list_of_numbers(choice_map, "multiplier_range", 2)
                    if multiplier_range[0] > multiplier_range[1]:
                        raise RecipeError("pitting_variation choice multiplier_range minimum must be <= maximum.")
        if "surface_roughness_variation" in concrete_texture:
            roughness_variation = _mapping(concrete_texture, "surface_roughness_variation")
            if "enabled" in roughness_variation and not isinstance(roughness_variation["enabled"], bool):
                raise RecipeError("surface_roughness_variation.enabled must be a boolean.")
            if "selection_key" in roughness_variation:
                _string(roughness_variation, "selection_key")
            if "choices" in roughness_variation:
                choices = roughness_variation["choices"]
                if not isinstance(choices, list) or not choices:
                    raise RecipeError("surface_roughness_variation.choices must be a non-empty list.")
                for choice in choices:
                    choice_map = _require_mapping(choice, "surface_roughness_variation choice")
                    _string(choice_map, "id")
                    if "weight" in choice_map:
                        _number(choice_map, "weight", minimum=0.0)
                    for range_key in ("displacement_multiplier_range", "pitting_multiplier_range"):
                        if range_key in choice_map:
                            pair = _list_of_numbers(choice_map, range_key, 2)
                            if pair[0] > pair[1]:
                                raise RecipeError(
                                    "surface_roughness_variation choice " + range_key + " minimum must be <= maximum."
                                )
        if "aggregate_variation" in concrete_texture:
            aggregate_variation = _mapping(concrete_texture, "aggregate_variation")
            if "enabled" in aggregate_variation and not isinstance(aggregate_variation["enabled"], bool):
                raise RecipeError("aggregate_variation.enabled must be a boolean.")
            if "selection_key" in aggregate_variation:
                _string(aggregate_variation, "selection_key")
            if "choices" in aggregate_variation:
                choices = aggregate_variation["choices"]
                if not isinstance(choices, list) or not choices:
                    raise RecipeError("aggregate_variation.choices must be a non-empty list.")
                for choice in choices:
                    choice_map = _require_mapping(choice, "aggregate_variation choice")
                    _string(choice_map, "id")
                    if "enabled" in choice_map and not isinstance(choice_map["enabled"], bool):
                        raise RecipeError("aggregate_variation choice enabled must be a boolean.")
                    if "weight" in choice_map:
                        _number(choice_map, "weight", minimum=0.0)
                    for range_key in ("scale_range", "ramp_black_range", "ramp_width_range", "roughness_range"):
                        if range_key in choice_map:
                            pair = _list_of_numbers(choice_map, range_key, 2)
                            if pair[0] > pair[1]:
                                raise RecipeError("aggregate_variation choice " + range_key + " minimum must be <= maximum.")
                    if "color_choices" in choice_map:
                        colors = choice_map["color_choices"]
                        if not isinstance(colors, list) or not colors:
                            raise RecipeError("aggregate_variation choice color_choices must be a non-empty list.")
                        for color in colors:
                            if not isinstance(color, str) or not color:
                                raise RecipeError("aggregate_variation choice color_choices entries must be strings.")

    render = _mapping(data, "render")
    backend = _literal(render, "backend", {"preview", "blender"})
    if backend == "preview":
        _literal(render, "image_format", {"ppm"})
    else:
        _literal(render, "image_format", {"jpg", "jpeg", "png"})
    if "executable" in render:
        _string(render, "executable")
    if "block_depth" in render:
        _number(render, "block_depth", minimum=0.001)
    if "world_color" in render:
        color = _list_of_numbers(render, "world_color", 3)
        for channel in color:
            if channel < 0.0 or channel > 1.0:
                raise RecipeError("world_color channels must be between 0.0 and 1.0.")
    if "render_detail" in render:
        render_detail = _mapping(render, "render_detail")
        if "crack_edge_falloff" in render_detail:
            crack_edge_falloff = _mapping(render_detail, "crack_edge_falloff")
            for key in (
                "min_width_fraction",
                "max_width_fraction",
                "depth_multiplier",
                "roughness",
                "coarse_period_mm",
                "fine_period_mm",
                "lateral_jitter_fraction",
            ):
                if key in crack_edge_falloff:
                    _number(crack_edge_falloff, key, minimum=0.0)
            if (
                "min_width_fraction" in crack_edge_falloff
                and "max_width_fraction" in crack_edge_falloff
                and float(crack_edge_falloff["min_width_fraction"]) > float(crack_edge_falloff["max_width_fraction"])
            ):
                raise RecipeError("crack_edge_falloff.min_width_fraction must be <= max_width_fraction.")
        if "crack_debris" in render_detail:
            crack_debris = _mapping(render_detail, "crack_debris")
            if "probability" in crack_debris:
                _number(crack_debris, "probability", minimum=0.0, maximum=1.0)
            for key in ("count_per_100mm_range", "depth_range", "size_range", "vertex_count_range"):
                if key in crack_debris:
                    pair = _list_of_numbers(crack_debris, key, 2)
                    if pair[0] > pair[1]:
                        raise RecipeError("crack_debris." + key + " minimum must be <= maximum.")
            for key in ("width_fraction_max",):
                if key in crack_debris:
                    _number(crack_debris, key, minimum=0.0)


def _merged_default(default: Mapping[str, Any], override: Any) -> Dict[str, Any]:
    if not isinstance(override, Mapping):
        raise RecipeError("Defaulted recipe sections must be mappings.")
    merged = dict(default)
    merged.update(override)
    return merged


def _camera_for_type(camera: Mapping[str, Any]) -> Dict[str, Any]:
    typed_camera = dict(camera)
    if typed_camera.get("type") == "perspective":
        typed_camera.pop("orthographic_scale", None)
    else:
        typed_camera.pop("fov_degrees", None)
    return typed_camera


def _validate_camera(camera: Mapping[str, Any]) -> None:
    camera_type = _literal(camera, "type", {"orthographic", "perspective"})
    _list_of_numbers(camera, "position", 3)
    _list_of_numbers(camera, "target", 3)
    _list_of_ints(camera, "resolution", 2, minimum=1)
    if camera_type == "orthographic":
        _number(camera, "orthographic_scale", minimum=0.001)
    else:
        _number(camera, "fov_degrees", minimum=1.0, maximum=179.0)


def _validate_lighting(lighting: Mapping[str, Any]) -> None:
    lighting_type = _literal(lighting, "type", {"area", "sun", "spot", "point", "multi", "preset_random", "preset"})
    if lighting_type == "preset_random":
        if "choices" in lighting:
            choices = lighting["choices"]
            if not isinstance(choices, list) or not choices:
                raise RecipeError("lighting.choices must be a non-empty list when provided.")
        return
    if lighting_type == "preset":
        _string(lighting, "preset")
        return
    if lighting_type == "multi":
        lights = lighting.get("lights")
        if not isinstance(lights, list) or not lights:
            raise RecipeError("multi lighting must define a non-empty lights list.")
        for light in lights:
            _validate_lighting(_require_mapping(light, "light"))
        if "shadow_occluders" in lighting:
            occluders = lighting["shadow_occluders"]
            if occluders == "seeded_irregular":
                return
            if not isinstance(occluders, list):
                raise RecipeError("lighting.shadow_occluders must be a list.")
            for occluder in occluders:
                _validate_shadow_occluder(_require_mapping(occluder, "shadow_occluder"))
        return

    _number(lighting, "energy", minimum=0.0)
    if lighting_type != "sun":
        _list_of_numbers(lighting, "position", 3)
    elif "position" in lighting:
        _list_of_numbers(lighting, "position", 3)
    if "target" in lighting:
        _list_of_numbers(lighting, "target", 3)
    if lighting_type == "area":
        _number(lighting, "size", minimum=0.001)
        if "size_y" in lighting:
            _number(lighting, "size_y", minimum=0.001)
        if "shape" in lighting:
            _literal(lighting, "shape", {"square", "rectangle", "disk", "ellipse"})
    elif lighting_type == "sun":
        if "angle_degrees" in lighting:
            _number(lighting, "angle_degrees", minimum=0.0, maximum=180.0)
    elif lighting_type == "spot":
        if "spot_size_degrees" in lighting:
            _number(lighting, "spot_size_degrees", minimum=0.001, maximum=180.0)
        if "spot_blend" in lighting:
            _number(lighting, "spot_blend", minimum=0.0, maximum=1.0)
        if "shadow_soft_size" in lighting:
            _number(lighting, "shadow_soft_size", minimum=0.0)
    elif lighting_type == "point":
        if "shadow_soft_size" in lighting:
            _number(lighting, "shadow_soft_size", minimum=0.0)


def _validate_shadow_occluder(occluder: Mapping[str, Any]) -> None:
    occluder_type = _literal(occluder, "type", {"rectangle", "polygon"})
    _list_of_numbers(occluder, "position", 3)
    if occluder_type == "rectangle":
        size = _list_of_numbers(occluder, "size", 2)
        if min(size) < 0.001:
            raise RecipeError("shadow_occluder.size values must be >= 0.001.")
    else:
        vertices = occluder.get("vertices")
        if not isinstance(vertices, list) or len(vertices) < 3:
            raise RecipeError("polygon shadow_occluder.vertices must contain at least 3 points.")
        for vertex in vertices:
            if not isinstance(vertex, list) or len(vertex) != 2:
                raise RecipeError("polygon shadow_occluder.vertices entries must be 2D points.")
            for value in vertex:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise RecipeError("polygon shadow_occluder.vertices entries must contain numbers.")
    if "rotation_degrees" in occluder:
        _number(occluder, "rotation_degrees")


def _validate_color_ramp(stops: Any, name: str) -> None:
    if not isinstance(stops, list) or len(stops) < 2:
        raise RecipeError(name + " must contain at least two color stops.")
    previous_position = -1.0
    for stop in stops:
        stop_map = _require_mapping(stop, name + " stop")
        position = _number(stop_map, "position", minimum=0.0, maximum=1.0)
        if position < previous_position:
            raise RecipeError(name + " stop positions must be sorted.")
        previous_position = position
        _string(stop_map, "color")


def _validate_length_distribution(distribution: Mapping[str, Any]) -> None:
    modes = ("across_view", "one_end_visible", "contained")
    total_probability = 0.0
    for mode_name in modes:
        if mode_name not in distribution:
            continue
        mode = _mapping(distribution, mode_name)
        probability = _number(mode, "probability", minimum=0.0)
        min_multiplier = _number(mode, "min_chord_multiplier", minimum=0.001)
        max_multiplier = _number(mode, "max_chord_multiplier", minimum=0.001)
        if min_multiplier > max_multiplier:
            raise RecipeError(
                "length_distribution."
                + mode_name
                + ".min_chord_multiplier must be <= max_chord_multiplier."
            )
        total_probability += probability
    if total_probability <= 0.0:
        raise RecipeError("length_distribution must define at least one mode with probability > 0.")


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecipeError(name + " must be a mapping.")
    return value


def _mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = _required(data, key)
    if not isinstance(value, Mapping):
        raise RecipeError(key + " must be a mapping.")
    return value


def _required(data: Mapping[str, Any], key: str) -> Any:
    if key not in data:
        raise RecipeError("Missing required recipe key: " + key)
    return data[key]


def _string(data: Mapping[str, Any], key: str) -> str:
    value = _required(data, key)
    if not isinstance(value, str) or not value:
        raise RecipeError(key + " must be a non-empty string.")
    return value


def _int(data: Mapping[str, Any], key: str, minimum: Optional[int] = None) -> int:
    value = _required(data, key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise RecipeError(key + " must be an integer.")
    if minimum is not None and value < minimum:
        raise RecipeError(key + " must be >= " + str(minimum) + ".")
    return value


def _number(
    data: Mapping[str, Any],
    key: str,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    value = _required(data, key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RecipeError(key + " must be a number.")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise RecipeError(key + " must be >= " + str(minimum) + ".")
    if maximum is not None and numeric > maximum:
        raise RecipeError(key + " must be <= " + str(maximum) + ".")
    return numeric


def _literal(data: Mapping[str, Any], key: str, allowed: set) -> str:
    value = _string(data, key)
    if value not in allowed:
        raise RecipeError(key + " must be one of: " + ", ".join(sorted(allowed)) + ".")
    return value


def _list_of_numbers(data: Mapping[str, Any], key: str, length: int) -> List[float]:
    value = _required(data, key)
    if not isinstance(value, list) or len(value) != length:
        raise RecipeError(key + " must be a list of " + str(length) + " numbers.")
    for item in value:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise RecipeError(key + " must contain only numbers.")
    return [float(item) for item in value]


def _list_of_ints(data: Mapping[str, Any], key: str, length: int, minimum: int) -> List[int]:
    value = _required(data, key)
    if not isinstance(value, list) or len(value) != length:
        raise RecipeError(key + " must be a list of " + str(length) + " integers.")
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool) or item < minimum:
            raise RecipeError(key + " must contain integers >= " + str(minimum) + ".")
    return value


def _optional_pair(data: Mapping[str, Any], key: str) -> Optional[Tuple[float, float]]:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, list) or len(value) != 2:
        raise RecipeError(key + " must be a list of 2 numbers.")
    for item in value:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise RecipeError(key + " must contain only numbers.")
    return float(value[0]), float(value[1])
