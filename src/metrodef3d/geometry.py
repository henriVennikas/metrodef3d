import hashlib
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import VISIBLE_DEFECT_SCHEMA_VERSION


@dataclass(frozen=True)
class ConstructedScene:
    surface: Dict[str, Any]
    defect: Dict[str, Any]
    seeds: Dict[str, int]


def construct_scene(recipe: Mapping[str, Any]) -> ConstructedScene:
    base_seed = int(recipe["run"]["seed"])
    surface_seed = _derive_seed(base_seed, "surface")
    crack_seed = _derive_seed(base_seed, "crack")
    return ConstructedScene(
        surface=_construct_plane(recipe["surface"], surface_seed),
        defect=_construct_crack(recipe, crack_seed),
        seeds={"base": base_seed, "surface": surface_seed, "crack": crack_seed},
    )


def _construct_plane(surface: Mapping[str, Any], seed: int) -> Dict[str, Any]:
    width = float(surface["width"])
    height = float(surface["height"])
    sx = int(surface["subdivisions_x"])
    sy = int(surface["subdivisions_y"])
    return {
        "type": "plane",
        "seed": seed,
        "width": width,
        "height": height,
        "subdivisions_x": sx,
        "subdivisions_y": sy,
        "origin": [0.0, 0.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "bounds": {
            "x_min": -width / 2.0,
            "x_max": width / 2.0,
            "y_min": -height / 2.0,
            "y_max": height / 2.0,
        },
    }


def visible_defect_for_capture(defect: Mapping[str, Any], camera: Mapping[str, Any]) -> Dict[str, Any]:
    clipped_points, clipped_widths, clipped_depths = _clip_profiled_polyline_to_camera(
        defect["centerline"], defect["width_profile"], defect["depth_profile"], camera
    )
    visible = bool(len(clipped_points) >= 2)
    measurands = {
        "centerline_length": round(_polyline_length(clipped_points), 6) if visible else 0.0,
        "max_width": round(max(clipped_widths), 6) if visible else 0.0,
        "max_depth": round(max(clipped_depths), 6) if visible else 0.0,
        "crack_area": round(_profile_area(clipped_points, clipped_widths), 6) if visible else 0.0,
        "point_count": len(clipped_points),
    }
    return {
        "schema": {
            "name": "metrodef3d.visible_defect",
            "version": VISIBLE_DEFECT_SCHEMA_VERSION,
        },
        "visible": visible,
        "clip_model": "camera_frustum",
        "camera_type": camera["type"],
        "clip_fov_mm": camera.get("fov_mm", camera.get("orthographic_scale")),
        "centerline": clipped_points,
        "width_profile": clipped_widths,
        "depth_profile": clipped_depths,
        "measurands": measurands,
    }


def capture_bounds(camera: Mapping[str, Any]) -> Dict[str, float]:
    resolution = camera["resolution"]
    target = camera["target"]
    if camera["type"] == "orthographic":
        vertical = float(camera["orthographic_scale"])
        horizontal = vertical * (float(resolution[0]) / float(resolution[1]))
        return {
            "x_min": float(target[0]) - horizontal / 2.0,
            "x_max": float(target[0]) + horizontal / 2.0,
            "y_min": float(target[1]) - vertical / 2.0,
            "y_max": float(target[1]) + vertical / 2.0,
        }

    corners = _perspective_camera_surface_corners(camera)
    if not corners:
        fov = float(camera.get("fov_mm", 150.0))
        horizontal = fov * (float(resolution[0]) / float(resolution[1]))
        return {
            "x_min": float(target[0]) - horizontal / 2.0,
            "x_max": float(target[0]) + horizontal / 2.0,
            "y_min": float(target[1]) - fov / 2.0,
            "y_max": float(target[1]) + fov / 2.0,
        }
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


def _perspective_camera_surface_corners(camera: Mapping[str, Any]) -> List[Tuple[float, float]]:
    basis = _camera_basis(camera)
    position = basis["position"]
    aspect = float(camera["resolution"][0]) / float(camera["resolution"][1])
    tan_vertical = math.tan(math.radians(float(camera["fov_degrees"])) / 2.0)
    tan_horizontal = tan_vertical * aspect
    corners = []
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            ray = _normalize(
                (
                    basis["forward"][0]
                    + basis["right"][0] * x_sign * tan_horizontal
                    + basis["up"][0] * y_sign * tan_vertical,
                    basis["forward"][1]
                    + basis["right"][1] * x_sign * tan_horizontal
                    + basis["up"][1] * y_sign * tan_vertical,
                    basis["forward"][2]
                    + basis["right"][2] * x_sign * tan_horizontal
                    + basis["up"][2] * y_sign * tan_vertical,
                )
            )
            if abs(ray[2]) < 1.0e-9:
                continue
            distance = -position[2] / ray[2]
            if distance <= 0.0:
                continue
            corners.append((position[0] + ray[0] * distance, position[1] + ray[1] * distance))
    return corners


def _clip_profiled_polyline_to_camera(
    points: List[List[float]],
    widths: List[float],
    depths: List[float],
    camera: Mapping[str, Any],
) -> Tuple[List[List[float]], List[float], List[float]]:
    clipped_points: List[List[float]] = []
    clipped_widths: List[float] = []
    clipped_depths: List[float] = []
    for index in range(len(points) - 1):
        left = points[index]
        right = points[index + 1]
        interval = _camera_segment_interval(left, right, camera)
        if interval is None:
            continue
        start, end = interval
        candidates = [
            (
                start,
                _interpolate_point(left, right, start),
                _interpolate_scalar(widths[index], widths[index + 1], start),
                _interpolate_scalar(depths[index], depths[index + 1], start),
            ),
            (
                end,
                _interpolate_point(left, right, end),
                _interpolate_scalar(widths[index], widths[index + 1], end),
                _interpolate_scalar(depths[index], depths[index + 1], end),
            ),
        ]
        for _fraction, point, width, depth in candidates:
            rounded_point = [round(point[0], 6), round(point[1], 6), round(point[2], 6)]
            if clipped_points and rounded_point == clipped_points[-1]:
                clipped_widths[-1] = round(width, 6)
                clipped_depths[-1] = round(depth, 6)
            else:
                clipped_points.append(rounded_point)
                clipped_widths.append(round(width, 6))
                clipped_depths.append(round(depth, 6))
    return clipped_points, clipped_widths, clipped_depths


def _camera_segment_interval(
    left: List[float],
    right: List[float],
    camera: Mapping[str, Any],
) -> Optional[Tuple[float, float]]:
    basis = _camera_basis(camera)
    left_cam = _camera_coordinates(left, basis)
    right_cam = _camera_coordinates(right, basis)
    if camera["type"] == "orthographic":
        vertical = float(camera["orthographic_scale"])
        horizontal = vertical * (float(camera["resolution"][0]) / float(camera["resolution"][1]))
        planes = [
            (1.0, 0.0, 0.0, horizontal / 2.0),
            (-1.0, 0.0, 0.0, horizontal / 2.0),
            (0.0, 1.0, 0.0, vertical / 2.0),
            (0.0, -1.0, 0.0, vertical / 2.0),
            (0.0, 0.0, 1.0, max(left_cam[2], right_cam[2], 1.0e-6) + 1.0),
        ]
    else:
        aspect = float(camera["resolution"][0]) / float(camera["resolution"][1])
        tan_vertical = math.tan(math.radians(float(camera["fov_degrees"])) / 2.0)
        tan_horizontal = tan_vertical * aspect
        planes = [
            (1.0, 0.0, -tan_horizontal, 0.0),
            (-1.0, 0.0, -tan_horizontal, 0.0),
            (0.0, 1.0, -tan_vertical, 0.0),
            (0.0, -1.0, -tan_vertical, 0.0),
            (0.0, 0.0, -1.0, -1.0e-6),
        ]
    return _clip_camera_interval(left_cam, right_cam, planes)


def _clip_camera_interval(
    left_cam: Tuple[float, float, float],
    right_cam: Tuple[float, float, float],
    planes: List[Tuple[float, float, float, float]],
) -> Optional[Tuple[float, float]]:
    start = 0.0
    end = 1.0
    delta = (
        right_cam[0] - left_cam[0],
        right_cam[1] - left_cam[1],
        right_cam[2] - left_cam[2],
    )
    for a, b, c, d in planes:
        value = a * left_cam[0] + b * left_cam[1] + c * left_cam[2] - d
        slope = a * delta[0] + b * delta[1] + c * delta[2]
        if abs(slope) < 1.0e-12:
            if value > 0.0:
                return None
            continue
        t = -value / slope
        if slope > 0.0:
            end = min(end, t)
        else:
            start = max(start, t)
        if start > end:
            return None
    return (max(0.0, start), min(1.0, end))


def _camera_basis(camera: Mapping[str, Any]) -> Dict[str, Tuple[float, float, float]]:
    position = tuple(float(value) for value in camera["position"])
    target = tuple(float(value) for value in camera["target"])
    forward = _normalize((target[0] - position[0], target[1] - position[1], target[2] - position[2]))
    world_up = (0.0, 1.0, 0.0)
    if abs(_dot(forward, world_up)) > 0.98:
        world_up = (1.0, 0.0, 0.0)
    right = _normalize(_cross(forward, world_up))
    up = _normalize(_cross(right, forward))
    roll = math.radians(float(camera.get("roll_degrees", 0.0)))
    if roll:
        cos_roll = math.cos(roll)
        sin_roll = math.sin(roll)
        rolled_right = (
            right[0] * cos_roll + up[0] * sin_roll,
            right[1] * cos_roll + up[1] * sin_roll,
            right[2] * cos_roll + up[2] * sin_roll,
        )
        rolled_up = (
            up[0] * cos_roll - right[0] * sin_roll,
            up[1] * cos_roll - right[1] * sin_roll,
            up[2] * cos_roll - right[2] * sin_roll,
        )
        right, up = rolled_right, rolled_up
    return {"position": position, "right": right, "up": up, "forward": forward}


def _camera_coordinates(point: List[float], basis: Mapping[str, Tuple[float, float, float]]) -> Tuple[float, float, float]:
    position = basis["position"]
    delta = (point[0] - position[0], point[1] - position[1], point[2] - position[2])
    return (_dot(delta, basis["right"]), _dot(delta, basis["up"]), _dot(delta, basis["forward"]))


def _normalize(vector: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = math.sqrt(_dot(vector, vector)) or 1.0
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _dot(left: Tuple[float, float, float], right: Tuple[float, float, float]) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross(left: Tuple[float, float, float], right: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _construct_crack(recipe: Mapping[str, Any], seed: int) -> Dict[str, Any]:
    defect = recipe["defect"]
    rng = random.Random(seed)
    placement_bounds = capture_bounds(recipe["captures"][0]["camera"])
    surface_bounds = recipe["surface"].get("bounds")
    if surface_bounds is None:
        surface_width = float(recipe["surface"]["width"])
        surface_height = float(recipe["surface"]["height"])
        surface_bounds = {
            "x_min": -surface_width / 2.0,
            "x_max": surface_width / 2.0,
            "y_min": -surface_height / 2.0,
            "y_max": surface_height / 2.0,
        }
    construction_model = str(defect.get("construction_model", "ribbon_fbm_width"))
    nominal_width = float(defect["nominal_width"])
    width_variation = defect.get("width_variation", {})
    min_width_multiplier = float(width_variation.get("min_multiplier", 0.45))
    max_width_multiplier = float(width_variation.get("max_multiplier", 1.9))
    width_field_amplitude = float(width_variation.get("field_amplitude", 3.0))
    width_field_octaves = int(width_variation.get("field_octaves", 5))
    width_field_base_frequency = float(width_variation.get("field_base_frequency", 1.4))
    secondary_width_field_amplitude = float(width_variation.get("secondary_field_amplitude", 1.0))
    secondary_width_field_octaves = int(width_variation.get("secondary_field_octaves", 2))
    secondary_width_field_frequency_multiplier = float(
        width_variation.get("secondary_field_frequency_multiplier", 9.0)
    )
    edge_jitter_field_amplitude = float(width_variation.get("edge_jitter_field_amplitude", 0.65))
    edge_jitter_field_octaves = int(width_variation.get("edge_jitter_field_octaves", 2))
    edge_jitter_field_frequency_multiplier = float(
        width_variation.get("edge_jitter_field_frequency_multiplier", 34.0)
    )
    end_taper_fraction = float(width_variation.get("end_taper_fraction", 0.5))
    width_multiplier = rng.uniform(min_width_multiplier, max_width_multiplier)
    effective_nominal_width = nominal_width * width_multiplier
    depth = float(defect["depth"])
    roughness = float(defect["roughness"])
    if "center" in defect:
        center = (float(defect["center"][0]), float(defect["center"][1]))
    else:
        center = (
            rng.uniform(
                placement_bounds["x_min"] + 0.2 * (placement_bounds["x_max"] - placement_bounds["x_min"]),
                placement_bounds["x_min"] + 0.8 * (placement_bounds["x_max"] - placement_bounds["x_min"]),
            ),
            rng.uniform(
                placement_bounds["y_min"] + 0.2 * (placement_bounds["y_max"] - placement_bounds["y_min"]),
                placement_bounds["y_min"] + 0.8 * (placement_bounds["y_max"] - placement_bounds["y_min"]),
            ),
        )

    angle = rng.uniform(0.0, math.tau)
    if construction_model == "split_displacement":
        surface_chord_length = _line_chord_length(surface_bounds, center, angle)
        surface_overrun_multiplier = float(defect.get("surface_overrun_multiplier", 1.12))
        length = max(float(defect["length"]), surface_chord_length * surface_overrun_multiplier)
        length_sampling = {
            "model": "surface_through_split",
            "mode": "through_surface",
            "reference": "surface_chord",
            "reference_length": round(surface_chord_length, 6),
            "surface_overrun_multiplier": surface_overrun_multiplier,
            "endpoint_extension": {"enabled": False},
        }
    else:
        length, length_sampling = _sample_crack_length(defect, rng, placement_bounds, center, angle)
    skeleton_step = float(defect.get("skeleton_step", 0.2))
    control_step = float(defect.get("path_control_step", 6.857143))
    path_jaggedness = _path_jaggedness(defect)
    if construction_model == "split_displacement":
        extension_margin = float(
            defect.get(
                "surface_extension_margin",
                max(
                    surface_bounds["x_max"] - surface_bounds["x_min"],
                    surface_bounds["y_max"] - surface_bounds["y_min"],
                )
                * 0.12,
            )
        )
        walk_points, span_generation = _random_walk_centerline_across_bounds(
            rng,
            center,
            angle,
            skeleton_step,
            roughness,
            control_step,
            path_jaggedness,
            surface_bounds,
            extension_margin,
        )
        length = _polyline_length_2d(walk_points)
        step = length / float(len(walk_points) - 1)
        length_sampling["endpoint_extension"] = {
            "enabled": False,
            "reason": "walk_generated_until_surface_crossing",
        }
        length_sampling["walk_span"] = span_generation
        segments = len(walk_points)
    else:
        segments = int(math.ceil(length / skeleton_step)) + 1
        if "segments" in defect and "skeleton_step" not in defect:
            segments = int(defect["segments"])
            skeleton_step = length / float(segments - 1)
        step = length / float(segments - 1)
        walk_points = _random_walk_centerline(
            rng,
            center,
            angle,
            step,
            segments,
            roughness,
            control_step,
            path_jaggedness,
        )
    points: List[List[float]] = [[round(x, 6), round(y, 6), 0.0] for x, y in walk_points]
    opening_metadata: Dict[str, Any] = {}
    if construction_model == "split_displacement":
        widths, left_opening, right_opening, opening_metadata = _rigid_split_opening_profile(
            defect,
            rng,
            segments,
        )
        width_stabilization = {
            "enabled": False,
            "reason": "split_displacement_uses_rigid_body_offset",
        }
    else:
        width_field_rng = random.Random(_derive_seed(seed, "width-field"))
        width_field = _fbm_width_field(
            width_field_rng,
            segments,
            width_field_octaves,
            width_field_base_frequency,
        )
        secondary_width_field_rng = random.Random(_derive_seed(seed, "width-field-secondary"))
        secondary_width_field = _fbm_width_field(
            secondary_width_field_rng,
            segments,
            secondary_width_field_octaves,
            width_field_base_frequency * secondary_width_field_frequency_multiplier,
        )
        edge_jitter_width_field_rng = random.Random(_derive_seed(seed, "width-field-edge-jitter"))
        edge_jitter_width_field = _fbm_width_field(
            edge_jitter_width_field_rng,
            segments,
            edge_jitter_field_octaves,
            width_field_base_frequency * edge_jitter_field_frequency_multiplier,
        )
        widths = []
        for index in range(segments):
            fraction = index / float(segments - 1)
            distance_to_end = min(fraction, 1.0 - fraction)
            taper_fraction = max(min(end_taper_fraction, 0.5), 0.001)
            taper = math.sin(0.5 * math.pi * min(1.0, distance_to_end / taper_fraction))
            field_multiplier = max(
                0.05,
                1.0
                + width_field_amplitude * width_field[index]
                + secondary_width_field_amplitude * secondary_width_field[index],
            )
            edge_multiplier = max(
                0.1,
                1.0 + edge_jitter_field_amplitude * edge_jitter_width_field[index],
            )
            widths.append(
                round(
                    max(
                        effective_nominal_width * 0.2,
                        effective_nominal_width * field_multiplier * edge_multiplier * taper,
                    ),
                    6,
                )
            )
        points, widths, width_stabilization = _filter_intersecting_width_whiskers(
            points, widths, effective_nominal_width
        )
        segments = len(points)
        left_opening = [round(width / 2.0, 6) for width in widths]
        right_opening = [round(width / 2.0, 6) for width in widths]

    path_length = _polyline_length(points)
    station_profile = _station_profile(points)
    left_boundary, right_boundary = _crack_boundary_profiles(points, left_opening, right_opening)
    render_geometry_preflight = _render_geometry_preflight(
        construction_model,
        surface_bounds,
        left_boundary,
        right_boundary,
    )
    measurement_profile = _measurement_profile(points, station_profile, widths, left_boundary, right_boundary)
    return {
        "type": "crack",
        "seed": seed,
        "center": [round(center[0], 6), round(center[1], 6), 0.0],
        "orientation_degrees": round(math.degrees(angle), 6),
        "centerline": points,
        "station_profile": station_profile,
        "left_boundary": left_boundary,
        "right_boundary": right_boundary,
        "measurement_profile": measurement_profile,
        "width_profile": widths,
        "left_opening_profile": left_opening,
        "right_opening_profile": right_opening,
        "depth_profile": [round(depth * math.sin(math.pi * i / float(segments - 1)), 6) for i in range(segments)],
        "construction_parameters": {
            "construction_model": construction_model,
            "target_length": length,
            "base_length": float(defect["length"]),
            "length_sampling": length_sampling,
            "nominal_width": nominal_width,
            "effective_nominal_width": round(effective_nominal_width, 6),
            "width_multiplier": round(width_multiplier, 6),
            "width_variation": {
                "min_multiplier": min_width_multiplier,
                "max_multiplier": max_width_multiplier,
                "field_model": "fbm_1d",
                "field_amplitude": width_field_amplitude,
                "field_octaves": width_field_octaves,
                "field_base_frequency": width_field_base_frequency,
                "secondary_field_amplitude": secondary_width_field_amplitude,
                "secondary_field_octaves": secondary_width_field_octaves,
                "secondary_field_frequency_multiplier": secondary_width_field_frequency_multiplier,
                "edge_jitter_field_amplitude": edge_jitter_field_amplitude,
                "edge_jitter_field_octaves": edge_jitter_field_octaves,
                "edge_jitter_field_frequency_multiplier": edge_jitter_field_frequency_multiplier,
                "end_taper_fraction": end_taper_fraction,
                "boundary_stabilization": width_stabilization,
            },
            "opening_model": opening_metadata,
            "render_geometry_preflight": render_geometry_preflight,
            "depth": depth,
            "roughness": roughness,
            "segments": segments,
            "skeleton_step": round(skeleton_step, 6),
            "actual_skeleton_step": round(step, 6),
            "branching_enabled": False,
            "placement_reference": "first_capture_orthographic_field",
            "center_sampling_fraction": [0.2, 0.8],
            "path_model": "directed_random_walk",
            "path_control_step": round(control_step, 6),
            "path_control_step_model": "variable_distance",
            "path_control_step_min": round(control_step * 0.12, 6),
            "path_control_step_max": round(control_step * 3.0, 6),
            "heading_drift_degrees_per_control_step": path_jaggedness["heading_drift_degrees"],
            "kink_interval_model": "multi_scale_random_distance",
            "micro_kink_min_interval": path_jaggedness["micro_min_interval"],
            "micro_kink_max_interval": path_jaggedness["micro_max_interval"],
            "micro_kink_degrees": path_jaggedness["micro_degrees"],
            "minor_kink_min_interval": path_jaggedness["minor_min_interval"],
            "minor_kink_max_interval": path_jaggedness["minor_max_interval"],
            "minor_kink_degrees": path_jaggedness["minor_degrees"],
            "major_kink_interval_model": "random_distance",
            "major_kink_min_interval": path_jaggedness["major_min_interval"],
            "major_kink_max_interval": path_jaggedness["major_max_interval"],
            "major_kink_degrees": path_jaggedness["major_degrees"],
            "max_turn_degrees": path_jaggedness["max_turn_degrees"],
            "skeleton_resampling": "arc_length",
            "self_intersection_allowed": False,
        },
        "measurands": {
            "centerline_length": round(path_length, 6),
            "max_width": round(max(widths), 6),
            "max_depth": depth,
            "crack_area": round(_profile_area(points, widths), 6),
            "point_count": segments,
        },
    }


def _render_geometry_preflight(
    construction_model: str,
    surface_bounds: Mapping[str, float],
    left_boundary: List[List[float]],
    right_boundary: List[List[float]],
) -> Dict[str, Any]:
    boundary = left_boundary + right_boundary
    outside = [
        point
        for point in boundary
        if not (
            float(surface_bounds["x_min"]) <= float(point[0]) <= float(surface_bounds["x_max"])
            and float(surface_bounds["y_min"]) <= float(point[1]) <= float(surface_bounds["y_max"])
        )
    ]
    xs = [float(point[0]) for point in boundary] or [0.0]
    ys = [float(point[1]) for point in boundary] or [0.0]
    outside_count = len(outside)
    point_count = len(boundary)
    explicit_hole_requires_internal_boundary = construction_model != "split_displacement"
    return {
        "model": "explicit_ribbon_hole_preflight",
        "construction_model": construction_model,
        "explicit_hole_requires_internal_boundary": explicit_hole_requires_internal_boundary,
        "boundary_inside_surface": outside_count == 0,
        "outside_boundary_point_count": outside_count,
        "outside_boundary_point_fraction": round(outside_count / float(point_count), 6) if point_count else 0.0,
        "boundary_bbox": {
            "x_min": round(min(xs), 6),
            "x_max": round(max(xs), 6),
            "y_min": round(min(ys), 6),
            "y_max": round(max(ys), 6),
        },
        "surface_bounds": {
            "x_min": round(float(surface_bounds["x_min"]), 6),
            "x_max": round(float(surface_bounds["x_max"]), 6),
            "y_min": round(float(surface_bounds["y_min"]), 6),
            "y_max": round(float(surface_bounds["y_max"]), 6),
        },
        "risk": "explicit_hole_boundary_exits_surface"
        if explicit_hole_requires_internal_boundary and outside_count > 0
        else "none",
    }


def _sample_crack_length(
    defect: Mapping[str, Any],
    rng: random.Random,
    bounds: Mapping[str, float],
    center: Tuple[float, float],
    angle: float,
) -> Tuple[float, Dict[str, Any]]:
    base_length = float(defect["length"])
    distribution = defect.get("length_distribution")
    if not distribution:
        return base_length, {
            "model": "fixed",
            "mode": "fixed",
            "reference_length": base_length,
        }

    mode_name, mode = _sample_weighted_length_mode(rng, distribution)
    reference_length = _line_chord_length(bounds, center, angle)
    minimum = float(mode["min_chord_multiplier"]) * reference_length
    maximum = float(mode["max_chord_multiplier"]) * reference_length
    sampled_length = rng.uniform(minimum, maximum)
    return sampled_length, {
        "model": "weighted_capture_chord",
        "mode": mode_name,
        "reference": str(distribution.get("reference", "first_capture_chord")),
        "reference_length": round(reference_length, 6),
        "probability": float(mode["probability"]),
        "min_chord_multiplier": float(mode["min_chord_multiplier"]),
        "max_chord_multiplier": float(mode["max_chord_multiplier"]),
    }


def _sample_weighted_length_mode(rng: random.Random, distribution: Mapping[str, Any]) -> Tuple[str, Mapping[str, Any]]:
    modes = [
        (name, distribution[name])
        for name in ("across_view", "one_end_visible", "contained")
        if name in distribution
    ]
    total = sum(float(mode["probability"]) for _name, mode in modes)
    threshold = rng.uniform(0.0, total)
    running = 0.0
    for name, mode in modes:
        running += float(mode["probability"])
        if threshold <= running:
            return name, mode
    return modes[-1]


def _line_chord_length(bounds: Mapping[str, float], center: Tuple[float, float], angle: float) -> float:
    direction = (math.cos(angle), math.sin(angle))
    return _distance_to_bounds(bounds, center, direction) + _distance_to_bounds(
        bounds, center, (-direction[0], -direction[1])
    )


def _distance_to_bounds(
    bounds: Mapping[str, float],
    point: Tuple[float, float],
    direction: Tuple[float, float],
) -> float:
    distances = []
    if direction[0] > 0.0:
        distances.append((bounds["x_max"] - point[0]) / direction[0])
    elif direction[0] < 0.0:
        distances.append((bounds["x_min"] - point[0]) / direction[0])
    if direction[1] > 0.0:
        distances.append((bounds["y_max"] - point[1]) / direction[1])
    elif direction[1] < 0.0:
        distances.append((bounds["y_min"] - point[1]) / direction[1])
    positive = [distance for distance in distances if distance >= 0.0]
    return min(positive) if positive else 0.0


def _random_walk_centerline(
    rng: random.Random,
    center: Tuple[float, float],
    initial_angle: float,
    step: float,
    segments: int,
    roughness: float,
    control_step: float,
    jaggedness: Mapping[str, float],
) -> List[Tuple[float, float]]:
    start_angle = initial_angle + math.pi
    target_length = step * float(segments - 1)
    half_length = target_length / 2.0
    forward = _walk_half(rng, center, start_angle, half_length, control_step, roughness, jaggedness)
    backward = list(reversed(forward[1:]))
    forward_half = _walk_half(rng, center, initial_angle, half_length, control_step, roughness, jaggedness)
    control_points = backward + forward_half
    return _resample_polyline(control_points, segments)


def _random_walk_centerline_across_bounds(
    rng: random.Random,
    center: Tuple[float, float],
    initial_angle: float,
    skeleton_step: float,
    roughness: float,
    control_step: float,
    jaggedness: Mapping[str, float],
    bounds: Mapping[str, float],
    margin: float,
) -> Tuple[List[Tuple[float, float]], Dict[str, Any]]:
    width = bounds["x_max"] - bounds["x_min"]
    height = bounds["y_max"] - bounds["y_min"]
    maximum_walk_distance = math.hypot(width, height) * 3.0 + margin * 2.0
    start_half, start_meta = _walk_half_until_outside_bounds(
        rng,
        center,
        initial_angle + math.pi,
        control_step,
        roughness,
        jaggedness,
        bounds,
        margin,
        maximum_walk_distance,
    )
    end_half, end_meta = _walk_half_until_outside_bounds(
        rng,
        center,
        initial_angle,
        control_step,
        roughness,
        jaggedness,
        bounds,
        margin,
        maximum_walk_distance,
    )
    control_points = list(reversed(start_half[1:])) + end_half
    target_count = int(math.ceil(_polyline_length_2d(control_points) / skeleton_step)) + 1
    resampled = _resample_polyline(control_points, max(2, target_count))
    return resampled, {
        "enabled": True,
        "model": "bidirectional_random_walk_until_surface_crossing",
        "margin": round(margin, 6),
        "maximum_walk_distance": round(maximum_walk_distance, 6),
        "start_half": start_meta,
        "end_half": end_meta,
    }


def _walk_half_until_outside_bounds(
    rng: random.Random,
    start: Tuple[float, float],
    initial_angle: float,
    mean_step: float,
    roughness: float,
    jaggedness: Mapping[str, float],
    bounds: Mapping[str, float],
    margin: float,
    maximum_walk_distance: float,
) -> Tuple[List[Tuple[float, float]], Dict[str, Any]]:
    expanded_bounds = {
        "x_min": bounds["x_min"] - margin,
        "x_max": bounds["x_max"] + margin,
        "y_min": bounds["y_min"] - margin,
        "y_max": bounds["y_max"] + margin,
    }
    points = [start]
    angle = initial_angle
    preferred = initial_angle
    attempts_per_step = 40
    walked_distance = 0.0
    distance_to_next_micro_kink = _sample_kink_interval(
        rng,
        jaggedness["micro_min_interval"],
        jaggedness["micro_max_interval"],
    )
    distance_to_next_minor_kink = _sample_kink_interval(
        rng,
        jaggedness["minor_min_interval"],
        jaggedness["minor_max_interval"],
    )
    distance_to_next_major_kink = _sample_kink_interval(
        rng,
        jaggedness["major_min_interval"],
        jaggedness["major_max_interval"],
    )
    crossed = False
    while walked_distance < maximum_walk_distance:
        step = _sample_walk_step(rng, mean_step)
        accepted = None
        accepted_angle = angle
        force_major_kink = distance_to_next_major_kink <= 0.0
        force_minor_kink = distance_to_next_minor_kink <= 0.0 and not force_major_kink
        force_micro_kink = (
            distance_to_next_micro_kink <= 0.0 and not force_major_kink and not force_minor_kink
        )
        kink_kind = (
            "major"
            if force_major_kink
            else "minor"
            if force_minor_kink
            else "micro"
            if force_micro_kink
            else None
        )
        for _attempt in range(attempts_per_step):
            candidate_angle = _next_heading(
                rng,
                angle,
                preferred,
                roughness,
                jaggedness,
                kink_kind if _attempt == 0 else None,
            )
            candidate = (
                points[-1][0] + math.cos(candidate_angle) * step,
                points[-1][1] + math.sin(candidate_angle) * step,
            )
            if _progresses_forward(points[-1], candidate, preferred) and not _would_self_intersect(points, candidate):
                accepted = candidate
                accepted_angle = candidate_angle
                break
        if accepted is None:
            accepted_angle = _nudge_toward(angle, preferred, math.radians(12.0))
            accepted = (
                points[-1][0] + math.cos(accepted_angle) * step,
                points[-1][1] + math.sin(accepted_angle) * step,
            )
        points.append(accepted)
        angle = accepted_angle
        walked_distance += step
        if not _point_inside_bounds(accepted, expanded_bounds):
            crossed = True
            break
        if force_major_kink:
            distance_to_next_major_kink = _sample_kink_interval(
                rng,
                jaggedness["major_min_interval"],
                jaggedness["major_max_interval"],
            )
        else:
            distance_to_next_major_kink -= step
        if force_minor_kink:
            distance_to_next_minor_kink = _sample_kink_interval(
                rng,
                jaggedness["minor_min_interval"],
                jaggedness["minor_max_interval"],
            )
        else:
            distance_to_next_minor_kink -= step
        if force_micro_kink:
            distance_to_next_micro_kink = _sample_kink_interval(
                rng,
                jaggedness["micro_min_interval"],
                jaggedness["micro_max_interval"],
            )
        else:
            distance_to_next_micro_kink -= step
    if not crossed:
        exit_distance = _extension_distance_to_exit(points[-1], (math.cos(preferred), math.sin(preferred)), bounds, margin)
        points.append(
            (
                points[-1][0] + math.cos(preferred) * exit_distance,
                points[-1][1] + math.sin(preferred) * exit_distance,
            )
        )
        walked_distance += exit_distance
    return points, {
        "crossed_expanded_bounds": crossed,
        "walked_distance": round(walked_distance, 6),
        "control_point_count": len(points),
        "terminal_point": [round(points[-1][0], 6), round(points[-1][1], 6), 0.0],
    }


def _walk_half(
    rng: random.Random,
    start: Tuple[float, float],
    initial_angle: float,
    target_distance: float,
    mean_step: float,
    roughness: float,
    jaggedness: Mapping[str, float],
) -> List[Tuple[float, float]]:
    points = [start]
    angle = initial_angle
    preferred = initial_angle
    attempts_per_step = 40
    walked_distance = 0.0
    distance_to_next_micro_kink = _sample_kink_interval(
        rng,
        jaggedness["micro_min_interval"],
        jaggedness["micro_max_interval"],
    )
    distance_to_next_minor_kink = _sample_kink_interval(
        rng,
        jaggedness["minor_min_interval"],
        jaggedness["minor_max_interval"],
    )
    distance_to_next_major_kink = _sample_kink_interval(
        rng,
        jaggedness["major_min_interval"],
        jaggedness["major_max_interval"],
    )
    while walked_distance < target_distance:
        step = min(target_distance - walked_distance, _sample_walk_step(rng, mean_step))
        accepted = None
        accepted_angle = angle
        force_major_kink = distance_to_next_major_kink <= 0.0
        force_minor_kink = distance_to_next_minor_kink <= 0.0 and not force_major_kink
        force_micro_kink = (
            distance_to_next_micro_kink <= 0.0 and not force_major_kink and not force_minor_kink
        )
        kink_kind = (
            "major"
            if force_major_kink
            else "minor"
            if force_minor_kink
            else "micro"
            if force_micro_kink
            else None
        )
        for _attempt in range(attempts_per_step):
            candidate_angle = _next_heading(
                rng,
                angle,
                preferred,
                roughness,
                jaggedness,
                kink_kind if _attempt == 0 else None,
            )
            candidate = (
                points[-1][0] + math.cos(candidate_angle) * step,
                points[-1][1] + math.sin(candidate_angle) * step,
            )
            if _progresses_forward(points[-1], candidate, preferred) and not _would_self_intersect(points, candidate):
                accepted = candidate
                accepted_angle = candidate_angle
                break
        if accepted is None:
            accepted_angle = _nudge_toward(angle, preferred, math.radians(12.0))
            accepted = (
                points[-1][0] + math.cos(accepted_angle) * step,
                points[-1][1] + math.sin(accepted_angle) * step,
            )
        points.append(accepted)
        angle = accepted_angle
        walked_distance += step
        if force_major_kink:
            distance_to_next_major_kink = _sample_kink_interval(
                rng,
                jaggedness["major_min_interval"],
                jaggedness["major_max_interval"],
            )
        else:
            distance_to_next_major_kink -= step
        if force_minor_kink:
            distance_to_next_minor_kink = _sample_kink_interval(
                rng,
                jaggedness["minor_min_interval"],
                jaggedness["minor_max_interval"],
            )
        else:
            distance_to_next_minor_kink -= step
        if force_micro_kink:
            distance_to_next_micro_kink = _sample_kink_interval(
                rng,
                jaggedness["micro_min_interval"],
                jaggedness["micro_max_interval"],
            )
        else:
            distance_to_next_micro_kink -= step
    return points


def _sample_walk_step(rng: random.Random, mean_step: float) -> float:
    draw = rng.random()
    if draw < 0.25:
        multiplier = rng.uniform(0.12, 0.45)
    elif draw > 0.88:
        multiplier = rng.uniform(1.8, 3.0)
    else:
        multiplier = rng.triangular(0.45, 1.8, 0.8)
    return max(mean_step * multiplier, 0.05)


def _polyline_length_2d(points: List[Tuple[float, float]]) -> float:
    return sum(math.hypot(right[0] - left[0], right[1] - left[1]) for left, right in zip(points, points[1:]))


def _extend_walk_to_surface_bounds(
    points: List[Tuple[float, float]],
    bounds: Mapping[str, float],
    margin: float,
) -> Tuple[List[Tuple[float, float]], Dict[str, Any]]:
    if len(points) < 2:
        return points, {"enabled": False, "reason": "too_few_points"}

    start_direction = _normalize_2d((points[0][0] - points[1][0], points[0][1] - points[1][1]))
    end_direction = _normalize_2d((points[-1][0] - points[-2][0], points[-1][1] - points[-2][1]))
    start_distance = _extension_distance_to_exit(points[0], start_direction, bounds, margin)
    end_distance = _extension_distance_to_exit(points[-1], end_direction, bounds, margin)
    extended = points[:]
    start_added = start_distance > 0.0
    end_added = end_distance > 0.0
    if start_added:
        extended.insert(
            0,
            (
                points[0][0] + start_direction[0] * start_distance,
                points[0][1] + start_direction[1] * start_distance,
            ),
        )
    if end_added:
        extended.append(
            (
                points[-1][0] + end_direction[0] * end_distance,
                points[-1][1] + end_direction[1] * end_distance,
            )
        )
    return extended, {
        "enabled": True,
        "model": "endpoint_tangent_to_surface_bounds",
        "margin": round(margin, 6),
        "start_added": start_added,
        "end_added": end_added,
        "start_extension_length": round(start_distance, 6),
        "end_extension_length": round(end_distance, 6),
    }


def _extension_distance_to_exit(
    point: Tuple[float, float],
    direction: Tuple[float, float],
    bounds: Mapping[str, float],
    margin: float,
) -> float:
    if not _point_inside_bounds(point, bounds):
        return margin
    return _distance_to_bounds(bounds, point, direction) + margin


def _point_inside_bounds(point: Tuple[float, float], bounds: Mapping[str, float]) -> bool:
    return (
        bounds["x_min"] <= point[0] <= bounds["x_max"]
        and bounds["y_min"] <= point[1] <= bounds["y_max"]
    )


def _normalize_2d(vector: Tuple[float, float]) -> Tuple[float, float]:
    length = math.sqrt(vector[0] * vector[0] + vector[1] * vector[1])
    if length == 0.0:
        return (1.0, 0.0)
    return (vector[0] / length, vector[1] / length)


def _resample_polyline(points: List[Tuple[float, float]], count: int) -> List[Tuple[float, float]]:
    if len(points) < 2 or count <= 1:
        return points[:]
    cumulative = [0.0]
    for left, right in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.hypot(right[0] - left[0], right[1] - left[1]))
    total = cumulative[-1]
    if total == 0.0:
        return [points[0] for _ in range(count)]
    result = []
    segment_index = 0
    for index in range(count):
        target = total * float(index) / float(count - 1)
        while segment_index < len(cumulative) - 2 and cumulative[segment_index + 1] < target:
            segment_index += 1
        left_distance = cumulative[segment_index]
        right_distance = cumulative[segment_index + 1]
        if right_distance == left_distance:
            fraction = 0.0
        else:
            fraction = (target - left_distance) / (right_distance - left_distance)
        left = points[segment_index]
        right = points[segment_index + 1]
        result.append(
            (
                left[0] + (right[0] - left[0]) * fraction,
                left[1] + (right[1] - left[1]) * fraction,
            )
        )
    return result


def _split_displacement_opening_profile(
    defect: Mapping[str, Any],
    rng: random.Random,
    seed: int,
    segments: int,
) -> Tuple[List[float], List[float], List[float], Dict[str, Any]]:
    opening = defect.get("opening_model", {})
    model_type = str(opening.get("type", "hinged"))
    min_opening = float(opening.get("min_opening", 0.1))
    max_opening = rng.uniform(float(opening.get("max_opening_min", 0.8)), float(opening.get("max_opening_max", 10.0)))
    residual_opening = rng.uniform(min_opening, min(max_opening, float(opening.get("contact_opening_max", 0.35))))
    exponent = rng.uniform(float(opening.get("profile_exponent_min", 0.85)), float(opening.get("profile_exponent_max", 1.7)))
    contact_end = rng.choice(["start", "end"])
    moving_side = rng.choice(["left", "right"])
    vertical_offset_max = float(opening.get("vertical_offset_max", 0.0))
    vertical_offset = rng.uniform(-vertical_offset_max, vertical_offset_max) if vertical_offset_max else 0.0
    edge_jitter_amplitude = float(opening.get("edge_jitter_amplitude", 0.08))
    jitter_rng = random.Random(_derive_seed(seed, "split-opening-jitter"))
    jitter_field = _fbm_width_field(jitter_rng, segments, 2, 28.0)

    widths: List[float] = []
    for index in range(segments):
        fraction = float(index) / float(segments - 1) if segments > 1 else 0.0
        if contact_end == "end":
            fraction = 1.0 - fraction
        profile = residual_opening + (max_opening - residual_opening) * (fraction**exponent)
        jitter = 1.0 + edge_jitter_amplitude * jitter_field[index]
        widths.append(round(max(min_opening, profile * jitter), 6))

    if model_type != "hinged":
        model_type = "hinged"
    if moving_side == "left":
        left_opening = widths[:]
        right_opening = [0.0 for _ in widths]
    else:
        left_opening = [0.0 for _ in widths]
        right_opening = widths[:]
    return widths, left_opening, right_opening, {
        "type": model_type,
        "physical_model": "surface_split_displacement",
        "contact_end": contact_end,
        "moving_side": moving_side,
        "min_opening": round(min_opening, 6),
        "residual_contact_opening": round(residual_opening, 6),
        "max_opening": round(max_opening, 6),
        "profile_exponent": round(exponent, 6),
        "edge_jitter_amplitude": edge_jitter_amplitude,
        "vertical_offset": round(vertical_offset, 6),
    }


def _rigid_split_opening_profile(
    defect: Mapping[str, Any],
    rng: random.Random,
    segments: int,
) -> Tuple[List[float], List[float], List[float], Dict[str, Any]]:
    opening = defect.get("opening_model", {})
    model_type = str(opening.get("type", "rigid_offset"))
    min_opening = float(opening.get("min_opening", 0.1))
    max_opening = rng.uniform(float(opening.get("max_opening_min", 0.8)), float(opening.get("max_opening_max", 10.0)))
    hinge_probability = float(opening.get("hinge_probability", 0.0))
    vertical_offset_max = float(opening.get("vertical_offset_max", 0.0))
    vertical_offset = rng.uniform(-vertical_offset_max, vertical_offset_max) if vertical_offset_max else 0.0
    max_width = round(max(min_opening, max_opening), 6)
    use_hinge = rng.random() < hinge_probability
    if use_hinge:
        contact_end = rng.choice(["start", "end"])
        exponent = rng.uniform(float(opening.get("profile_exponent_min", 1.0)), float(opening.get("profile_exponent_max", 1.0)))
        widths = []
        for index in range(segments):
            fraction = float(index) / float(segments - 1) if segments > 1 else 0.0
            if contact_end == "end":
                fraction = 1.0 - fraction
            widths.append(round(max_width * (fraction**exponent), 6))
        opening_metadata = {
            "type": model_type,
            "physical_model": "surface_split_hinged_symmetric",
            "moving_side": "both",
            "contact_end": contact_end,
            "min_opening": round(min_opening, 6),
            "closed_end_width": 0.0,
            "max_opening": max_width,
            "rigid_offset": max_width,
            "half_offset": round(max_width / 2.0, 6),
            "profile_exponent": round(exponent, 6),
            "vertical_offset": round(vertical_offset, 6),
            "width_model": "hinged_power_profile_along_centerline",
            "hinge_probability": hinge_probability,
            "in_view_width_capped_by_max_opening": True,
        }
    else:
        widths = [max_width for _ in range(segments)]
        opening_metadata = {
            "type": model_type,
            "physical_model": "surface_split_rigid_body_offset",
            "moving_side": "both",
            "min_opening": round(min_opening, 6),
            "rigid_offset": max_width,
            "half_offset": round(max_width / 2.0, 6),
            "max_opening": max_width,
            "vertical_offset": round(vertical_offset, 6),
            "width_model": "constant_along_centerline",
            "hinge_probability": hinge_probability,
        }
    half_widths = [round(width / 2.0, 6) for width in widths]
    left_opening = half_widths[:]
    right_opening = half_widths[:]
    return widths, left_opening, right_opening, opening_metadata


def _fbm_width_field(
    rng: random.Random,
    count: int,
    octaves: int,
    base_frequency: float,
) -> List[float]:
    if count <= 1:
        return [0.0 for _ in range(count)]
    values = []
    total_amplitude = 0.0
    octave_specs = []
    for octave in range(octaves):
        frequency = base_frequency * (2.0**octave)
        amplitude = 0.5**octave
        grid_count = max(2, int(math.ceil(frequency)) + 2)
        grid = [rng.uniform(-1.0, 1.0) for _ in range(grid_count)]
        octave_specs.append((frequency, amplitude, grid))
        total_amplitude += amplitude

    for index in range(count):
        position = float(index) / float(count - 1)
        value = 0.0
        for frequency, amplitude, grid in octave_specs:
            value += amplitude * _value_noise_1d(grid, position * frequency)
        values.append(value / total_amplitude if total_amplitude else 0.0)
    return values


def _stabilize_width_profile(
    points: List[List[float]],
    widths: List[float],
    nominal_width: float,
) -> Tuple[List[float], Dict[str, Any]]:
    stabilized = widths[:]
    minimum_width = max(nominal_width * 0.16, 0.05)
    passes = 0
    reductions = 0
    remaining_intersections = 0
    for passes in range(1, 13):
        intersections = _crack_boundary_intersections(points, stabilized, limit=32)
        if not intersections:
            passes -= 1
            break
        remaining_intersections = len(intersections)
        touched = set()
        for left_edge, right_edge in intersections:
            for center_index in (
                _boundary_edge_center_index(left_edge, len(points)),
                _boundary_edge_center_index(right_edge, len(points)),
            ):
                for index in range(max(0, center_index - 5), min(len(stabilized), center_index + 6)):
                    touched.add(index)
        if not touched:
            break
        for index in touched:
            new_width = max(minimum_width, stabilized[index] * 0.72)
            if new_width < stabilized[index]:
                stabilized[index] = new_width
                reductions += 1
        remaining_intersections = len(_crack_boundary_intersections(points, stabilized, limit=32))
        if remaining_intersections == 0:
            break
    return [round(width, 6) for width in stabilized], {
        "enabled": True,
        "passes": passes,
        "local_reductions": reductions,
        "remaining_boundary_intersections": remaining_intersections,
        "minimum_width": round(minimum_width, 6),
    }


def _filter_intersecting_width_whiskers(
    points: List[List[float]],
    widths: List[float],
    nominal_width: float,
) -> Tuple[List[List[float]], List[float], Dict[str, Any]]:
    if len(points) <= 2:
        return points[:], [round(width, 6) for width in widths], {
            "enabled": True,
            "model": "width_whisker_intersection_rejection",
            "generated_point_count": len(points),
            "accepted_point_count": len(points),
            "rejected_point_count": 0,
            "rejected_indices": [],
            "remaining_boundary_intersections": 0,
            "minimum_width": round(max(nominal_width * 0.16, 0.05), 6),
        }

    accepted_points = [points[0]]
    accepted_widths = [float(widths[0])]
    rejected_indices: List[int] = []
    rejected_by_reason = {"whisker_intersection": 0, "boundary_intersection": 0, "global_boundary_intersection": 0}
    minimum_width = max(nominal_width * 0.16, 0.05)

    for index in range(1, len(points)):
        candidate_points = accepted_points + [points[index]]
        candidate_widths = accepted_widths + [float(widths[index])]
        reason = _candidate_width_whisker_rejection_reason(candidate_points, candidate_widths)
        if reason is None or len(accepted_points) < 2:
            accepted_points = candidate_points
            accepted_widths = candidate_widths
            continue
        rejected_indices.append(index)
        rejected_by_reason[reason] += 1

    if len(accepted_points) < 2:
        accepted_points = [points[0], points[-1]]
        accepted_widths = [float(widths[0]), float(widths[-1])]
        rejected_indices = list(range(1, len(points) - 1))

    accepted_points, accepted_widths, cleanup = _reject_remaining_boundary_intersections(
        accepted_points,
        accepted_widths,
    )
    rejected_by_reason["global_boundary_intersection"] = cleanup["rejected_point_count"]
    remaining_intersections = len(
        _crack_boundary_intersections(accepted_points, [round(width, 6) for width in accepted_widths], limit=32)
    )
    total_rejected_count = len(rejected_indices) + cleanup["rejected_point_count"]
    return [point[:] for point in accepted_points], [round(width, 6) for width in accepted_widths], {
        "enabled": True,
        "model": "width_whisker_intersection_rejection",
        "generated_point_count": len(points),
        "accepted_point_count": len(accepted_points),
        "rejected_point_count": total_rejected_count,
        "local_rejected_point_count": len(rejected_indices),
        "rejected_indices": rejected_indices[:256],
        "rejected_indices_truncated": len(rejected_indices) > 256,
        "rejected_by_reason": rejected_by_reason,
        "global_cleanup_passes": cleanup["passes"],
        "remaining_boundary_intersections": remaining_intersections,
        "minimum_width": round(minimum_width, 6),
    }


def _reject_remaining_boundary_intersections(
    points: List[List[float]],
    widths: List[float],
) -> Tuple[List[List[float]], List[float], Dict[str, int]]:
    cleaned_points = points[:]
    cleaned_widths = widths[:]
    rejected_count = 0
    passes = 0
    for passes in range(1, 9):
        intersections = _crack_boundary_intersections(cleaned_points, cleaned_widths, limit=64)
        if not intersections:
            passes -= 1
            break
        reject_indices = set()
        for left_edge, right_edge in intersections:
            for boundary_edge in (left_edge, right_edge):
                center_index = _boundary_edge_center_index(boundary_edge, len(cleaned_points))
                if 0 < center_index < len(cleaned_points) - 1:
                    reject_indices.add(center_index)
        if not reject_indices:
            break
        cleaned_points = [point for index, point in enumerate(cleaned_points) if index not in reject_indices]
        cleaned_widths = [width for index, width in enumerate(cleaned_widths) if index not in reject_indices]
        rejected_count += len(reject_indices)
        if len(cleaned_points) < 2:
            return points[:2], widths[:2], {"passes": passes, "rejected_point_count": rejected_count}
    return cleaned_points, cleaned_widths, {"passes": passes, "rejected_point_count": rejected_count}


def _candidate_width_whisker_rejection_reason(
    points: List[List[float]],
    widths: List[float],
) -> Optional[str]:
    if len(points) < 3:
        return None
    previous_index = len(points) - 2
    candidate_index = len(points) - 1
    previous_left, previous_right = _width_whisker_2d(points, previous_index, widths[previous_index])
    candidate_left, candidate_right = _width_whisker_2d(points, candidate_index, widths[candidate_index])
    previous_whisker = (
        previous_left,
        previous_right,
    )
    candidate_whisker = (
        candidate_left,
        candidate_right,
    )
    if _segments_intersect(previous_whisker[0], previous_whisker[1], candidate_whisker[0], candidate_whisker[1]):
        return "whisker_intersection"
    previous_left_edge = _width_whisker_2d(points, previous_index - 1, widths[previous_index - 1])[0]
    previous_right_edge = _width_whisker_2d(points, previous_index - 1, widths[previous_index - 1])[1]
    local_segments = [
        (previous_left_edge, previous_left),
        (previous_left, candidate_left),
        (candidate_left, candidate_right),
        (candidate_right, previous_right),
        (previous_right, previous_right_edge),
        (previous_right_edge, previous_left_edge),
    ]
    for left_index, left_segment in enumerate(local_segments):
        for right_index in range(left_index + 1, len(local_segments)):
            if abs(left_index - right_index) <= 1 or (left_index == 0 and right_index == len(local_segments) - 1):
                continue
            right_segment = local_segments[right_index]
            if _segments_intersect(left_segment[0], left_segment[1], right_segment[0], right_segment[1]):
                return "boundary_intersection"
    return None


def _width_whisker_2d(
    points: List[List[float]],
    index: int,
    width: float,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    nx, ny = _tangent_normal_2d(points, index)
    half_width = max(float(width), 0.001) / 2.0
    point = points[index]
    return (
        (point[0] + nx * half_width, point[1] + ny * half_width),
        (point[0] - nx * half_width, point[1] - ny * half_width),
    )


def _stabilize_split_opening_profile(
    points: List[List[float]],
    openings: List[float],
    moving_side: str,
    minimum_opening: float,
) -> Tuple[List[float], Dict[str, Any]]:
    stabilized = openings[:]
    sign = 1.0 if moving_side == "left" else -1.0
    passes = 0
    reductions = 0
    remaining_intersections = 0
    minimum = max(float(minimum_opening), 0.05)
    for passes in range(1, 17):
        intersections = _offset_polyline_intersections(points, stabilized, sign, limit=32)
        if not intersections:
            passes -= 1
            break
        remaining_intersections = len(intersections)
        touched = set()
        for left_edge, right_edge in intersections:
            for center_index in (left_edge, right_edge):
                for index in range(max(0, center_index - 8), min(len(stabilized), center_index + 10)):
                    touched.add(index)
        if not touched:
            break
        for index in touched:
            new_opening = max(minimum, stabilized[index] * 0.65)
            if new_opening < stabilized[index]:
                stabilized[index] = new_opening
                reductions += 1
        remaining_intersections = len(_offset_polyline_intersections(points, stabilized, sign, limit=32))
        if remaining_intersections == 0:
            break
    return [round(width, 6) for width in stabilized], {
        "enabled": True,
        "model": "one_sided_offset_self_intersection_reduction",
        "moving_side": moving_side,
        "passes": passes,
        "local_reductions": reductions,
        "remaining_offset_intersections": remaining_intersections,
        "minimum_opening": round(minimum, 6),
    }


def _damp_inner_turn_openings(
    points: List[List[float]],
    openings: List[float],
    moving_side: str,
    minimum_opening: float,
) -> Tuple[List[float], Dict[str, Any]]:
    damped = openings[:]
    minimum = max(float(minimum_opening), 0.05)
    moving_sign = 1.0 if moving_side == "left" else -1.0
    affected = 0
    strongest_turn_degrees = 0.0
    for index in range(1, len(points) - 1):
        ax = points[index][0] - points[index - 1][0]
        ay = points[index][1] - points[index - 1][1]
        bx = points[index + 1][0] - points[index][0]
        by = points[index + 1][1] - points[index][1]
        a_length = math.sqrt(ax * ax + ay * ay) or 1.0
        b_length = math.sqrt(bx * bx + by * by) or 1.0
        cross = (ax / a_length) * (by / b_length) - (ay / a_length) * (bx / b_length)
        dot = max(-1.0, min(1.0, (ax / a_length) * (bx / b_length) + (ay / a_length) * (by / b_length)))
        turn = math.atan2(cross, dot)
        if turn * moving_sign <= 0.0:
            continue
        turn_degrees = abs(math.degrees(turn))
        if turn_degrees < 8.0:
            continue
        strongest_turn_degrees = max(strongest_turn_degrees, turn_degrees)
        severity = min(1.0, (turn_degrees - 8.0) / 42.0)
        center_factor = 1.0 - 0.58 * severity
        radius = 5 + int(round(10.0 * severity))
        for local_index in range(max(0, index - radius), min(len(damped), index + radius + 1)):
            distance = abs(local_index - index) / float(radius + 1)
            blend = 0.5 * (1.0 + math.cos(math.pi * min(1.0, distance)))
            factor = 1.0 - (1.0 - center_factor) * blend
            new_opening = max(minimum, damped[local_index] * factor)
            if new_opening < damped[local_index]:
                damped[local_index] = new_opening
                affected += 1
    return [round(width, 6) for width in damped], {
        "enabled": True,
        "model": "inner_turn_opening_damping",
        "moving_side": moving_side,
        "affected_samples": affected,
        "turn_threshold_degrees": 8.0,
        "strongest_inner_turn_degrees": round(strongest_turn_degrees, 6),
        "minimum_opening": round(minimum, 6),
    }


def _smooth_opening_profile(openings: List[float], minimum_opening: float) -> Tuple[List[float], Dict[str, Any]]:
    minimum = max(float(minimum_opening), 0.05)
    smoothed = openings[:]
    passes = 3
    for _pass in range(passes):
        next_values = smoothed[:]
        for index in range(1, len(smoothed) - 1):
            next_values[index] = max(
                minimum,
                0.25 * smoothed[index - 1] + 0.5 * smoothed[index] + 0.25 * smoothed[index + 1],
            )
        smoothed = next_values
    max_change = max((abs(left - right) for left, right in zip(openings, smoothed)), default=0.0)
    return [round(width, 6) for width in smoothed], {
        "enabled": True,
        "model": "three_pass_binomial_profile_smoothing",
        "passes": passes,
        "minimum_opening": round(minimum, 6),
        "max_adjustment": round(max_change, 6),
    }


def _offset_polyline_intersections(
    points: List[List[float]],
    offsets: List[float],
    sign: float,
    limit: int,
) -> List[Tuple[int, int]]:
    offset_points = _offset_polyline_2d(points, offsets, sign)
    count = len(offset_points)
    boxes = []
    for index in range(count - 1):
        left = offset_points[index]
        right = offset_points[index + 1]
        boxes.append(
            (
                min(left[0], right[0]),
                max(left[0], right[0]),
                min(left[1], right[1]),
                max(left[1], right[1]),
                index,
            )
        )
    boxes_by_min_x = sorted(boxes)
    intersections = []
    for box_position, left_box in enumerate(boxes_by_min_x):
        left_min_x, left_max_x, left_min_y, left_max_y, left_index = left_box
        left_a = offset_points[left_index]
        left_b = offset_points[left_index + 1]
        for right_box in boxes_by_min_x[box_position + 1 :]:
            right_min_x, right_max_x, right_min_y, right_max_y, right_index = right_box
            if right_min_x > left_max_x:
                break
            if right_max_x < left_min_x or right_min_y > left_max_y or right_max_y < left_min_y:
                continue
            if abs(left_index - right_index) <= 1:
                continue
            right_a = offset_points[right_index]
            right_b = offset_points[right_index + 1]
            if _segments_intersect(left_a, left_b, right_a, right_b):
                intersections.append((left_index, right_index))
                if len(intersections) >= limit:
                    return intersections
    return intersections


def _offset_polyline_2d(
    points: List[List[float]],
    offsets: List[float],
    sign: float,
) -> List[Tuple[float, float]]:
    edge = []
    for index, point in enumerate(points):
        nx, ny = _tangent_normal_2d(points, index)
        offset = max(float(offsets[index]), 0.0)
        edge.append((point[0] + sign * nx * offset, point[1] + sign * ny * offset))
    return edge


def _crack_boundary_intersections(
    points: List[List[float]],
    widths: List[float],
    limit: int,
) -> List[Tuple[int, int]]:
    boundary = _crack_boundary_2d(points, widths)
    count = len(boundary)
    boxes = []
    for index in range(count):
        left = boundary[index]
        right = boundary[(index + 1) % count]
        boxes.append(
            (
                min(left[0], right[0]),
                max(left[0], right[0]),
                min(left[1], right[1]),
                max(left[1], right[1]),
                index,
            )
        )
    boxes_by_min_x = sorted(boxes)
    intersections = []
    for box_position, left_box in enumerate(boxes_by_min_x):
        left_min_x, left_max_x, left_min_y, left_max_y, left_index = left_box
        left_a = boundary[left_index]
        left_b = boundary[(left_index + 1) % count]
        for right_box in boxes_by_min_x[box_position + 1 :]:
            right_min_x, right_max_x, right_min_y, right_max_y, right_index = right_box
            if right_min_x > left_max_x:
                break
            if right_max_x < left_min_x or right_min_y > left_max_y or right_max_y < left_min_y:
                continue
            if abs(left_index - right_index) <= 1 or (left_index == 0 and right_index == count - 1):
                continue
            right_a = boundary[right_index]
            right_b = boundary[(right_index + 1) % count]
            if _segments_intersect(left_a, left_b, right_a, right_b):
                intersections.append((left_index, right_index))
                if len(intersections) >= limit:
                    return intersections
    return intersections


def _crack_boundary_2d(points: List[List[float]], widths: List[float]) -> List[Tuple[float, float]]:
    left_edge = []
    right_edge = []
    for index, point in enumerate(points):
        nx, ny = _tangent_normal_2d(points, index)
        half_width = max(float(widths[index]), 0.001) / 2.0
        left_edge.append((point[0] + nx * half_width, point[1] + ny * half_width))
        right_edge.append((point[0] - nx * half_width, point[1] - ny * half_width))
    return left_edge + list(reversed(right_edge))


def _tangent_normal_2d(points: List[List[float]], index: int) -> Tuple[float, float]:
    if index == 0:
        dx = points[1][0] - points[0][0]
        dy = points[1][1] - points[0][1]
    elif index == len(points) - 1:
        dx = points[-1][0] - points[-2][0]
        dy = points[-1][1] - points[-2][1]
    else:
        dx = points[index + 1][0] - points[index - 1][0]
        dy = points[index + 1][1] - points[index - 1][1]
    length = math.sqrt(dx * dx + dy * dy) or 1.0
    return (-dy / length, dx / length)


def _boundary_edge_center_index(boundary_edge_index: int, point_count: int) -> int:
    if boundary_edge_index < point_count:
        return min(boundary_edge_index, point_count - 1)
    reversed_right_index = boundary_edge_index - point_count
    return max(0, point_count - 1 - reversed_right_index)


def _value_noise_1d(grid: List[float], x: float) -> float:
    left_index = int(math.floor(x)) % len(grid)
    right_index = (left_index + 1) % len(grid)
    fraction = x - math.floor(x)
    fraction = fraction * fraction * (3.0 - 2.0 * fraction)
    return grid[left_index] + (grid[right_index] - grid[left_index]) * fraction


def _sample_kink_interval(rng: random.Random, minimum: float, maximum: float) -> float:
    return rng.uniform(minimum, maximum)


def _path_jaggedness(defect: Mapping[str, Any]) -> Dict[str, float]:
    config = defect.get("path_jaggedness", {})
    return {
        "heading_drift_degrees": float(config.get("heading_drift_degrees", 8.0)),
        "micro_min_interval": float(config.get("micro_min_interval", 0.35)),
        "micro_max_interval": float(config.get("micro_max_interval", 1.6)),
        "micro_degrees": float(config.get("micro_degrees", 8.0)),
        "micro_sigma_degrees": float(config.get("micro_sigma_degrees", 2.5)),
        "minor_min_interval": float(config.get("minor_min_interval", 3.5)),
        "minor_max_interval": float(config.get("minor_max_interval", 18.0)),
        "minor_degrees": float(config.get("minor_degrees", 11.0)),
        "minor_sigma_degrees": float(config.get("minor_sigma_degrees", 3.0)),
        "major_min_interval": float(config.get("major_min_interval", 18.0)),
        "major_max_interval": float(config.get("major_max_interval", 110.0)),
        "major_degrees": float(config.get("major_degrees", 36.0)),
        "major_sigma_degrees": float(config.get("major_sigma_degrees", 9.0)),
        "max_turn_degrees": float(config.get("max_turn_degrees", 55.0)),
        "preferred_nudge_degrees": float(config.get("preferred_nudge_degrees", 3.0)),
    }


def _next_heading(
    rng: random.Random,
    current: float,
    preferred: float,
    roughness: float,
    jaggedness: Mapping[str, float],
    kink_kind: Optional[str] = None,
) -> float:
    drift_sigma = math.radians(jaggedness["heading_drift_degrees"] + min(10.0, roughness * 2.0))
    if kink_kind == "major":
        delta = rng.choice([-1.0, 1.0]) * abs(
            rng.gauss(math.radians(jaggedness["major_degrees"]), math.radians(jaggedness["major_sigma_degrees"]))
        )
    elif kink_kind == "minor":
        delta = rng.choice([-1.0, 1.0]) * abs(
            rng.gauss(math.radians(jaggedness["minor_degrees"]), math.radians(jaggedness["minor_sigma_degrees"]))
        )
    elif kink_kind == "micro":
        delta = rng.choice([-1.0, 1.0]) * abs(
            rng.gauss(math.radians(jaggedness["micro_degrees"]), math.radians(jaggedness["micro_sigma_degrees"]))
        )
    else:
        delta = rng.gauss(0.0, drift_sigma)
    target = current + delta
    target = _nudge_toward(target, preferred, math.radians(jaggedness["preferred_nudge_degrees"]))
    return _clamp_angle_delta(target, preferred, math.radians(jaggedness["max_turn_degrees"]))


def _progresses_forward(left: Tuple[float, float], right: Tuple[float, float], preferred: float) -> bool:
    forward = (math.cos(preferred), math.sin(preferred))
    dx = right[0] - left[0]
    dy = right[1] - left[1]
    return dx * forward[0] + dy * forward[1] > 0.0


def _would_self_intersect(points: List[Tuple[float, float]], candidate: Tuple[float, float]) -> bool:
    if len(points) < 3:
        return False
    new_start = points[-1]
    for left, right in zip(points[:-2], points[1:-1]):
        if _segments_intersect(left, right, new_start, candidate):
            return True
    return False


def _segments_intersect(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
    d: Tuple[float, float],
) -> bool:
    def orientation(p, q, r):
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    return o1 * o2 < 0.0 and o3 * o4 < 0.0


def _nudge_toward(angle: float, preferred: float, amount: float) -> float:
    delta = _angle_delta(angle, preferred)
    if abs(delta) <= amount:
        return preferred
    return angle + amount * (1.0 if delta > 0.0 else -1.0)


def _clamp_angle_delta(angle: float, preferred: float, maximum: float) -> float:
    delta = _angle_delta(preferred, angle)
    if delta > maximum:
        return preferred + maximum
    if delta < -maximum:
        return preferred - maximum
    return angle


def _angle_delta(left: float, right: float) -> float:
    return (right - left + math.pi) % math.tau - math.pi


def _clip_profiled_polyline(
    points: List[List[float]],
    widths: List[float],
    depths: List[float],
    bounds: Mapping[str, float],
) -> Tuple[List[List[float]], List[float], List[float]]:
    clipped_points: List[List[float]] = []
    clipped_widths: List[float] = []
    clipped_depths: List[float] = []
    for index in range(len(points) - 1):
        clipped = _clip_segment(points[index], points[index + 1], bounds)
        if clipped is None:
            continue
        t0, t1 = clipped
        segment_points = [
            _interpolate_point(points[index], points[index + 1], t0),
            _interpolate_point(points[index], points[index + 1], t1),
        ]
        segment_widths = [
            _interpolate_scalar(widths[index], widths[index + 1], t0),
            _interpolate_scalar(widths[index], widths[index + 1], t1),
        ]
        segment_depths = [
            _interpolate_scalar(depths[index], depths[index + 1], t0),
            _interpolate_scalar(depths[index], depths[index + 1], t1),
        ]
        if clipped_points and _points_equal(clipped_points[-1], segment_points[0]):
            clipped_points.append(segment_points[1])
            clipped_widths.append(segment_widths[1])
            clipped_depths.append(segment_depths[1])
        else:
            clipped_points.extend(segment_points)
            clipped_widths.extend(segment_widths)
            clipped_depths.extend(segment_depths)
    return clipped_points, clipped_widths, clipped_depths


def _clip_segment(
    left: List[float], right: List[float], bounds: Mapping[str, float]
) -> Optional[Tuple[float, float]]:
    dx = right[0] - left[0]
    dy = right[1] - left[1]
    t0 = 0.0
    t1 = 1.0
    for p, q in [
        (-dx, left[0] - bounds["x_min"]),
        (dx, bounds["x_max"] - left[0]),
        (-dy, left[1] - bounds["y_min"]),
        (dy, bounds["y_max"] - left[1]),
    ]:
        if p == 0.0:
            if q < 0.0:
                return None
            continue
        ratio = q / p
        if p < 0.0:
            if ratio > t1:
                return None
            if ratio > t0:
                t0 = ratio
        else:
            if ratio < t0:
                return None
            if ratio < t1:
                t1 = ratio
    if t0 > t1:
        return None
    return t0, t1


def _interpolate_point(left: List[float], right: List[float], t: float) -> List[float]:
    return [
        round(_interpolate_scalar(left[0], right[0], t), 6),
        round(_interpolate_scalar(left[1], right[1], t), 6),
        round(_interpolate_scalar(left[2], right[2], t), 6),
    ]


def _interpolate_scalar(left: float, right: float, t: float) -> float:
    return round(float(left) + (float(right) - float(left)) * t, 6)


def _points_equal(left: List[float], right: List[float]) -> bool:
    return all(abs(a - b) < 0.000001 for a, b in zip(left, right))


def _polyline_length(points: List[List[float]]) -> float:
    total = 0.0
    for left, right in zip(points, points[1:]):
        dx = right[0] - left[0]
        dy = right[1] - left[1]
        dz = right[2] - left[2]
        total += math.sqrt(dx * dx + dy * dy + dz * dz)
    return total


def _station_profile(points: List[List[float]]) -> List[float]:
    stations = [0.0]
    for left, right in zip(points, points[1:]):
        stations.append(stations[-1] + _polyline_length([left, right]))
    return [round(station, 6) for station in stations]


def _profile_area(points: List[List[float]], widths: List[float]) -> float:
    if len(points) < 2:
        return 0.0
    area = 0.0
    for index, (left, right) in enumerate(zip(points, points[1:])):
        segment_length = _polyline_length([left, right])
        area += segment_length * (float(widths[index]) + float(widths[index + 1])) / 2.0
    return area


def _crack_boundary_profiles(
    points: List[List[float]],
    left_opening: List[float],
    right_opening: List[float],
) -> Tuple[List[List[float]], List[List[float]]]:
    left_boundary = []
    right_boundary = []
    for index, point in enumerate(points):
        nx, ny = _tangent_normal_2d(points, index)
        left_offset = max(float(left_opening[index]), 0.0)
        right_offset = max(float(right_opening[index]), 0.0)
        left_boundary.append(
            [
                round(point[0] + nx * left_offset, 6),
                round(point[1] + ny * left_offset, 6),
                round(point[2], 6),
            ]
        )
        right_boundary.append(
            [
                round(point[0] - nx * right_offset, 6),
                round(point[1] - ny * right_offset, 6),
                round(point[2], 6),
            ]
        )
    return left_boundary, right_boundary


def _measurement_profile(
    points: List[List[float]],
    stations: List[float],
    widths: List[float],
    left_boundary: List[List[float]],
    right_boundary: List[List[float]],
) -> List[Dict[str, Any]]:
    profile = []
    for index, point in enumerate(points):
        profile.append(
            {
                "index": index,
                "station": stations[index],
                "center": point,
                "left_boundary": left_boundary[index],
                "right_boundary": right_boundary[index],
                "width": round(float(widths[index]), 6),
            }
        )
    return profile


def _derive_seed(base_seed: int, label: str) -> int:
    payload = (str(base_seed) + ":" + label).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:16], 16) % (2**32)
