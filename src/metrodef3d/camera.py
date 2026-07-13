import copy
import hashlib
import math
import random
from typing import Any, Dict, Mapping, Tuple


def resolve_cameras(recipe: Mapping[str, Any]) -> Dict[str, Any]:
    resolved = copy.deepcopy(recipe)
    seed = int(resolved["run"]["seed"])
    for capture in resolved["captures"]:
        camera = capture["camera"]
        variation = camera.get("variation")
        if isinstance(variation, Mapping) and variation.get("enabled", True):
            capture["camera"] = _resolve_camera(camera, seed)
    if resolved["captures"]:
        resolved["camera"] = copy.deepcopy(resolved["captures"][0]["camera"])
    return resolved


def _resolve_camera(camera: Mapping[str, Any], seed: int) -> Dict[str, Any]:
    resolved = copy.deepcopy(camera)
    variation = dict(resolved.pop("variation"))
    selection_key = str(variation.get("selection_key", "camera"))
    fov_rng = random.Random(_derive_seed(seed, "camera-fov", selection_key))
    pose_rng = random.Random(_derive_seed(seed, "camera-pose", selection_key, str(resolved.get("type", "camera"))))
    fov_range = variation.get("fov_mm_range", [50.0, 150.0])
    fov_mm = fov_rng.uniform(float(fov_range[0]), float(fov_range[1]))
    resolved["fov_mm"] = round(fov_mm, 6)
    resolved["camera_variation"] = {
        "selection_mode": "seeded_random",
        "selection_key": selection_key,
        "fov_mm_range": [float(fov_range[0]), float(fov_range[1])],
    }

    if resolved["type"] == "orthographic":
        resolved["orthographic_scale"] = round(fov_mm, 6)
        resolved["lens_model"] = {"type": "orthographic", "distortion": "none"}
        return resolved

    target = tuple(float(value) for value in resolved["target"])
    position = tuple(float(value) for value in resolved["position"])
    target_shift = float(variation.get("target_shift_mm", 12.0))
    target = (
        target[0] + pose_rng.uniform(-target_shift, target_shift),
        target[1] + pose_rng.uniform(-target_shift, target_shift),
        target[2],
    )
    height = max(position[2] - target[2], 1.0)
    tilt_range = variation.get("tilt_degrees_range", [0.0, 7.0])
    tilt_degrees = pose_rng.uniform(float(tilt_range[0]), float(tilt_range[1]))
    azimuth_range = variation.get("tilt_azimuth_degrees_range", [0.0, 360.0])
    azimuth_degrees = pose_rng.uniform(float(azimuth_range[0]), float(azimuth_range[1]))
    lateral = math.tan(math.radians(tilt_degrees)) * height
    position = (
        target[0] + math.cos(math.radians(azimuth_degrees)) * lateral,
        target[1] + math.sin(math.radians(azimuth_degrees)) * lateral,
        position[2],
    )
    roll_range = variation.get("roll_degrees_range", [-2.0, 2.0])
    roll_degrees = pose_rng.uniform(float(roll_range[0]), float(roll_range[1]))
    distance = _distance(position, target)
    fov_degrees = math.degrees(2.0 * math.atan(fov_mm / (2.0 * distance)))
    sensor_width_mm = float(variation.get("sensor_width_mm", 36.0))
    focal_length_mm = sensor_width_mm * distance / max(fov_mm, 0.001)

    resolved["position"] = [round(value, 6) for value in position]
    resolved["target"] = [round(value, 6) for value in target]
    resolved["fov_degrees"] = round(fov_degrees, 6)
    resolved["roll_degrees"] = round(roll_degrees, 6)
    resolved["lens_model"] = {
        "type": "pinhole_perspective",
        "fov_mm": round(fov_mm, 6),
        "sensor_width_mm": round(sensor_width_mm, 6),
        "focal_length_mm": round(focal_length_mm, 6),
        "distortion": "none",
    }
    resolved["camera_variation"].update(
        {
            "target_shift_mm": target_shift,
            "tilt_degrees": round(tilt_degrees, 6),
            "tilt_azimuth_degrees_range": [float(azimuth_range[0]), float(azimuth_range[1])],
            "azimuth_degrees": round(azimuth_degrees, 6),
            "roll_degrees": round(roll_degrees, 6),
        }
    )
    return resolved


def _distance(left: Tuple[float, float, float], right: Tuple[float, float, float]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _derive_seed(seed: int, *parts: str) -> int:
    text = ":".join([str(seed), *parts])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)
