import copy
import colorsys
import hashlib
import random
from typing import Any, Dict, Mapping


DEFAULT_PITTING_VARIANTS = [
    {"id": "none", "weight": 0.22, "multiplier_range": [0.0, 0.0]},
    {"id": "subtle", "weight": 0.30, "multiplier_range": [0.20, 0.55]},
    {"id": "moderate", "weight": 0.33, "multiplier_range": [0.65, 1.05]},
    {"id": "strong", "weight": 0.15, "multiplier_range": [1.15, 1.65]},
]


DEFAULT_AGGREGATE_VARIANTS = [
    {"id": "none", "weight": 0.45, "enabled": False},
    {
        "id": "sparse",
        "weight": 0.35,
        "enabled": True,
        "scale_range": [220.0, 340.0],
        "ramp_black_range": [0.78, 0.86],
        "ramp_width_range": [0.003, 0.010],
        "color_choices": ["#8c887d", "#9a9588", "#77766f"],
        "roughness_range": [0.62, 0.86],
    },
    {
        "id": "moderate",
        "weight": 0.20,
        "enabled": True,
        "scale_range": [300.0, 460.0],
        "ramp_black_range": [0.76, 0.84],
        "ramp_width_range": [0.003, 0.012],
        "color_choices": ["#8a887f", "#a09a8b", "#6f716c"],
        "roughness_range": [0.58, 0.82],
    },
]


DEFAULT_SURFACE_FAMILIES = [
    {"id": "current_mottled", "weight": 0.55, "overrides": {}},
    {
        "id": "multitone_weathered",
        "weight": 0.45,
        "overrides": {
            "noise_scale": 4.0,
            "noise_roughness": 1.0,
            "noise_ramp_black": 0.293182,
            "noise_ramp_white": 0.495455,
            "noise_ramp_black_color": "#000000",
            "noise_ramp_white_color": "#dafcff",
            "cloudy_noise_detail": 12.8,
            "cloudy_noise_roughness": 0.9,
            "pore_noise_a_scale": 11.9,
            "pore_noise_normalize": False,
            "pore_mix_factor": 0.508333,
            "pore_ramp_a_black": 0.320454,
            "pore_ramp_a_white": 0.452273,
            "pore_ramp_a_black_color": "#ebeefe",
            "pore_ramp_a_white_color": "#000000",
            "pore_ramp_b_black": 0.238637,
            "pore_ramp_b_white": 0.334092,
            "pore_ramp_b_black_color": "#000000",
            "pore_ramp_b_white_color": "#fcf2ef",
            "final_mix_factor": 1.0,
            "base_from_min": -0.2,
            "base_from_max": 1.3,
            "base_to_min": 1.1,
            "base_to_max": 0.0,
            "base_color_model": "ramp",
            "base_color_ramp": [
                {"position": 0.0, "color": "#353433"},
                {"position": 0.118182, "color": "#6c6b73"},
                {"position": 0.552273, "color": "#5b5448"},
                {"position": 1.0, "color": "#9a8b88"},
            ],
            "pitting_coarse_detail": 10.0,
            "pitting_coarse_roughness": 0.5,
            "pitting_coarse_ramp_black": 0.470454,
            "pitting_fine_scale": 1000.0,
            "pitting_fine_ramp_black": 0.520455,
            "color_jitter": {
                "enabled": True,
                "hue_shift_range": [-0.018, 0.018],
                "saturation_multiplier_range": [0.88, 1.14],
                "value_multiplier_range": [0.92, 1.08],
                "per_stop_value_jitter": 0.035,
                "position_jitter": 0.035,
                "targets": [
                    "noise_ramp_white_color",
                    "pore_ramp_a_black_color",
                    "pore_ramp_b_white_color",
                    "base_color_ramp",
                ],
            },
        },
    },
]


DEFAULT_SURFACE_ROUGHNESS_VARIANTS = [
    {
        "id": "polished",
        "weight": 0.12,
        "displacement_multiplier_range": [0.0, 0.08],
        "pitting_multiplier_range": [0.0, 0.10],
    },
    {
        "id": "honed",
        "weight": 0.18,
        "displacement_multiplier_range": [0.16, 0.38],
        "pitting_multiplier_range": [0.12, 0.42],
    },
    {
        "id": "light_texture",
        "weight": 0.30,
        "displacement_multiplier_range": [0.45, 0.78],
        "pitting_multiplier_range": [0.42, 0.82],
    },
    {
        "id": "cast_texture",
        "weight": 0.28,
        "displacement_multiplier_range": [0.85, 1.18],
        "pitting_multiplier_range": [0.80, 1.22],
    },
    {
        "id": "rough_cast",
        "weight": 0.12,
        "displacement_multiplier_range": [1.25, 1.80],
        "pitting_multiplier_range": [1.12, 1.70],
    },
]


def resolve_material(recipe: Mapping[str, Any]) -> Dict[str, Any]:
    resolved = copy.deepcopy(recipe)
    material = resolved.get("material", {})
    texture = material.get("concrete_texture")
    if not isinstance(texture, Mapping):
        return resolved
    mutable_texture = dict(texture)
    seed = int(resolved["run"]["seed"])

    family_variation = texture.get("surface_family_variation")
    if isinstance(family_variation, Mapping) and family_variation.get("enabled", False):
        _resolve_surface_family(mutable_texture, seed, family_variation)

    variation = texture.get("pitting_variation")
    if isinstance(variation, Mapping) and variation.get("enabled", False):
        selection_key = str(variation.get("selection_key", "concrete-pitting"))
        rng = random.Random(_derive_seed(seed, "material-pitting", selection_key))
        variant = _choose_variant(variation, rng)
        multiplier_range = variant.get("multiplier_range", [1.0, 1.0])
        multiplier = rng.uniform(float(multiplier_range[0]), float(multiplier_range[1]))

        base_coarse_depth = float(mutable_texture.get("pitting_coarse_depth", -10.0))
        base_fine_depth = float(mutable_texture.get("pitting_fine_depth", -5.0))
        base_modulation_strength = float(mutable_texture.get("pitting_modulation_strength", 0.7))
        mutable_texture["pitting_coarse_depth"] = round(base_coarse_depth * multiplier, 6)
        mutable_texture["pitting_fine_depth"] = round(base_fine_depth * multiplier, 6)
        mutable_texture["pitting_modulation_strength"] = round(base_modulation_strength * multiplier, 6)
        mutable_texture["pitting_variation_resolved"] = {
            "selection_mode": "seeded_random",
            "selection_key": selection_key,
            "variant_id": str(variant.get("id", "custom")),
            "multiplier": round(multiplier, 6),
            "multiplier_range": [float(multiplier_range[0]), float(multiplier_range[1])],
            "base_pitting_coarse_depth": base_coarse_depth,
            "base_pitting_fine_depth": base_fine_depth,
            "base_pitting_modulation_strength": base_modulation_strength,
        }

    roughness_variation = texture.get("surface_roughness_variation")
    if isinstance(roughness_variation, Mapping) and roughness_variation.get("enabled", False):
        _resolve_surface_roughness_variation(mutable_texture, seed, roughness_variation)

    aggregate = texture.get("aggregate_variation")
    if isinstance(aggregate, Mapping) and aggregate.get("enabled", False):
        _resolve_aggregate_variation(mutable_texture, seed, aggregate)

    resolved["material"] = dict(material)
    resolved["material"]["concrete_texture"] = mutable_texture
    return resolved


def _resolve_surface_family(mutable_texture: Dict[str, Any], seed: int, variation: Mapping[str, Any]) -> None:
    selection_key = str(variation.get("selection_key", "concrete-surface-family"))
    rng = random.Random(_derive_seed(seed, "material-surface-family", selection_key))
    variant = _choose_variant(variation, rng, DEFAULT_SURFACE_FAMILIES)
    overrides = variant.get("overrides", {})
    if isinstance(overrides, Mapping):
        mutable_texture.update(copy.deepcopy(dict(overrides)))
    jitter = overrides.get("color_jitter") if isinstance(overrides, Mapping) else None
    jitter_resolved = None
    if isinstance(jitter, Mapping) and jitter.get("enabled", False):
        jitter_resolved = _apply_color_jitter(mutable_texture, seed, selection_key, jitter)
    mutable_texture["surface_family_variation_resolved"] = {
        "selection_mode": "seeded_random",
        "selection_key": selection_key,
        "variant_id": str(variant.get("id", "custom")),
        "overrides": copy.deepcopy(dict(overrides)) if isinstance(overrides, Mapping) else {},
    }
    if jitter_resolved is not None:
        mutable_texture["surface_family_variation_resolved"]["color_jitter"] = jitter_resolved


def _resolve_surface_roughness_variation(mutable_texture: Dict[str, Any], seed: int, variation: Mapping[str, Any]) -> None:
    selection_key = str(variation.get("selection_key", "concrete-surface-roughness"))
    rng = random.Random(_derive_seed(seed, "material-surface-roughness", selection_key))
    variant = _choose_variant(variation, rng, DEFAULT_SURFACE_ROUGHNESS_VARIANTS)
    displacement_range = variant.get("displacement_multiplier_range", [1.0, 1.0])
    pitting_range = variant.get("pitting_multiplier_range", displacement_range)
    displacement_multiplier = rng.uniform(float(displacement_range[0]), float(displacement_range[1]))
    pitting_multiplier = rng.uniform(float(pitting_range[0]), float(pitting_range[1]))

    base_cloudy_displacement = float(mutable_texture.get("cloudy_displacement_strength", 0.05))
    base_pitting_coarse_depth = float(mutable_texture.get("pitting_coarse_depth", -10.0))
    base_pitting_fine_depth = float(mutable_texture.get("pitting_fine_depth", -5.0))
    base_pitting_modulation_strength = float(mutable_texture.get("pitting_modulation_strength", 0.7))

    mutable_texture["cloudy_displacement_strength"] = round(base_cloudy_displacement * displacement_multiplier, 6)
    mutable_texture["pitting_coarse_depth"] = round(base_pitting_coarse_depth * pitting_multiplier, 6)
    mutable_texture["pitting_fine_depth"] = round(base_pitting_fine_depth * pitting_multiplier, 6)
    mutable_texture["pitting_modulation_strength"] = round(base_pitting_modulation_strength * pitting_multiplier, 6)
    mutable_texture["surface_roughness_variation_resolved"] = {
        "selection_mode": "seeded_random",
        "selection_key": selection_key,
        "variant_id": str(variant.get("id", "custom")),
        "displacement_multiplier": round(displacement_multiplier, 6),
        "displacement_multiplier_range": [float(displacement_range[0]), float(displacement_range[1])],
        "pitting_multiplier": round(pitting_multiplier, 6),
        "pitting_multiplier_range": [float(pitting_range[0]), float(pitting_range[1])],
        "base_cloudy_displacement_strength": base_cloudy_displacement,
        "base_pitting_coarse_depth": base_pitting_coarse_depth,
        "base_pitting_fine_depth": base_pitting_fine_depth,
        "base_pitting_modulation_strength": base_pitting_modulation_strength,
    }


def _resolve_aggregate_variation(mutable_texture: Dict[str, Any], seed: int, variation: Mapping[str, Any]) -> None:
    selection_key = str(variation.get("selection_key", "concrete-aggregate"))
    rng = random.Random(_derive_seed(seed, "material-aggregate", selection_key))
    variant = _choose_variant(variation, rng, DEFAULT_AGGREGATE_VARIANTS)
    enabled = bool(variant.get("enabled", True))
    resolved = {
        "selection_mode": "seeded_random",
        "selection_key": selection_key,
        "variant_id": str(variant.get("id", "custom")),
        "enabled": enabled,
    }
    mutable_texture["aggregate_enabled"] = enabled
    if not enabled:
        mutable_texture["aggregate_variation_resolved"] = resolved
        return

    scale_range = variant.get("scale_range", [18.0, 30.0])
    ramp_black_range = variant.get("ramp_black_range", [0.48, 0.56])
    ramp_width_range = variant.get("ramp_width_range", [0.04, 0.08])
    roughness_range = variant.get("roughness_range", [0.62, 0.86])
    color_choices = variant.get("color_choices", ["#8c887d"])
    scale = rng.uniform(float(scale_range[0]), float(scale_range[1]))
    ramp_black = rng.uniform(float(ramp_black_range[0]), float(ramp_black_range[1]))
    ramp_width = rng.uniform(float(ramp_width_range[0]), float(ramp_width_range[1]))
    ramp_white = min(ramp_black + ramp_width, 1.0)
    roughness = rng.uniform(float(roughness_range[0]), float(roughness_range[1]))
    color = str(rng.choice(color_choices)) if color_choices else "#8c887d"

    mutable_texture["aggregate_scale"] = round(scale, 6)
    mutable_texture["aggregate_ramp_black"] = round(ramp_black, 6)
    mutable_texture["aggregate_ramp_white"] = round(ramp_white, 6)
    mutable_texture["aggregate_color"] = color
    mutable_texture["aggregate_roughness"] = round(roughness, 6)
    mutable_texture["aggregate_variation_resolved"] = {
        **resolved,
        "scale": round(scale, 6),
        "scale_range": [float(scale_range[0]), float(scale_range[1])],
        "ramp_black": round(ramp_black, 6),
        "ramp_width": round(ramp_width, 6),
        "ramp_white": round(ramp_white, 6),
        "roughness": round(roughness, 6),
        "color": color,
    }


def _apply_color_jitter(
    mutable_texture: Dict[str, Any],
    seed: int,
    selection_key: str,
    jitter: Mapping[str, Any],
) -> Dict[str, Any]:
    rng = random.Random(_derive_seed(seed, "material-surface-color-jitter", selection_key))
    hue_range = jitter.get("hue_shift_range", [-0.015, 0.015])
    saturation_range = jitter.get("saturation_multiplier_range", [0.9, 1.1])
    value_range = jitter.get("value_multiplier_range", [0.92, 1.08])
    hue_shift = rng.uniform(float(hue_range[0]), float(hue_range[1]))
    saturation_multiplier = rng.uniform(float(saturation_range[0]), float(saturation_range[1]))
    value_multiplier = rng.uniform(float(value_range[0]), float(value_range[1]))
    per_stop_value_jitter = float(jitter.get("per_stop_value_jitter", 0.0))
    position_jitter = float(jitter.get("position_jitter", 0.0))
    targets = jitter.get("targets", [])
    changed = {}

    for target in targets:
        if target == "base_color_ramp" and isinstance(mutable_texture.get(target), list):
            new_stops = []
            stop_changes = []
            ramp_stops = mutable_texture[target]
            position_offsets = _ramp_position_offsets(ramp_stops, position_jitter, rng)
            for index, stop in enumerate(ramp_stops):
                if not isinstance(stop, Mapping) or "color" not in stop:
                    new_stops.append(stop)
                    continue
                local_value_multiplier = value_multiplier * rng.uniform(
                    max(0.0, 1.0 - per_stop_value_jitter),
                    1.0 + per_stop_value_jitter,
                )
                new_color = _jitter_hex_color(
                    str(stop["color"]),
                    hue_shift,
                    saturation_multiplier,
                    local_value_multiplier,
                )
                new_stop = dict(stop)
                base_position = float(stop.get("position", 0.0))
                new_position = _clamp(base_position + position_offsets[index], 0.0, 1.0)
                new_stop["position"] = round(new_position, 6)
                new_stop["color"] = new_color
                new_stops.append(new_stop)
                stop_changes.append(
                    {
                        "base_position": base_position,
                        "resolved_position": round(new_position, 6),
                        "base_color": str(stop["color"]),
                        "resolved_color": new_color,
                    }
                )
            new_stops = _ensure_sorted_ramp_stops(new_stops)
            for index, stop_change in enumerate(stop_changes):
                stop_change["resolved_position"] = float(new_stops[index]["position"])
            mutable_texture[target] = new_stops
            changed[target] = stop_changes
        elif target in mutable_texture:
            base_color = str(mutable_texture[target])
            new_color = _jitter_hex_color(base_color, hue_shift, saturation_multiplier, value_multiplier)
            mutable_texture[target] = new_color
            changed[str(target)] = {"base_color": base_color, "resolved_color": new_color}

    return {
        "hue_shift": round(hue_shift, 6),
        "saturation_multiplier": round(saturation_multiplier, 6),
        "value_multiplier": round(value_multiplier, 6),
        "per_stop_value_jitter": round(per_stop_value_jitter, 6),
        "position_jitter": round(position_jitter, 6),
        "targets": list(targets),
        "colors": changed,
    }


def _ramp_position_offsets(stops, jitter_amount: float, rng: random.Random):
    if jitter_amount <= 0.0:
        return [0.0 for _ in stops]
    offsets = []
    for index, _stop in enumerate(stops):
        if index == 0 or index == len(stops) - 1:
            offsets.append(0.0)
        else:
            offsets.append(rng.uniform(-jitter_amount, jitter_amount))
    return offsets


def _ensure_sorted_ramp_stops(stops):
    if len(stops) < 2:
        return stops
    sorted_stops = []
    minimum_gap = 0.025
    previous_position = -minimum_gap
    for index, stop in enumerate(stops):
        new_stop = dict(stop)
        if index == 0:
            new_stop["position"] = 0.0
        elif index == len(stops) - 1:
            new_stop["position"] = 1.0
        else:
            upper = 1.0 - minimum_gap * (len(stops) - 1 - index)
            position = max(float(new_stop["position"]), previous_position + minimum_gap)
            new_stop["position"] = round(min(position, upper), 6)
        previous_position = float(new_stop["position"])
        sorted_stops.append(new_stop)
    return sorted_stops


def _jitter_hex_color(value: str, hue_shift: float, saturation_multiplier: float, value_multiplier: float) -> str:
    red, green, blue = _hex_to_rgb01(value)
    hue, saturation, brightness = colorsys.rgb_to_hsv(red, green, blue)
    hue = (hue + hue_shift) % 1.0
    saturation = _clamp(saturation * saturation_multiplier, 0.0, 0.55)
    brightness = _clamp(brightness * value_multiplier, 0.05, 0.92)
    new_red, new_green, new_blue = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return _rgb01_to_hex(new_red, new_green, new_blue)


def _hex_to_rgb01(value: str):
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        return (0.5, 0.5, 0.5)
    return (
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
    )


def _rgb01_to_hex(red: float, green: float, blue: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        int(round(_clamp(red, 0.0, 1.0) * 255.0)),
        int(round(_clamp(green, 0.0, 1.0) * 255.0)),
        int(round(_clamp(blue, 0.0, 1.0) * 255.0)),
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _choose_variant(
    variation: Mapping[str, Any],
    rng: random.Random,
    default_choices=DEFAULT_PITTING_VARIANTS,
) -> Mapping[str, Any]:
    choices = variation.get("choices", default_choices)
    total = sum(float(choice.get("weight", 1.0)) for choice in choices)
    draw = rng.uniform(0.0, total)
    running = 0.0
    for choice in choices:
        running += float(choice.get("weight", 1.0))
        if draw <= running:
            return choice
    return choices[-1]


def _derive_seed(seed: int, *parts: str) -> int:
    text = ":".join([str(seed), *parts])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)
