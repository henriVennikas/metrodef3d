import copy
import hashlib
import math
import random
from typing import Any, Dict, List, Mapping, Optional, Tuple


DEFAULT_LIGHTING_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "daylight_clouded",
        "family": "natural_daylight",
        "weight": 1.3,
        "lighting": {
            "type": "area",
            "position": [0.0, 0.0, 320.0],
            "target": [0.0, 0.0, 0.0],
            "energy": 1700000.0,
            "size": 420.0,
        },
    },
    {
        "id": "sunny_direct",
        "family": "natural_daylight",
        "weight": 1.0,
        "lighting": {
            "type": "sun",
            "position": [-260.0, -180.0, 520.0],
            "target": [0.0, 0.0, 0.0],
            "energy": 6.4,
            "angle_degrees": 2.0,
        },
    },
    {
        "id": "sunny_partial_shadow",
        "family": "natural_daylight",
        "weight": 0.9,
        "lighting": {
            "type": "multi",
            "lights": [
                {
                    "type": "sun",
                    "position": [-260.0, -180.0, 520.0],
                    "target": [0.0, 0.0, 0.0],
                    "energy": 5.6,
                    "angle_degrees": 1.2,
                },
                {
                    "type": "area",
                    "position": [50.0, -75.0, 180.0],
                    "target": [0.0, 0.0, 0.0],
                    "energy": 360000.0,
                    "size": 260.0,
                },
            ],
            "shadow_occluders": "seeded_irregular",
        },
    },
    {
        "id": "indoor_spot",
        "family": "artificial_indoor",
        "weight": 1.0,
        "lighting": {
            "type": "spot",
            "position": [-90.0, -120.0, 260.0],
            "target": [0.0, 0.0, 0.0],
            "energy": 1900000.0,
            "spot_size_degrees": 45.0,
            "spot_blend": 0.45,
            "shadow_soft_size": 18.0,
        },
    },
    {
        "id": "indoor_led_strip",
        "family": "artificial_indoor",
        "weight": 1.0,
        "lighting": {
            "type": "area",
            "shape": "rectangle",
            "position": [0.0, -105.0, 170.0],
            "target": [0.0, 0.0, 0.0],
            "energy": 1300000.0,
            "size": 28.0,
            "size_y": 230.0,
        },
    },
    {
        "id": "indoor_halogen_tube",
        "family": "artificial_indoor",
        "weight": 0.8,
        "lighting": {
            "type": "area",
            "shape": "rectangle",
            "position": [-135.0, 40.0, 155.0],
            "target": [0.0, 0.0, 0.0],
            "energy": 1040000.0,
            "size": 22.0,
            "size_y": 190.0,
        },
    },
]


def resolve_lighting(recipe: Mapping[str, Any]) -> Dict[str, Any]:
    resolved = copy.deepcopy(recipe)
    base_seed = int(resolved["run"]["seed"])
    for capture in resolved["captures"]:
        lighting = capture["lighting"]
        if lighting.get("type") == "preset_random":
            capture["lighting"] = _resolve_random_preset(base_seed, str(capture["id"]), lighting)
        elif lighting.get("type") == "preset":
            capture["lighting"] = _resolve_named_preset(str(lighting["preset"]))
    if resolved["captures"]:
        resolved["lighting"] = copy.deepcopy(resolved["captures"][0]["lighting"])
    return resolved


def _resolve_random_preset(seed: int, capture_id: str, request: Mapping[str, Any]) -> Dict[str, Any]:
    choices = request.get("choices")
    presets = _preset_choices(choices)
    selection_key = str(request.get("selection_key", "lighting"))
    rng = random.Random(_derive_seed(seed, "lighting", selection_key))
    total = sum(float(preset.get("weight", 1.0)) for preset in presets)
    draw = rng.uniform(0.0, total)
    running = 0.0
    for preset in presets:
        running += float(preset.get("weight", 1.0))
        if draw <= running:
            return _resolved_preset_payload(preset, "seeded_random", selection_key, seed)
    return _resolved_preset_payload(presets[-1], "seeded_random", selection_key, seed)


def _resolve_named_preset(preset_id: str) -> Dict[str, Any]:
    for preset in DEFAULT_LIGHTING_PRESETS:
        if preset["id"] == preset_id:
            return _resolved_preset_payload(preset, "pinned", "lighting", None)
    raise ValueError("Unknown lighting preset: " + preset_id)


def _preset_choices(choices: Any) -> List[Mapping[str, Any]]:
    if choices is None:
        return DEFAULT_LIGHTING_PRESETS
    choice_ids = set(str(choice) for choice in choices)
    presets = [preset for preset in DEFAULT_LIGHTING_PRESETS if preset["id"] in choice_ids]
    if not presets:
        raise ValueError("lighting preset_random choices did not match any known presets.")
    return presets


def _resolved_preset_payload(
    preset: Mapping[str, Any],
    mode: str,
    selection_key: str,
    seed: Optional[int],
) -> Dict[str, Any]:
    lighting = copy.deepcopy(preset["lighting"])
    if lighting.get("shadow_occluders") == "seeded_irregular":
        if seed is None:
            lighting["shadow_occluders"] = _fixed_irregular_shadow_occluders()
        else:
            lighting["shadow_occluders"] = _seeded_irregular_shadow_occluders(seed, selection_key, str(preset["id"]))
    if seed is not None:
        _vary_directional_lights(lighting, seed, selection_key, str(preset["id"]))
    lighting["preset_id"] = preset["id"]
    lighting["preset_family"] = preset["family"]
    lighting["selection_mode"] = mode
    lighting["selection_key"] = selection_key
    return lighting


def _vary_directional_lights(lighting: Dict[str, Any], seed: int, selection_key: str, preset_id: str) -> None:
    if lighting["type"] == "multi":
        for index, light in enumerate(lighting["lights"]):
            _vary_directional_lights(light, seed, selection_key, preset_id + "-" + str(index))
        return
    if lighting["type"] != "sun":
        return
    rng = random.Random(_derive_seed(seed, "illumination-angle", selection_key, preset_id))
    target = lighting.get("target", [0.0, 0.0, 0.0])
    radius = rng.uniform(430.0, 680.0)
    azimuth = rng.uniform(0.0, 360.0)
    elevation = rng.uniform(28.0, 68.0)
    horizontal = radius * math.cos(math.radians(elevation))
    position = [
        float(target[0]) + math.cos(math.radians(azimuth)) * horizontal,
        float(target[1]) + math.sin(math.radians(azimuth)) * horizontal,
        float(target[2]) + math.sin(math.radians(elevation)) * radius,
    ]
    lighting["position"] = [round(value, 6) for value in position]
    lighting["direction_variation"] = {
        "selection_mode": "seeded_random",
        "selection_key": selection_key,
        "azimuth_degrees": round(azimuth, 6),
        "elevation_degrees": round(elevation, 6),
        "distance_mm": round(radius, 6),
    }


def _seeded_irregular_shadow_occluders(seed: int, selection_key: str, preset_id: str) -> List[Dict[str, Any]]:
    rng = random.Random(_derive_seed(seed, "shadow-occluders", selection_key, preset_id))
    occluders = []
    for index in range(rng.randint(1, 3)):
        length = rng.uniform(95.0, 260.0)
        width = rng.uniform(28.0, 95.0)
        x = rng.uniform(-95.0, 95.0)
        y = rng.uniform(-95.0, 95.0)
        z = rng.uniform(65.0, 185.0)
        rotation = rng.uniform(0.0, 180.0)
        vertices = _irregular_occluder_vertices(rng, length, width)
        occluders.append(
            {
                "type": "polygon",
                "position": [round(x, 6), round(y, 6), round(z, 6)],
                "rotation_degrees": round(rotation, 6),
                "vertices": [[round(px, 6), round(py, 6)] for px, py in vertices],
                "source": "seeded_irregular",
                "index": index,
            }
        )
    return occluders


def _fixed_irregular_shadow_occluders() -> List[Dict[str, Any]]:
    return [
        {
            "type": "polygon",
            "position": [-55.0, -10.0, 90.0],
            "rotation_degrees": 22.0,
            "vertices": [[-42.0, -95.0], [38.0, -82.0], [49.0, 88.0], [-33.0, 97.0]],
            "source": "fixed_irregular",
            "index": 0,
        }
    ]


def _irregular_occluder_vertices(rng: random.Random, length: float, width: float) -> List[Tuple[float, float]]:
    half_length = length / 2.0
    half_width = width / 2.0
    segments = rng.randint(2, 4)
    left = []
    right = []
    for index in range(segments + 1):
        y = -half_length + length * index / float(segments)
        left.append((-half_width * rng.uniform(0.75, 1.35), y + rng.uniform(-length * 0.05, length * 0.05)))
        right.append((half_width * rng.uniform(0.75, 1.35), y + rng.uniform(-length * 0.05, length * 0.05)))
    return left + list(reversed(right))


def _derive_seed(seed: int, *parts: str) -> int:
    text = ":".join([str(seed), *parts])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)
