import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import PIXEL_SCALE_SCHEMA_VERSION, VISIBLE_DEFECT_SCHEMA_VERSION
from .errors import RenderError


def render_image(recipe: Mapping[str, Any], scene: Mapping[str, Any], out_dir: Path) -> Path:
    capture = recipe["captures"][0]
    image_path = out_dir / ("render." + str(recipe["render"]["image_format"]).lower())
    return render_outputs(recipe, scene, {capture["id"]: {"image": image_path}})[0]["image_path"]


def render_outputs(
    recipe: Mapping[str, Any],
    scene: Mapping[str, Any],
    capture_paths: Mapping[str, Mapping[str, Path]],
) -> List[Dict[str, Any]]:
    if recipe["render"]["backend"] == "blender":
        return _render_blender_batch(recipe, scene, capture_paths)
    outputs = []
    for capture in recipe["captures"]:
        paths = capture_paths[capture["id"]]
        image_path = _render_capture(recipe, capture, scene, paths)
        outputs.append(_capture_output(capture, image_path, paths))
        for variant in capture.get("render_variants", []):
            if not variant.get("enabled", True):
                continue
            variant_paths = paths["variants"][str(variant["id"])]
            variant_image_path = _render_capture(recipe, capture, scene, variant_paths, variant)
            outputs.append(_capture_output(capture, variant_image_path, variant_paths, variant))
    return outputs


def _render_blender_batch(
    recipe: Mapping[str, Any],
    scene: Mapping[str, Any],
    capture_paths: Mapping[str, Mapping[str, Path]],
) -> List[Dict[str, Any]]:
    executable = str(recipe["render"].get("executable", "blender"))
    resolved = _resolve_blender_executable(executable)
    if resolved is None:
        raise RenderError(
            "Blender executable not found: "
            + executable
            + ". Install Blender, add it to PATH, or set render.executable in the recipe."
        )

    batch_paths = capture_paths["__batch__"]
    script_path = batch_paths["blender_script"]
    blend_path = batch_paths["blend"]
    script_path.parent.mkdir(parents=True, exist_ok=True)
    blend_path.parent.mkdir(parents=True, exist_ok=True)

    render_items, output_specs = _blender_render_specs(recipe, capture_paths)
    script_path.write_text(
        build_blender_batch_script(recipe, scene, render_items, blend_path),
        encoding="utf-8",
    )
    result = subprocess.run(
        [resolved, "--background", "--factory-startup", "--python", str(script_path)],
    )
    if result.returncode != 0:
        raise RenderError("Blender batch render failed with exit code " + str(result.returncode))

    _validate_blender_outputs(blend_path, output_specs)
    return _blender_capture_outputs(script_path, blend_path, output_specs)


def render_blender_seed_batch(items: List[Mapping[str, Any]], script_path: Path) -> List[List[Dict[str, Any]]]:
    if not items:
        return []
    executable = str(items[0]["recipe"]["render"].get("executable", "blender"))
    resolved = _resolve_blender_executable(executable)
    if resolved is None:
        raise RenderError(
            "Blender executable not found: "
            + executable
            + ". Install Blender, add it to PATH, or set render.executable in the recipe."
        )
    script_path.parent.mkdir(parents=True, exist_ok=True)
    scripts = []
    per_seed_specs = []
    for item in items:
        recipe = item["recipe"]
        scene = item["scene"]
        capture_paths = item["capture_paths"]
        batch_paths = capture_paths["__batch__"]
        seed_script_path = batch_paths["blender_script"]
        blend_path = batch_paths["blend"]
        seed_script_path.parent.mkdir(parents=True, exist_ok=True)
        blend_path.parent.mkdir(parents=True, exist_ok=True)
        render_items, output_specs = _blender_render_specs(recipe, capture_paths)
        seed_script = build_blender_batch_script(recipe, scene, render_items, blend_path)
        seed_script_path.write_text(seed_script, encoding="utf-8")
        scripts.append("\n# metrodef3d hot batch seed " + str(recipe["run"]["seed"]) + "\n" + seed_script)
        per_seed_specs.append((seed_script_path, blend_path, output_specs))
    script_path.write_text("\n".join(scripts), encoding="utf-8")
    result = subprocess.run(
        [resolved, "--background", "--factory-startup", "--python", str(script_path)],
    )
    if result.returncode != 0:
        raise RenderError("Blender seed batch render failed with exit code " + str(result.returncode))
    outputs = []
    for seed_script_path, blend_path, output_specs in per_seed_specs:
        _validate_blender_outputs(blend_path, output_specs)
        outputs.append(_blender_capture_outputs(seed_script_path, blend_path, output_specs))
    return outputs


def _blender_render_specs(
    recipe: Mapping[str, Any],
    capture_paths: Mapping[str, Mapping[str, Path]],
) -> tuple:
    render_items = []
    output_specs = []
    seen_truth_paths = set()
    for capture in recipe["captures"]:
        paths = capture_paths[capture["id"]]
        specs = [(None, paths)]
        for variant in capture.get("render_variants", []):
            if variant.get("enabled", True):
                specs.append((variant, paths["variants"][str(variant["id"])]))
        for render_variant, item_paths in specs:
            image_path = item_paths["image"]
            image_path.parent.mkdir(parents=True, exist_ok=True)
            for key in ("visible_defect", "pixel_scale"):
                if key in item_paths:
                    item_paths[key].parent.mkdir(parents=True, exist_ok=True)
            render_items.append(
                {
                    "capture": capture,
                    "render_variant": dict(render_variant) if render_variant is not None else None,
                    "image_path": str(image_path),
                    "visible_defect_path": str(item_paths["visible_defect"]),
                    "pixel_scale_path": str(item_paths["pixel_scale"]),
                    "write_truth": str(item_paths["visible_defect"]) not in seen_truth_paths,
                }
            )
            seen_truth_paths.add(str(item_paths["visible_defect"]))
            output_specs.append((capture, render_variant, image_path, item_paths))
    return render_items, output_specs


def _validate_blender_outputs(blend_path: Path, output_specs: List[tuple]) -> None:
    if not blend_path.exists() or blend_path.stat().st_size == 0:
        raise RenderError("Blender completed but did not write a non-empty blend file: " + str(blend_path))
    for _capture, _variant, image_path, item_paths in output_specs:
        if not image_path.exists() or image_path.stat().st_size == 0:
            raise RenderError("Blender completed but did not write a non-empty image: " + str(image_path))
        for key, label in (("visible_defect", "visible-defect sidecar"), ("pixel_scale", "pixel-scale sidecar")):
            path = item_paths[key]
            if not path.exists() or path.stat().st_size == 0:
                raise RenderError("Blender completed but did not write " + label + ": " + str(path))


def _blender_capture_outputs(
    script_path: Path,
    blend_path: Path,
    output_specs: List[tuple],
) -> List[Dict[str, Any]]:
    outputs = []
    for capture, render_variant, image_path, item_paths in output_specs:
        output_paths = dict(item_paths)
        output_paths["blender_script"] = script_path
        output_paths["blend"] = blend_path
        outputs.append(_capture_output(capture, image_path, output_paths, render_variant))
    return outputs


def _capture_output(
    capture: Mapping[str, Any],
    image_path: Path,
    paths: Mapping[str, Any],
    render_variant: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    output = {
        "capture_id": capture["id"],
        "image_path": image_path,
        "camera": capture["camera"],
        "lighting": capture["lighting"],
    }
    if render_variant is not None:
        output_id = str(render_variant.get("output_id", str(capture["id"]) + "-" + str(render_variant["id"])))
        output["capture_id"] = output_id
        output["source_capture_id"] = capture["id"]
        output["render_variant"] = dict(render_variant)
    if "blender_script" in paths:
        output["blender_script_path"] = paths["blender_script"]
    if "blend" in paths:
        output["blend_path"] = paths["blend"]
    if "visible_defect" in paths:
        output["visible_defect_path"] = paths["visible_defect"]
        if paths["visible_defect"].exists():
            output["visible_defect"] = json.loads(paths["visible_defect"].read_text(encoding="utf-8"))
    if "pixel_scale" in paths:
        output["pixel_scale_path"] = paths["pixel_scale"]
        if paths["pixel_scale"].exists():
            with zipfile.ZipFile(paths["pixel_scale"]) as archive:
                output["nominal_surface_pixel_scale"] = json.loads(
                    archive.read("summary.json").decode("utf-8")
                )
    return output


def _render_capture(
    recipe: Mapping[str, Any],
    capture: Mapping[str, Any],
    scene: Mapping[str, Any],
    paths: Mapping[str, Path],
    render_variant: Optional[Mapping[str, Any]] = None,
) -> Path:
    backend = recipe["render"]["backend"]
    if backend == "blender":
        return _render_blender(recipe, capture, scene, paths, render_variant)
    if backend != "preview":
        raise RenderError("Unknown render backend: " + str(backend))
    return _render_preview(recipe, capture, scene, paths["image"])


def _render_blender(
    recipe: Mapping[str, Any],
    capture: Mapping[str, Any],
    scene: Mapping[str, Any],
    paths: Mapping[str, Path],
    render_variant: Optional[Mapping[str, Any]] = None,
) -> Path:
    executable = str(recipe["render"].get("executable", "blender"))
    resolved = _resolve_blender_executable(executable)
    if resolved is None:
        raise RenderError(
            "Blender executable not found: "
            + executable
            + ". Install Blender, add it to PATH, or set render.executable in the recipe."
        )

    image_path = paths["image"]
    script_path = paths["blender_script"]
    blend_path = paths["blend"]
    visible_defect_path = paths.get("visible_defect")
    pixel_scale_path = paths.get("pixel_scale")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    if visible_defect_path is not None:
        visible_defect_path.parent.mkdir(parents=True, exist_ok=True)
    if pixel_scale_path is not None:
        pixel_scale_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        build_blender_script(
            recipe,
            capture,
            scene,
            image_path,
            blend_path,
            visible_defect_path,
            render_variant,
            pixel_scale_path,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [resolved, "--background", "--factory-startup", "--python", str(script_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr + "\n" + result.stdout).strip()
        raise RenderError("Blender render failed: " + detail)
    if not image_path.exists() or image_path.stat().st_size == 0:
        raise RenderError("Blender completed but did not write a non-empty image: " + str(image_path))
    if visible_defect_path is not None and (
        not visible_defect_path.exists() or visible_defect_path.stat().st_size == 0
    ):
        raise RenderError("Blender completed but did not write visible-defect sidecar: " + str(visible_defect_path))
    if pixel_scale_path is not None and (
        not pixel_scale_path.exists() or pixel_scale_path.stat().st_size == 0
    ):
        raise RenderError("Blender completed but did not write pixel-scale sidecar: " + str(pixel_scale_path))
    return image_path


def _resolve_blender_executable(executable: str) -> Optional[str]:
    direct = Path(executable).expanduser()
    if direct.exists():
        return str(direct)
    on_path = shutil.which(executable)
    if on_path is not None:
        return on_path
    if executable == "blender":
        macos_app = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if macos_app.exists():
            return str(macos_app)
    return None


def build_blender_script(
    recipe: Mapping[str, Any],
    capture: Mapping[str, Any],
    scene: Mapping[str, Any],
    image_path: Path,
    blend_path: Optional[Path] = None,
    visible_defect_path: Optional[Path] = None,
    render_variant: Optional[Mapping[str, Any]] = None,
    pixel_scale_path: Optional[Path] = None,
) -> str:
    render_item = {
        "capture": capture,
        "image_path": str(image_path),
        "visible_defect_path": str(
            visible_defect_path if visible_defect_path is not None else image_path.with_suffix(".visible_defect.json")
        ),
        "render_variant": dict(render_variant) if render_variant is not None else None,
        "pixel_scale_path": str(pixel_scale_path if pixel_scale_path is not None else image_path.with_suffix(".pixel_scale.npz")),
        "write_truth": True,
    }
    return build_blender_batch_script(
        recipe,
        scene,
        [render_item],
        blend_path if blend_path is not None else image_path.with_suffix(".blend"),
    )


def build_blender_batch_script(
    recipe: Mapping[str, Any],
    scene: Mapping[str, Any],
    render_items: List[Mapping[str, Any]],
    blend_path: Path,
) -> str:
    payload = {
        "recipe": recipe,
        "scene": scene,
        "render_items": list(render_items),
        "blend_path": str(blend_path),
        "versioning": {
            "visible_defect_schema_version": VISIBLE_DEFECT_SCHEMA_VERSION,
            "pixel_scale_schema_version": PIXEL_SCALE_SCHEMA_VERSION,
        },
    }
    return BLENDER_SCRIPT_TEMPLATE.replace("__METRODEF3D_PAYLOAD__", json.dumps(payload, sort_keys=True))


def _render_preview(
    recipe: Mapping[str, Any],
    capture: Mapping[str, Any],
    scene: Mapping[str, Any],
    image_path: Path,
) -> Path:
    resolution = capture["camera"]["resolution"]
    width = int(resolution[0])
    height = int(resolution[1])
    surface = scene["surface"]
    defect = scene["defect"]
    surface_color = _hex_to_rgb(recipe["material"]["surface_color"])
    crack_color = _hex_to_rgb(recipe["material"]["crack_color"])
    pixels = [surface_color for _ in range(width * height)]

    bounds = _preview_bounds(capture["camera"], surface, width, height)
    points = []
    for point in defect["centerline"]:
        u = (point[0] - bounds["x_min"]) / (bounds["x_max"] - bounds["x_min"])
        v = (point[1] - bounds["y_min"]) / (bounds["y_max"] - bounds["y_min"])
        px = int(round(u * (width - 1)))
        py = int(round((1.0 - v) * (height - 1)))
        points.append((px, py))

    for left, right in zip(points, points[1:]):
        _draw_line(pixels, width, height, left, right, crack_color)

    image_path.parent.mkdir(parents=True, exist_ok=True)
    with image_path.open("w", encoding="ascii") as handle:
        handle.write("P3\n")
        handle.write(str(width) + " " + str(height) + "\n")
        handle.write("255\n")
        for offset, pixel in enumerate(pixels):
            handle.write("{} {} {}".format(pixel[0], pixel[1], pixel[2]))
            handle.write("\n" if (offset + 1) % width == 0 else " ")
    return image_path


def _safe_capture_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    return safe or "capture"


def _preview_bounds(camera: Mapping[str, Any], surface: Mapping[str, Any], width: int, height: int) -> Dict[str, float]:
    if camera["type"] != "orthographic":
        return dict(surface["bounds"])
    vertical = float(camera["orthographic_scale"])
    horizontal = vertical * (float(width) / float(height))
    target = camera["target"]
    return {
        "x_min": float(target[0]) - horizontal / 2.0,
        "x_max": float(target[0]) + horizontal / 2.0,
        "y_min": float(target[1]) - vertical / 2.0,
        "y_max": float(target[1]) + vertical / 2.0,
    }


def _draw_line(pixels, width, height, start, end, color) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        for nx in range(x0 - 1, x0 + 2):
            for ny in range(y0 - 1, y0 + 2):
                if 0 <= nx < width and 0 <= ny < height:
                    pixels[ny * width + nx] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _hex_to_rgb(value: str):
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise RenderError("Color must be a 6-digit hex value: " + value)
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError as exc:
        raise RenderError("Color must be a 6-digit hex value: " + value) from exc


BLENDER_SCRIPT_TEMPLATE = r'''
import json
import math
import random
import struct
import zipfile

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


PAYLOAD = json.loads("""__METRODEF3D_PAYLOAD__""")
RECIPE = PAYLOAD["recipe"]
SCENE = PAYLOAD["scene"]
RENDER_ITEMS = PAYLOAD["render_items"]
BLEND_PATH = PAYLOAD["blend_path"]
CAPTURE = RENDER_ITEMS[0]["capture"]
VERSIONING = PAYLOAD["versioning"]


def hex_to_rgba(value):
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    return (
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
        1.0,
    )


def make_material(name, color, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def make_debug_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = 0.4
    return mat


def interpolate_point(left, right, fraction):
    return [
        float(left[0]) + (float(right[0]) - float(left[0])) * fraction,
        float(left[1]) + (float(right[1]) - float(left[1])) * fraction,
        float(left[2]) + (float(right[2]) - float(left[2])) * fraction,
    ]


def interpolate_scalar(left, right, fraction):
    return float(left) + (float(right) - float(left)) * fraction


def polyline_length(points):
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += math.sqrt(
            (float(right[0]) - float(left[0])) ** 2
            + (float(right[1]) - float(left[1])) ** 2
            + (float(right[2]) - float(left[2])) ** 2
        )
    return total


def profile_area(points, widths):
    total = 0.0
    for index in range(len(points) - 1):
        segment_length = math.sqrt(
            (float(points[index + 1][0]) - float(points[index][0])) ** 2
            + (float(points[index + 1][1]) - float(points[index][1])) ** 2
            + (float(points[index + 1][2]) - float(points[index][2])) ** 2
        )
        total += segment_length * (float(widths[index]) + float(widths[index + 1])) / 2.0
    return total


def polygon_area_xy(points):
    if len(points) < 3:
        return 0.0
    total = 0.0
    for left, right in zip(points, points[1:] + points[:1]):
        total += float(left[0]) * float(right[1]) - float(right[0]) * float(left[1])
    return abs(total) * 0.5


def clip_unit_square_interval(left_uvz, right_uvz):
    if left_uvz[2] <= 0.0 and right_uvz[2] <= 0.0:
        return None
    start = 0.0
    end = 1.0
    dx = right_uvz[0] - left_uvz[0]
    dy = right_uvz[1] - left_uvz[1]
    dz = right_uvz[2] - left_uvz[2]
    for p, q in (
        (-dx, left_uvz[0]),
        (dx, 1.0 - left_uvz[0]),
        (-dy, left_uvz[1]),
        (dy, 1.0 - left_uvz[1]),
        (-dz, left_uvz[2]),
    ):
        if abs(p) < 1.0e-12:
            if q < 0.0:
                return None
            continue
        value = q / p
        if p < 0.0:
            if value > end:
                return None
            if value > start:
                start = value
        else:
            if value < start:
                return None
            if value < end:
                end = value
    if start > end:
        return None
    return (max(0.0, start), min(1.0, end))


def uv_inside(point, edge):
    u = float(point[0])
    v = float(point[1])
    if edge == "left":
        return u >= 0.0
    if edge == "right":
        return u <= 1.0
    if edge == "bottom":
        return v >= 0.0
    if edge == "top":
        return v <= 1.0
    return False


def uv_intersection(left, right, edge):
    lu, lv = float(left[0]), float(left[1])
    ru, rv = float(right[0]), float(right[1])
    du = ru - lu
    dv = rv - lv
    if edge == "left":
        fraction = 0.0 if abs(du) < 1.0e-12 else (0.0 - lu) / du
    elif edge == "right":
        fraction = 0.0 if abs(du) < 1.0e-12 else (1.0 - lu) / du
    elif edge == "bottom":
        fraction = 0.0 if abs(dv) < 1.0e-12 else (0.0 - lv) / dv
    else:
        fraction = 0.0 if abs(dv) < 1.0e-12 else (1.0 - lv) / dv
    fraction = max(0.0, min(1.0, fraction))
    return (
        lu + du * fraction,
        lv + dv * fraction,
        float(left[2]) + (float(right[2]) - float(left[2])) * fraction,
    )


def clip_uv_polygon_to_unit_square(points):
    clipped = list(points)
    for edge in ("left", "right", "bottom", "top"):
        if not clipped:
            return []
        output = []
        previous = clipped[-1]
        previous_inside = uv_inside(previous, edge)
        for current in clipped:
            current_inside = uv_inside(current, edge)
            if current_inside:
                if not previous_inside:
                    output.append(uv_intersection(previous, current, edge))
                output.append(current)
            elif previous_inside:
                output.append(uv_intersection(previous, current, edge))
            previous = current
            previous_inside = current_inside
        clipped = output
    return clipped


def dedupe_points(points):
    deduped = []
    for point in points:
        rounded = round_point(point)
        if not deduped or rounded != deduped[-1]:
            deduped.append(rounded)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped


def dedupe_pixel_points(points):
    deduped = []
    for point in points:
        rounded = [round(float(point[0]), 6), round(float(point[1]), 6)]
        if not deduped or rounded != deduped[-1]:
            deduped.append(rounded)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped


def round_point(point):
    return [round(float(point[0]), 6), round(float(point[1]), 6), round(float(point[2]), 6)]


def uv_to_pixel(uv, camera):
    width = int(camera["resolution"][0])
    height = int(camera["resolution"][1])
    return [round(float(uv[0]) * width, 6), round((1.0 - float(uv[1])) * height, 6)]


def segment_fraction_for_point(left, right, point):
    dx = float(right[0]) - float(left[0])
    dy = float(right[1]) - float(left[1])
    dz = float(right[2]) - float(left[2])
    denom = dx * dx + dy * dy + dz * dz
    if denom <= 1.0e-18:
        return 0.0
    fraction = (
        (float(point[0]) - float(left[0])) * dx
        + (float(point[1]) - float(left[1])) * dy
        + (float(point[2]) - float(left[2])) * dz
    ) / denom
    return max(0.0, min(1.0, fraction))


def append_visible_sample(samples, point, pixel, width, depth, left_boundary, right_boundary, left_pixel, right_pixel, source_index, fraction):
    rounded = round_point(point)
    if samples["centerline"] and rounded == samples["centerline"][-1]:
        samples["width_profile"][-1] = round(float(width), 6)
        samples["depth_profile"][-1] = round(float(depth), 6)
        samples["left_boundary"][-1] = round_point(left_boundary)
        samples["right_boundary"][-1] = round_point(right_boundary)
        samples["centerline_pixels"][-1] = [round(float(pixel[0]), 6), round(float(pixel[1]), 6)]
        samples["left_boundary_pixels"][-1] = [round(float(left_pixel[0]), 6), round(float(left_pixel[1]), 6)]
        samples["right_boundary_pixels"][-1] = [round(float(right_pixel[0]), 6), round(float(right_pixel[1]), 6)]
        samples["source_profile"][-1] = {
            "segment_index": int(source_index),
            "segment_fraction": round(float(fraction), 6),
        }
        return
    samples["centerline"].append(rounded)
    samples["width_profile"].append(round(float(width), 6))
    samples["depth_profile"].append(round(float(depth), 6))
    samples["left_boundary"].append(round_point(left_boundary))
    samples["right_boundary"].append(round_point(right_boundary))
    samples["centerline_pixels"].append([round(float(pixel[0]), 6), round(float(pixel[1]), 6)])
    samples["left_boundary_pixels"].append([round(float(left_pixel[0]), 6), round(float(left_pixel[1]), 6)])
    samples["right_boundary_pixels"].append([round(float(right_pixel[0]), 6), round(float(right_pixel[1]), 6)])
    samples["source_profile"].append(
        {
            "segment_index": int(source_index),
            "segment_fraction": round(float(fraction), 6),
        }
    )


def visible_polygon_from_blender_camera(scene, camera_obj, defect):
    left_boundary = defect.get("left_boundary", [])
    right_boundary = defect.get("right_boundary", [])
    if len(left_boundary) < 2 or len(right_boundary) < 2:
        return []
    polygon = list(left_boundary) + list(reversed(right_boundary))
    uv_polygon = []
    for point in polygon:
        uv = world_to_camera_view(scene, camera_obj, Vector((float(point[0]), float(point[1]), float(point[2]))))
        if float(uv.z) <= 0.0:
            continue
        uv_polygon.append((float(uv.x), float(uv.y), float(uv.z)))
    clipped_uv = clip_uv_polygon_to_unit_square(uv_polygon)
    visible_polygon = []
    visible_polygon_pixels = []
    for u, v, _z in clipped_uv:
        world = ray_plane_intersection(camera_obj, float(u), float(v), 0.0)
        if world is not None:
            visible_polygon.append([float(world.x), float(world.y), 0.0])
            visible_polygon_pixels.append(uv_to_pixel((u, v), {"resolution": [scene.render.resolution_x, scene.render.resolution_y]}))
    return dedupe_points(visible_polygon), dedupe_pixel_points(visible_polygon_pixels)


def visible_defect_from_blender_camera(scene, camera_obj, defect, camera):
    points = defect["centerline"]
    widths = defect["width_profile"]
    depths = defect["depth_profile"]
    left_boundary = defect.get("left_boundary", points)
    right_boundary = defect.get("right_boundary", points)
    samples = {
        "centerline": [],
        "width_profile": [],
        "depth_profile": [],
        "left_boundary": [],
        "right_boundary": [],
        "centerline_pixels": [],
        "left_boundary_pixels": [],
        "right_boundary_pixels": [],
        "source_profile": [],
    }

    for index in range(len(points) - 1):
        left = points[index]
        right = points[index + 1]
        left_uv = world_to_camera_view(scene, camera_obj, Vector((float(left[0]), float(left[1]), float(left[2]))))
        right_uv = world_to_camera_view(scene, camera_obj, Vector((float(right[0]), float(right[1]), float(right[2]))))
        interval = clip_unit_square_interval(
            (float(left_uv.x), float(left_uv.y), float(left_uv.z)),
            (float(right_uv.x), float(right_uv.y), float(right_uv.z)),
        )
        if interval is None:
            continue
        for uv_fraction in interval:
            clipped_uv = (
                float(left_uv.x) + (float(right_uv.x) - float(left_uv.x)) * uv_fraction,
                float(left_uv.y) + (float(right_uv.y) - float(left_uv.y)) * uv_fraction,
            )
            clipped_world = ray_plane_intersection(camera_obj, clipped_uv[0], clipped_uv[1], 0.0)
            if clipped_world is None:
                continue
            point = [float(clipped_world.x), float(clipped_world.y), float(clipped_world.z)]
            fraction = segment_fraction_for_point(left, right, point)
            left_boundary_point = interpolate_point(left_boundary[index], left_boundary[index + 1], fraction)
            right_boundary_point = interpolate_point(right_boundary[index], right_boundary[index + 1], fraction)
            left_boundary_uv = world_to_camera_view(
                scene,
                camera_obj,
                Vector((float(left_boundary_point[0]), float(left_boundary_point[1]), float(left_boundary_point[2]))),
            )
            right_boundary_uv = world_to_camera_view(
                scene,
                camera_obj,
                Vector((float(right_boundary_point[0]), float(right_boundary_point[1]), float(right_boundary_point[2]))),
            )
            append_visible_sample(
                samples,
                point,
                uv_to_pixel(clipped_uv, camera),
                interpolate_scalar(widths[index], widths[index + 1], fraction),
                interpolate_scalar(depths[index], depths[index + 1], fraction),
                left_boundary_point,
                right_boundary_point,
                uv_to_pixel((float(left_boundary_uv.x), float(left_boundary_uv.y)), camera),
                uv_to_pixel((float(right_boundary_uv.x), float(right_boundary_uv.y)), camera),
                index,
                fraction,
            )

    visible_polygon, visible_polygon_pixels = visible_polygon_from_blender_camera(scene, camera_obj, defect)
    visible = len(samples["centerline"]) >= 2
    centerline_length = polyline_length(samples["centerline"]) if visible else 0.0
    polygon_area = polygon_area_xy(visible_polygon)
    visible = visible or polygon_area > 0.0
    mean_width = polygon_area / centerline_length if centerline_length > 1.0e-9 else 0.0
    measurands = {
        "centerline_length": round(centerline_length, 6) if visible else 0.0,
        "max_width": round(max(samples["width_profile"]), 6) if visible else 0.0,
        "mean_width": round(mean_width, 6) if visible else 0.0,
        "max_depth": round(max(samples["depth_profile"]), 6) if visible else 0.0,
        "crack_area": round(polygon_area, 6) if visible else 0.0,
        "point_count": len(samples["centerline"]),
        "visible_polygon_point_count": len(visible_polygon),
    }
    return {
        "schema": {
            "name": "metrodef3d.visible_defect",
            "version": int(VERSIONING["visible_defect_schema_version"]),
        },
        "visible": visible,
        "clip_model": "blender_camera_view",
        "camera_type": camera["type"],
        "clip_fov_mm": camera.get("fov_mm", camera.get("orthographic_scale")),
        "centerline": samples["centerline"],
        "left_boundary": samples["left_boundary"],
        "right_boundary": samples["right_boundary"],
        "visible_polygon": visible_polygon,
        "centerline_pixels": samples["centerline_pixels"],
        "left_boundary_pixels": samples["left_boundary_pixels"],
        "right_boundary_pixels": samples["right_boundary_pixels"],
        "visible_polygon_pixels": visible_polygon_pixels,
        "width_profile": samples["width_profile"],
        "depth_profile": samples["depth_profile"],
        "source_profile": samples["source_profile"],
        "measurands": measurands,
    }


def write_visible_defect(path, scene, camera_obj, defect, camera):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(visible_defect_from_blender_camera(scene, camera_obj, defect, camera), handle, indent=2, sort_keys=True)
        handle.write("\n")


def npy_float32_bytes(values, shape):
    header = "{'descr': '<f4', 'fortran_order': False, 'shape': (" + str(shape[0]) + ", " + str(shape[1]) + "), }"
    header_bytes = header.encode("latin1")
    padding = 16 - ((10 + len(header_bytes) + 1) % 16)
    header_bytes = header_bytes + b" " * padding + b"\n"
    data = bytearray()
    for value in values:
        data.extend(struct.pack("<f", float(value)))
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header_bytes)) + header_bytes + bytes(data)


def npy_uint8_bytes(values, shape):
    header = "{'descr': '|u1', 'fortran_order': False, 'shape': (" + str(shape[0]) + ", " + str(shape[1]) + "), }"
    header_bytes = header.encode("latin1")
    padding = 16 - ((10 + len(header_bytes) + 1) % 16)
    header_bytes = header_bytes + b" " * padding + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header_bytes)) + header_bytes + bytes(values)


def camera_frame_point(camera_obj, u, v):
    frame = camera_obj.data.view_frame(scene=bpy.context.scene)
    top_right = frame[0]
    bottom_right = frame[1]
    bottom_left = frame[2]
    top_left = frame[3]
    bottom = bottom_left.lerp(bottom_right, u)
    top = top_left.lerp(top_right, u)
    return bottom.lerp(top, v)


def ray_plane_intersection(camera_obj, u, v, plane_z=0.0):
    frame_point = camera_frame_point(camera_obj, u, v)
    world_point = camera_obj.matrix_world @ frame_point
    if camera_obj.data.type == "ORTHO":
        origin = world_point
        direction = camera_obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    else:
        origin = camera_obj.matrix_world.translation
        direction = (world_point - origin).normalized()
    if abs(direction.z) < 1.0e-9:
        return None
    distance = (plane_z - origin.z) / direction.z
    if distance <= 0.0:
        return None
    return origin + direction * distance


def distance_or_nan(left, right):
    if left is None or right is None:
        return float("nan")
    return (right - left).length


def finite_values(values):
    return [value for value in values if math.isfinite(value)]


def summarize_scale(values):
    finite = finite_values(values)
    if not finite:
        return {"min": None, "max": None, "mean": None}
    return {
        "min": round(min(finite), 9),
        "max": round(max(finite), 9),
        "mean": round(sum(finite) / len(finite), 9),
    }


def write_nominal_surface_pixel_scale(path, scene, camera_obj, camera):
    width = int(camera["resolution"][0])
    height = int(camera["resolution"][1])
    scale_x = []
    scale_y = []
    valid = []
    for py in range(height):
        v_center = 1.0 - ((py + 0.5) / height)
        v_top = 1.0 - (py / height)
        v_bottom = 1.0 - ((py + 1.0) / height)
        for px in range(width):
            u_center = (px + 0.5) / width
            u_left = px / width
            u_right = (px + 1.0) / width
            center = ray_plane_intersection(camera_obj, u_center, v_center)
            left = ray_plane_intersection(camera_obj, u_left, v_center)
            right = ray_plane_intersection(camera_obj, u_right, v_center)
            top = ray_plane_intersection(camera_obj, u_center, v_top)
            bottom = ray_plane_intersection(camera_obj, u_center, v_bottom)
            scale_x.append(distance_or_nan(left, right))
            scale_y.append(distance_or_nan(top, bottom))
            valid.append(1 if center is not None and left is not None and right is not None and top is not None and bottom is not None else 0)
    summary = {
        "schema": {
            "name": "metrodef3d.pixel_scale",
            "version": int(VERSIONING["pixel_scale_schema_version"]),
        },
        "model": "camera_ray_to_nominal_z0_plane",
        "units": "mm_per_pixel",
        "plane": {"axis": "z", "value": 0.0},
        "resolution": [width, height],
        "camera_type": camera["type"],
        "scale_x_mm_per_px": summarize_scale(scale_x),
        "scale_y_mm_per_px": summarize_scale(scale_y),
        "valid_pixel_count": int(sum(valid)),
        "pixel_count": int(width * height),
        "arrays": {
            "scale_x_mm_per_px": {"file": "scale_x_mm_per_px.npy", "dtype": "float32", "shape": [height, width]},
            "scale_y_mm_per_px": {"file": "scale_y_mm_per_px.npy", "dtype": "float32", "shape": [height, width]},
            "valid_surface": {"file": "valid_surface.npy", "dtype": "uint8", "shape": [height, width]},
        },
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("scale_x_mm_per_px.npy", npy_float32_bytes(scale_x, (height, width)))
        archive.writestr("scale_y_mm_per_px.npy", npy_float32_bytes(scale_y, (height, width)))
        archive.writestr("valid_surface.npy", npy_uint8_bytes(valid, (height, width)))
        archive.writestr("summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")


def set_input(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value


def first_socket(sockets, names):
    for name in names:
        if name in sockets:
            return sockets[name]
    raise KeyError("None of the sockets exist: " + ", ".join(names))


def configure_cycles_gpu(render):
    if bpy.context.scene.render.engine != "CYCLES":
        return
    if not bool(render.get("use_gpu", True)):
        return
    bpy.context.scene.cycles.device = "GPU"
    preferences = bpy.context.preferences.addons.get("cycles")
    if preferences is None:
        print("METRODEF3D_GPU cycles add-on preferences unavailable")
        return
    cycles_preferences = preferences.preferences
    for compute_type in tuple(render.get("compute_device_type_order", ["OPTIX", "CUDA"])):
        try:
            cycles_preferences.compute_device_type = str(compute_type)
            cycles_preferences.get_devices()
        except Exception as exc:
            print("METRODEF3D_GPU device probe failed", compute_type, exc)
            continue
        enabled = []
        for device in cycles_preferences.devices:
            device.use = device.type != "CPU"
            if device.use:
                enabled.append(device.name + ":" + device.type)
        if enabled:
            print("METRODEF3D_GPU enabled", compute_type, ", ".join(enabled))
            return
    print("METRODEF3D_GPU no GPU device enabled; Cycles may use CPU")


def set_ramp(ramp_node, left_position, right_position, left_color=(0.0, 0.0, 0.0, 1.0), right_color=(1.0, 1.0, 1.0, 1.0)):
    ramp = ramp_node.color_ramp
    ramp.elements[0].position = left_position
    ramp.elements[0].color = left_color
    ramp.elements[1].position = right_position
    ramp.elements[1].color = right_color


def set_multi_ramp(ramp_node, stops):
    ramp = ramp_node.color_ramp
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < len(stops):
        ramp.elements.new(float(stops[len(ramp.elements)]["position"]))
    for index, stop in enumerate(stops):
        ramp.elements[index].position = float(stop["position"])
        ramp.elements[index].color = hex_to_rgba(str(stop["color"]))


def add_obfuscated_surface_texture(mat, material, seed, render_variant):
    if not render_variant:
        return False
    variant_type = str(render_variant.get("type", ""))
    if variant_type not in {"colorful_noise", "bw_noise"}:
        return False
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    output = nodes.get("Material Output")
    if bsdf is None or output is None:
        return False

    texture = render_variant.get("texture", {})
    rng = random.Random(seed + int(render_variant.get("seed_offset", 0)))
    bsdf.label = "white blemishes"
    bsdf.inputs["Roughness"].default_value = float(texture.get("roughness", 0.0))
    if "Diffuse Roughness" in bsdf.inputs:
        bsdf.inputs["Diffuse Roughness"].default_value = float(texture.get("diffuse_roughness", 1.0))
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = float(texture.get("coat_weight", 1.0))
    if "Coat Roughness" in bsdf.inputs:
        bsdf.inputs["Coat Roughness"].default_value = float(texture.get("coat_roughness", 0.36136364936828613))
    if "Coat IOR" in bsdf.inputs:
        bsdf.inputs["Coat IOR"].default_value = float(texture.get("coat_ior", 1.0))
    if "Coat Tint" in bsdf.inputs:
        bsdf.inputs["Coat Tint"].default_value = (0.6514633893966675, 0.6514633893966675, 0.6514633893966675, 1.0)

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-1100, 220)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-875, 220)
    if "Location" in mapping.inputs:
        mapping.inputs["Location"].default_value = (
            rng.uniform(-100.0, 100.0),
            rng.uniform(-100.0, 100.0),
            0.0,
        )
    if "Rotation" in mapping.inputs:
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, rng.uniform(0.0, math.tau))
    if "Scale" in mapping.inputs:
        mapping_scale = float(texture.get("mapping_scale", material.get("concrete_texture", {}).get("mapping_scale", 0.001)))
        mapping.inputs["Scale"].default_value = (mapping_scale, mapping_scale, mapping_scale)

    seed_node = nodes.new("ShaderNodeValue")
    seed_node.name = "Obfuscation SEED"
    seed_node.location = (-875, 440)
    seed_node.outputs["Value"].default_value = float(texture.get("seed_w", seed + int(render_variant.get("seed_offset", 0))))

    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "Obfuscation noise"
    noise.label = variant_type
    noise.location = (-630, 225)
    if hasattr(noise, "noise_dimensions"):
        noise.noise_dimensions = str(texture.get("noise_dimensions", "4D"))
    if hasattr(noise, "noise_type"):
        noise.noise_type = "FBM"
    if hasattr(noise, "normalize"):
        noise.normalize = bool(texture.get("noise_normalize", False))
    set_input(noise, "Scale", float(texture.get("noise_scale", 12.2)))
    set_input(noise, "Detail", float(texture.get("noise_detail", 15.0)))
    set_input(noise, "Roughness", float(texture.get("noise_roughness", 1.0)))
    set_input(noise, "Lacunarity", float(texture.get("noise_lacunarity", 2.0)))

    links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    if "W" in noise.inputs:
        links.new(seed_node.outputs["Value"], noise.inputs["W"])
    if variant_type == "colorful_noise":
        links.new(noise.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        links.new(first_socket(noise.outputs, ("Factor", "Fac")), bsdf.inputs["Base Color"])
    return True


def add_concrete_texture(mat, material, seed, render_variant=None):
    if material.get("texture_model", "concrete_noise") == "none":
        return
    if add_obfuscated_surface_texture(mat, material, seed, render_variant):
        return
    texture = material.get("concrete_texture", {})
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    output = nodes.get("Material Output")
    if bsdf is None or output is None:
        return

    rng = random.Random(seed)
    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-3015, 65)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-2760, 45)
    if "Location" in mapping.inputs:
        mapping.inputs["Location"].default_value = (
            rng.uniform(-100.0, 100.0),
            rng.uniform(-100.0, 100.0),
            0.0,
        )
    if "Rotation" in mapping.inputs:
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, rng.uniform(0.0, math.tau))
    if "Scale" in mapping.inputs:
        mapping_scale = float(texture.get("mapping_scale", 0.001))
        mapping.inputs["Scale"].default_value = (mapping_scale, mapping_scale, mapping_scale)

    seed_node = nodes.new("ShaderNodeValue")
    seed_node.name = "Value"
    seed_node.label = "SEED"
    seed_node.location = (-2780, 335)
    seed_node.outputs["Value"].default_value = float(texture.get("seed_w", seed))

    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "Concrete broad noise"
    noise.label = "concrete surface rough texture"
    noise.location = (-1220, 120)
    if hasattr(noise, "noise_dimensions"):
        noise.noise_dimensions = str(texture.get("noise_dimensions", "4D"))
    if hasattr(noise, "noise_type"):
        noise.noise_type = "FBM"
    if hasattr(noise, "normalize"):
        noise.normalize = bool(texture.get("noise_normalize", False))
    set_input(noise, "Scale", float(texture.get("noise_scale", 2.8)))
    set_input(noise, "Detail", float(texture.get("noise_detail", 15.0)))
    set_input(noise, "Roughness", float(texture.get("noise_roughness", 0.948)))
    set_input(noise, "Lacunarity", float(texture.get("noise_lacunarity", 2.0)))

    noise_ramp = nodes.new("ShaderNodeValToRGB")
    noise_ramp.name = "Concrete broad ramp"
    noise_ramp.location = (-980, 110)
    set_ramp(
        noise_ramp,
        float(texture.get("noise_ramp_black", 0.2704549)),
        float(texture.get("noise_ramp_white", 0.4886369)),
        hex_to_rgba(texture.get("noise_ramp_black_color", "#000000")),
        hex_to_rgba(texture.get("noise_ramp_white_color", "#ffffff")),
    )

    cloudy_noise = nodes.new("ShaderNodeTexNoise")
    cloudy_noise.name = "Concrete broad noise.001"
    cloudy_noise.label = "concrete surface cloudy texture"
    cloudy_noise.location = (-1220, -350)
    if hasattr(cloudy_noise, "noise_dimensions"):
        cloudy_noise.noise_dimensions = str(texture.get("cloudy_noise_dimensions", "4D"))
    if hasattr(cloudy_noise, "noise_type"):
        cloudy_noise.noise_type = "FBM"
    if hasattr(cloudy_noise, "normalize"):
        cloudy_noise.normalize = bool(texture.get("cloudy_noise_normalize", False))
    set_input(cloudy_noise, "Scale", float(texture.get("cloudy_noise_scale", 2.2)))
    set_input(cloudy_noise, "Detail", float(texture.get("cloudy_noise_detail", 11.4)))
    set_input(cloudy_noise, "Roughness", float(texture.get("cloudy_noise_roughness", 1.0)))
    set_input(cloudy_noise, "Lacunarity", float(texture.get("cloudy_noise_lacunarity", 2.0)))

    pore_noise_a = nodes.new("ShaderNodeTexNoise")
    pore_noise_a.name = "Concrete pore noise A"
    pore_noise_a.label = "dark blemishes"
    pore_noise_a.location = (-1220, 500)
    if hasattr(pore_noise_a, "noise_dimensions"):
        pore_noise_a.noise_dimensions = str(texture.get("pore_noise_dimensions", "4D"))
    if hasattr(pore_noise_a, "noise_type"):
        pore_noise_a.noise_type = "FBM"
    if hasattr(pore_noise_a, "normalize"):
        pore_noise_a.normalize = bool(texture.get("pore_noise_normalize", True))
    set_input(pore_noise_a, "Scale", float(texture.get("pore_noise_a_scale", 10.5)))
    set_input(pore_noise_a, "Detail", float(texture.get("pore_noise_a_detail", texture.get("pore_noise_detail", 0.3))))
    set_input(pore_noise_a, "Roughness", float(texture.get("pore_noise_roughness", 1.0)))
    set_input(pore_noise_a, "Lacunarity", float(texture.get("pore_noise_lacunarity", 2.0)))

    pore_noise_b = nodes.new("ShaderNodeTexNoise")
    pore_noise_b.name = "Concrete pore noise B"
    pore_noise_b.label = "bright blemishes"
    pore_noise_b.location = (-1220, 850)
    if hasattr(pore_noise_b, "noise_dimensions"):
        pore_noise_b.noise_dimensions = str(texture.get("pore_noise_dimensions", "4D"))
    if hasattr(pore_noise_b, "noise_type"):
        pore_noise_b.noise_type = "FBM"
    if hasattr(pore_noise_b, "normalize"):
        pore_noise_b.normalize = bool(texture.get("pore_noise_normalize", True))
    set_input(pore_noise_b, "Scale", float(texture.get("pore_noise_b_scale", 8.4)))
    set_input(pore_noise_b, "Detail", float(texture.get("pore_noise_b_detail", texture.get("pore_noise_detail", 0.2))))
    set_input(pore_noise_b, "Roughness", float(texture.get("pore_noise_roughness", 1.0)))
    set_input(pore_noise_b, "Lacunarity", float(texture.get("pore_noise_lacunarity", 2.0)))

    pore_ramp_a = nodes.new("ShaderNodeValToRGB")
    pore_ramp_a.name = "Concrete pore ramp A"
    pore_ramp_a.location = (-980, 500)
    set_ramp(
        pore_ramp_a,
        float(texture.get("pore_ramp_a_black", 0.28636387)),
        float(texture.get("pore_ramp_a_white", 0.30227369)),
        hex_to_rgba(texture.get("pore_ramp_a_black_color", "#000000")),
        hex_to_rgba(texture.get("pore_ramp_a_white_color", "#ffffff")),
    )

    pore_ramp_b = nodes.new("ShaderNodeValToRGB")
    pore_ramp_b.name = "Concrete pore ramp B"
    pore_ramp_b.location = (-980, 850)
    set_ramp(
        pore_ramp_b,
        float(texture.get("pore_ramp_b_white", 0.2840919)),
        float(texture.get("pore_ramp_b_black", 0.3113639)),
        hex_to_rgba(texture.get("pore_ramp_b_white_color", "#ffffff")),
        hex_to_rgba(texture.get("pore_ramp_b_black_color", "#000000")),
    )

    pore_mix = nodes.new("ShaderNodeMix")
    pore_mix.name = "Concrete pore mix"
    pore_mix.data_type = "FLOAT"
    pore_mix.location = (-500, 540)
    set_input(pore_mix, "Factor", float(texture.get("pore_mix_factor", 0.5)))
    final_mix = nodes.new("ShaderNodeMix")
    final_mix.name = "Concrete final mix"
    final_mix.data_type = "FLOAT"
    final_mix.location = (-360, 240)
    set_input(final_mix, "Factor", float(texture.get("final_mix_factor", 0.6625)))

    base_map = nodes.new("ShaderNodeMapRange")
    base_map.name = "Map Range"
    base_map.location = (40, 415)
    base_map.data_type = "FLOAT"
    base_map.clamp = True
    set_input(base_map, "From Min", float(texture.get("base_from_min", 0.0)))
    set_input(base_map, "From Max", float(texture.get("base_from_max", 1.0)))
    set_input(base_map, "To Min", float(texture.get("base_to_min", 0.0)))
    set_input(base_map, "To Max", float(texture.get("base_to_max", 0.6)))

    color_mix = None
    base_color_ramp = None
    if texture.get("base_color_model", "mix") == "ramp":
        base_color_ramp = nodes.new("ShaderNodeValToRGB")
        base_color_ramp.name = "Concrete base color ramp"
        base_color_ramp.location = (270, 500)
        set_multi_ramp(
            base_color_ramp,
            texture.get(
                "base_color_ramp",
                [
                    {"position": 0.0, "color": "#353433"},
                    {"position": 1.0, "color": "#9a8b88"},
                ],
            ),
        )
    else:
        color_mix = nodes.new("ShaderNodeMix")
        color_mix.name = "Mix"
        color_mix.data_type = "RGBA"
        color_mix.location = (272, 500)
        set_input(color_mix, "Factor", float(texture.get("base_color_mix_factor", 0.5)))
        if "B" in color_mix.inputs:
            color_mix.inputs["B"].default_value = hex_to_rgba(texture.get("base_mix_color", "#55524d"))

    cloudy_displacement = nodes.new("ShaderNodeMapRange")
    cloudy_displacement.name = "Map Range.001"
    cloudy_displacement.location = (-735, -225)
    cloudy_displacement.data_type = "FLOAT"
    cloudy_displacement.clamp = False
    set_input(cloudy_displacement, "From Min", 0.0)
    set_input(cloudy_displacement, "From Max", 1.0)
    set_input(cloudy_displacement, "To Min", 0.0)
    set_input(cloudy_displacement, "To Max", float(texture.get("cloudy_displacement_strength", 0.05)))

    pit_noise_coarse = nodes.new("ShaderNodeTexNoise")
    pit_noise_coarse.name = "Noise Texture"
    pit_noise_coarse.label = "coarse pitting"
    pit_noise_coarse.location = (-1245, -940)
    if hasattr(pit_noise_coarse, "noise_dimensions"):
        pit_noise_coarse.noise_dimensions = "4D"
    if hasattr(pit_noise_coarse, "noise_type"):
        pit_noise_coarse.noise_type = "FBM"
    if hasattr(pit_noise_coarse, "normalize"):
        pit_noise_coarse.normalize = False
    set_input(pit_noise_coarse, "Scale", float(texture.get("pitting_coarse_scale", 89.2)))
    set_input(pit_noise_coarse, "Detail", float(texture.get("pitting_coarse_detail", 15.0)))
    set_input(pit_noise_coarse, "Roughness", float(texture.get("pitting_coarse_roughness", 0.412)))

    pit_ramp_coarse = nodes.new("ShaderNodeValToRGB")
    pit_ramp_coarse.name = "Color Ramp"
    pit_ramp_coarse.location = (-1015, -920)
    set_ramp(pit_ramp_coarse, float(texture.get("pitting_coarse_ramp_black", 0.40454513)), 1.0)

    pit_map_coarse = nodes.new("ShaderNodeMapRange")
    pit_map_coarse.name = "Map Range.002"
    pit_map_coarse.location = (-685, -870)
    pit_map_coarse.data_type = "FLOAT"
    pit_map_coarse.clamp = False
    set_input(pit_map_coarse, "From Min", -1.0)
    set_input(pit_map_coarse, "From Max", 1.0)
    set_input(pit_map_coarse, "To Min", 0.0)
    set_input(pit_map_coarse, "To Max", float(texture.get("pitting_coarse_depth", -10.0)))

    pit_noise_fine = nodes.new("ShaderNodeTexNoise")
    pit_noise_fine.name = "Noise Texture.003"
    pit_noise_fine.label = "fine pitting"
    pit_noise_fine.location = (-960, -1295)
    if hasattr(pit_noise_fine, "noise_dimensions"):
        pit_noise_fine.noise_dimensions = "4D"
    if hasattr(pit_noise_fine, "noise_type"):
        pit_noise_fine.noise_type = "FBM"
    if hasattr(pit_noise_fine, "normalize"):
        pit_noise_fine.normalize = False
    set_input(pit_noise_fine, "Scale", float(texture.get("pitting_fine_scale", 880.0)))
    set_input(pit_noise_fine, "Detail", float(texture.get("pitting_fine_detail", 15.0)))
    set_input(pit_noise_fine, "Roughness", float(texture.get("pitting_fine_roughness", 0.272)))

    pit_ramp_fine = nodes.new("ShaderNodeValToRGB")
    pit_ramp_fine.name = "Color Ramp.002"
    pit_ramp_fine.location = (-730, -1275)
    set_ramp(pit_ramp_fine, float(texture.get("pitting_fine_ramp_black", 0.625)), 1.0)

    pit_map_fine = nodes.new("ShaderNodeMapRange")
    pit_map_fine.name = "Map Range.004"
    pit_map_fine.location = (-400, -1225)
    pit_map_fine.data_type = "FLOAT"
    pit_map_fine.clamp = False
    set_input(pit_map_fine, "From Min", -1.0)
    set_input(pit_map_fine, "From Max", 1.0)
    set_input(pit_map_fine, "To Min", 0.0)
    set_input(pit_map_fine, "To Max", float(texture.get("pitting_fine_depth", -5.0)))

    pit_noise_mod = nodes.new("ShaderNodeTexNoise")
    pit_noise_mod.name = "Noise Texture.001"
    pit_noise_mod.label = "pitting modulation"
    pit_noise_mod.location = (-345, -1600)
    if hasattr(pit_noise_mod, "noise_dimensions"):
        pit_noise_mod.noise_dimensions = "4D"
    if hasattr(pit_noise_mod, "noise_type"):
        pit_noise_mod.noise_type = "FBM"
    if hasattr(pit_noise_mod, "normalize"):
        pit_noise_mod.normalize = True
    set_input(pit_noise_mod, "Scale", float(texture.get("pitting_modulation_scale", 64.0)))
    set_input(pit_noise_mod, "Detail", float(texture.get("pitting_modulation_detail", 7.8)))
    set_input(pit_noise_mod, "Roughness", float(texture.get("pitting_modulation_roughness", 0.632)))

    pit_map_mod = nodes.new("ShaderNodeMapRange")
    pit_map_mod.name = "Map Range.003"
    pit_map_mod.location = (-125, -1490)
    pit_map_mod.data_type = "FLOAT"
    pit_map_mod.clamp = False
    set_input(pit_map_mod, "From Min", -1.0)
    set_input(pit_map_mod, "From Max", 1.0)
    set_input(pit_map_mod, "To Min", 0.0)
    set_input(pit_map_mod, "To Max", float(texture.get("pitting_modulation_strength", 0.7)))

    pit_sum = nodes.new("ShaderNodeMath")
    pit_sum.name = "Math.001"
    pit_sum.operation = "ADD"
    pit_sum.location = (-112, -885)
    displacement_pits = nodes.new("ShaderNodeMath")
    displacement_pits.name = "Math"
    displacement_pits.operation = "ADD"
    displacement_pits.location = (190, -875)
    displacement_total = nodes.new("ShaderNodeMath")
    displacement_total.name = "Math.002"
    displacement_total.operation = "ADD"
    displacement_total.location = (610, -70)
    bsdf.label = "white blemishes"

    links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(mapping.outputs["Vector"], pore_noise_a.inputs["Vector"])
    links.new(mapping.outputs["Vector"], pore_noise_b.inputs["Vector"])
    links.new(mapping.outputs["Vector"], cloudy_noise.inputs["Vector"])
    links.new(mapping.outputs["Vector"], pit_noise_coarse.inputs["Vector"])
    links.new(mapping.outputs["Vector"], pit_noise_fine.inputs["Vector"])
    links.new(mapping.outputs["Vector"], pit_noise_mod.inputs["Vector"])
    for node in (noise, cloudy_noise, pore_noise_a, pore_noise_b, pit_noise_coarse, pit_noise_fine, pit_noise_mod):
        if "W" in node.inputs:
            links.new(seed_node.outputs["Value"], node.inputs["W"])
    links.new(first_socket(noise.outputs, ("Factor", "Fac")), first_socket(noise_ramp.inputs, ("Factor", "Fac")))
    links.new(first_socket(pore_noise_a.outputs, ("Factor", "Fac")), first_socket(pore_ramp_a.inputs, ("Factor", "Fac")))
    links.new(first_socket(pore_noise_b.outputs, ("Factor", "Fac")), first_socket(pore_ramp_b.inputs, ("Factor", "Fac")))
    links.new(pore_ramp_b.outputs["Color"], pore_mix.inputs["A"])
    links.new(pore_ramp_a.outputs["Color"], pore_mix.inputs["B"])
    links.new(pore_mix.outputs["Result"], final_mix.inputs["A"])
    links.new(noise_ramp.outputs["Color"], final_mix.inputs["B"])
    links.new(final_mix.outputs["Result"], base_map.inputs["Value"])
    if base_color_ramp is not None:
        links.new(base_map.outputs["Result"], first_socket(base_color_ramp.inputs, ("Factor", "Fac")))
        links.new(base_color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        links.new(base_map.outputs["Result"], color_mix.inputs["A"])
        links.new(color_mix.outputs["Result"], bsdf.inputs["Base Color"])

    links.new(first_socket(cloudy_noise.outputs, ("Factor", "Fac")), cloudy_displacement.inputs["Value"])
    links.new(first_socket(pit_noise_coarse.outputs, ("Factor", "Fac")), first_socket(pit_ramp_coarse.inputs, ("Factor", "Fac")))
    links.new(pit_ramp_coarse.outputs["Color"], pit_map_coarse.inputs["Value"])
    links.new(first_socket(pit_noise_fine.outputs, ("Factor", "Fac")), first_socket(pit_ramp_fine.inputs, ("Factor", "Fac")))
    links.new(pit_ramp_fine.outputs["Color"], pit_map_fine.inputs["Value"])
    links.new(first_socket(pit_noise_mod.outputs, ("Factor", "Fac")), pit_map_mod.inputs["Value"])
    links.new(pit_map_coarse.outputs["Result"], pit_sum.inputs[0])
    links.new(pit_map_fine.outputs["Result"], pit_sum.inputs[1])
    links.new(pit_sum.outputs["Value"], displacement_pits.inputs[0])
    links.new(pit_map_mod.outputs["Result"], displacement_pits.inputs[1])
    links.new(displacement_pits.outputs["Value"], displacement_total.inputs[0])
    links.new(cloudy_displacement.outputs["Result"], displacement_total.inputs[1])
    links.new(displacement_total.outputs["Value"], output.inputs["Displacement"])

    if bool(texture.get("aggregate_enabled", False)):
        aggregate_voronoi = nodes.new("ShaderNodeTexVoronoi")
        aggregate_voronoi.name = "Aggregate Voronoi mask"
        aggregate_voronoi.label = "aggregate cells"
        aggregate_voronoi.location = (-1010, 1185)
        if hasattr(aggregate_voronoi, "voronoi_dimensions"):
            aggregate_voronoi.voronoi_dimensions = "4D"
        if hasattr(aggregate_voronoi, "feature"):
            aggregate_voronoi.feature = "F1"
        set_input(aggregate_voronoi, "Scale", float(texture.get("aggregate_scale", 24.0)))
        set_input(aggregate_voronoi, "Randomness", float(texture.get("aggregate_randomness", 1.0)))

        aggregate_ramp = nodes.new("ShaderNodeValToRGB")
        aggregate_ramp.name = "Aggregate mask ramp"
        aggregate_ramp.location = (-765, 1185)
        set_ramp(
            aggregate_ramp,
            float(texture.get("aggregate_ramp_black", 0.50)),
            float(texture.get("aggregate_ramp_white", 0.56)),
        )

        aggregate_bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        aggregate_bsdf.name = "Aggregate stone Principled"
        aggregate_bsdf.location = (660, 965)
        aggregate_bsdf.inputs["Base Color"].default_value = hex_to_rgba(texture.get("aggregate_color", "#8c887d"))
        aggregate_bsdf.inputs["Roughness"].default_value = float(texture.get("aggregate_roughness", 0.72))

        aggregate_mix = nodes.new("ShaderNodeMixShader")
        aggregate_mix.name = "Concrete aggregate material mix"
        aggregate_mix.location = (925, 450)

        links.new(mapping.outputs["Vector"], aggregate_voronoi.inputs["Vector"])
        if "W" in aggregate_voronoi.inputs:
            links.new(seed_node.outputs["Value"], aggregate_voronoi.inputs["W"])
        links.new(aggregate_voronoi.outputs["Color"], first_socket(aggregate_ramp.inputs, ("Factor", "Fac")))
        links.new(aggregate_ramp.outputs["Color"], aggregate_mix.inputs["Fac"])
        links.new(bsdf.outputs["BSDF"], aggregate_mix.inputs[1])
        links.new(aggregate_bsdf.outputs["BSDF"], aggregate_mix.inputs[2])
        for link in list(output.inputs["Surface"].links):
            links.remove(link)
        links.new(aggregate_mix.outputs["Shader"], output.inputs["Surface"])


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def tangent_normal(points, index):
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


def segment_direction(points, index):
    dx = points[index + 1][0] - points[index][0]
    dy = points[index + 1][1] - points[index][1]
    length = math.sqrt(dx * dx + dy * dy) or 1.0
    return (dx / length, dy / length)


def line_intersection_2d(point_a, dir_a, point_b, dir_b):
    denominator = dir_a[0] * dir_b[1] - dir_a[1] * dir_b[0]
    if abs(denominator) < 1.0e-8:
        return None
    delta = (point_b[0] - point_a[0], point_b[1] - point_a[1])
    t = (delta[0] * dir_b[1] - delta[1] * dir_b[0]) / denominator
    return (point_a[0] + dir_a[0] * t, point_a[1] + dir_a[1] * t, 0.0)


def offset_polyline_edge(points, offsets, side_sign, miter_limit=2.25):
    edge = []
    count = len(points)
    for index, point in enumerate(points):
        offset = max(float(offsets[index]), 0.0)
        if offset <= 0.0:
            edge.append((point[0], point[1], float(point[2])))
            continue
        if index == 0 or index == count - 1:
            nx, ny = tangent_normal(points, index)
            edge.append((point[0] + side_sign * nx * offset, point[1] + side_sign * ny * offset, float(point[2])))
            continue
        prev_dir = segment_direction(points, index - 1)
        next_dir = segment_direction(points, index)
        prev_normal = (-prev_dir[1] * side_sign, prev_dir[0] * side_sign)
        next_normal = (-next_dir[1] * side_sign, next_dir[0] * side_sign)
        prev_point = (point[0] + prev_normal[0] * offset, point[1] + prev_normal[1] * offset)
        next_point = (point[0] + next_normal[0] * offset, point[1] + next_normal[1] * offset)
        joined = line_intersection_2d(prev_point, prev_dir, next_point, next_dir)
        if joined is None:
            nx = prev_normal[0] + next_normal[0]
            ny = prev_normal[1] + next_normal[1]
            normal_length = math.sqrt(nx * nx + ny * ny) or 1.0
            joined = (point[0] + nx / normal_length * offset, point[1] + ny / normal_length * offset, float(point[2]))
        miter_dx = joined[0] - point[0]
        miter_dy = joined[1] - point[1]
        miter_length = math.sqrt(miter_dx * miter_dx + miter_dy * miter_dy)
        max_miter = max(offset * miter_limit, offset + 0.35)
        if miter_length > max_miter:
            scale = max_miter / miter_length
            joined = (point[0] + miter_dx * scale, point[1] + miter_dy * scale, float(point[2]))
        edge.append(joined)
    return edge


def almost_same_2d(left, right, epsilon=1.0e-5):
    return abs(left[0] - right[0]) <= epsilon and abs(left[1] - right[1]) <= epsilon


def clip_segment_to_rect(start, end, bounds):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    t0 = 0.0
    t1 = 1.0
    for p, q in (
        (-dx, start[0] - bounds["x_min"]),
        (dx, bounds["x_max"] - start[0]),
        (-dy, start[1] - bounds["y_min"]),
        (dy, bounds["y_max"] - start[1]),
    ):
        if abs(p) < 1.0e-12:
            if q < 0.0:
                return None
            continue
        r = q / p
        if p < 0.0:
            if r > t1:
                return None
            if r > t0:
                t0 = r
        else:
            if r < t0:
                return None
            if r < t1:
                t1 = r
    return (
        (start[0] + t0 * dx, start[1] + t0 * dy, 0.0),
        (start[0] + t1 * dx, start[1] + t1 * dy, 0.0),
    )


def clip_polyline_to_rect(points, bounds):
    clipped = []
    for start, end in zip(points, points[1:]):
        segment = clip_segment_to_rect(start, end, bounds)
        if segment is None:
            continue
        for point in segment:
            if not clipped or not almost_same_2d(clipped[-1], point):
                clipped.append(point)
    return clipped


def clamp_to_boundary(point, bounds):
    x = min(max(point[0], bounds["x_min"]), bounds["x_max"])
    y = min(max(point[1], bounds["y_min"]), bounds["y_max"])
    candidates = [
        (abs(x - bounds["x_min"]), bounds["x_min"], y),
        (abs(x - bounds["x_max"]), bounds["x_max"], y),
        (abs(y - bounds["y_min"]), x, bounds["y_min"]),
        (abs(y - bounds["y_max"]), x, bounds["y_max"]),
    ]
    _distance, bx, by = min(candidates, key=lambda item: item[0])
    return (bx, by, 0.0)


def perimeter_distance(point, bounds):
    x, y = point[0], point[1]
    width = bounds["x_max"] - bounds["x_min"]
    height = bounds["y_max"] - bounds["y_min"]
    if abs(y - bounds["y_min"]) <= 1.0e-4:
        return x - bounds["x_min"]
    if abs(x - bounds["x_max"]) <= 1.0e-4:
        return width + (y - bounds["y_min"])
    if abs(y - bounds["y_max"]) <= 1.0e-4:
        return width + height + (bounds["x_max"] - x)
    return 2.0 * width + height + (bounds["y_max"] - y)


def boundary_path_ccw(start, end, bounds):
    width = bounds["x_max"] - bounds["x_min"]
    height = bounds["y_max"] - bounds["y_min"]
    perimeter = 2.0 * (width + height)
    start = clamp_to_boundary(start, bounds)
    end = clamp_to_boundary(end, bounds)
    start_d = perimeter_distance(start, bounds)
    end_d = perimeter_distance(end, bounds)
    corners = [
        (width, (bounds["x_max"], bounds["y_min"], 0.0)),
        (width + height, (bounds["x_max"], bounds["y_max"], 0.0)),
        (2.0 * width + height, (bounds["x_min"], bounds["y_max"], 0.0)),
        (perimeter, (bounds["x_min"], bounds["y_min"], 0.0)),
    ]
    if end_d <= start_d:
        end_d += perimeter
    adjusted = []
    for distance, corner in corners:
        if distance <= start_d:
            distance += perimeter
        adjusted.append((distance, corner))
    adjusted.sort(key=lambda item: item[0])
    path = [start]
    for distance, corner in adjusted:
        if start_d < distance < end_d and not almost_same_2d(path[-1], corner):
            path.append(corner)
    if not almost_same_2d(path[-1], end):
        path.append(end)
    return path


def remove_duplicate_polygon_points(points):
    cleaned = []
    for point in points:
        if not cleaned or not almost_same_2d(cleaned[-1], point):
            cleaned.append(point)
    if len(cleaned) > 1 and almost_same_2d(cleaned[0], cleaned[-1]):
        cleaned.pop()
    return cleaned


def simplify_polygon_points(points, tolerance=0.001):
    cleaned = remove_duplicate_polygon_points(points)
    if len(cleaned) < 4:
        return cleaned
    changed = True
    while changed and len(cleaned) >= 4:
        changed = False
        simplified = []
        count = len(cleaned)
        for index, point in enumerate(cleaned):
            previous = cleaned[(index - 1) % count]
            following = cleaned[(index + 1) % count]
            area = abs(
                (point[0] - previous[0]) * (following[1] - previous[1])
                - (point[1] - previous[1]) * (following[0] - previous[0])
            )
            base = math.hypot(following[0] - previous[0], following[1] - previous[1])
            distance = area / base if base > 1.0e-12 else 0.0
            if distance <= tolerance and len(cleaned) - 1 >= 3:
                changed = True
                continue
            simplified.append(point)
        cleaned = simplified
    return cleaned


def polygon_signed_area(points):
    area = 0.0
    for left, right in zip(points, points[1:] + points[:1]):
        area += left[0] * right[1] - right[0] * left[1]
    return area / 2.0


def make_solid_from_top_polygon(name, top_polygon, block_depth, material):
    top_polygon = simplify_polygon_points(top_polygon)
    if len(top_polygon) < 3:
        raise ValueError("Cannot create split body with fewer than 3 top vertices.")
    if polygon_signed_area(top_polygon) < 0.0:
        top_polygon = list(reversed(top_polygon))
    top = [(point[0], point[1], 0.0) for point in top_polygon]
    bottom = [(point[0], point[1], -block_depth) for point in top_polygon]
    verts = top + bottom
    count = len(top)
    faces = []
    for tri in tessellate_polygon([[Vector(co) for co in top]]):
        faces.append(tuple(tri))
    bottom_indices = list(reversed(range(count, count * 2)))
    for tri in tessellate_polygon([[Vector(co) for co in reversed(bottom)]]):
        faces.append(tuple(bottom_indices[index] for index in tri))
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    bpy.context.collection.objects.link(obj)
    return obj


def make_block_with_crack_hole(name, bounds, crack_boundary, block_depth, material):
    crack_boundary = remove_duplicate_polygon_points(crack_boundary)
    if len(crack_boundary) < 3:
        raise ValueError("Cannot create crack cut with fewer than 3 boundary vertices.")
    if polygon_signed_area(crack_boundary) > 0.0:
        crack_boundary = list(reversed(crack_boundary))

    outer_top = [
        (bounds["x_min"], bounds["y_min"], 0.0),
        (bounds["x_max"], bounds["y_min"], 0.0),
        (bounds["x_max"], bounds["y_max"], 0.0),
        (bounds["x_min"], bounds["y_max"], 0.0),
    ]
    hole_top = [(point[0], point[1], 0.0) for point in crack_boundary]
    outer_bottom = [(x, y, -block_depth) for x, y, _z in outer_top]
    hole_bottom = [(x, y, -block_depth) for x, y, _z in hole_top]

    verts = outer_top + hole_top + outer_bottom + hole_bottom
    outer_count = len(outer_top)
    hole_count = len(hole_top)
    bottom_outer_offset = outer_count + hole_count
    bottom_hole_offset = bottom_outer_offset + outer_count

    faces = []
    for tri in tessellate_polygon([[Vector(co) for co in outer_top], [Vector(co) for co in hole_top]]):
        faces.append(tuple(tri))

    bottom_outer_loop = list(reversed(outer_bottom))
    bottom_hole_loop = list(reversed(hole_bottom))
    bottom_index_loop = list(reversed(range(bottom_outer_offset, bottom_outer_offset + outer_count)))
    bottom_hole_index_loop = list(reversed(range(bottom_hole_offset, bottom_hole_offset + hole_count)))
    bottom_lookup = bottom_index_loop + bottom_hole_index_loop
    for tri in tessellate_polygon([[Vector(co) for co in bottom_outer_loop], [Vector(co) for co in bottom_hole_loop]]):
        faces.append(tuple(bottom_lookup[index] for index in tri))

    for index in range(outer_count):
        next_index = (index + 1) % outer_count
        faces.append((index, next_index, bottom_outer_offset + next_index, bottom_outer_offset + index))

    for index in range(hole_count):
        next_index = (index + 1) % hole_count
        faces.append(
            (
                outer_count + index,
                outer_count + next_index,
                bottom_hole_offset + next_index,
                bottom_hole_offset + index,
            )
        )

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    obj["metrodef3d_construction"] = "explicit_ribbon_crack_hole"
    bpy.context.collection.objects.link(obj)
    return obj


def create_centerline_split_bodies(points, bounds, block_depth, material):
    split_line = clip_polyline_to_rect(points, bounds)
    if len(split_line) < 2:
        raise ValueError("Split centerline does not cross the slab.")
    start = split_line[0]
    end = split_line[-1]
    left_polygon = split_line + boundary_path_ccw(end, start, bounds)[1:]
    right_polygon = list(reversed(split_line)) + boundary_path_ccw(start, end, bounds)[1:]
    return [
        make_solid_from_top_polygon("known_cracked_surface_body_left", left_polygon, block_depth, material),
        make_solid_from_top_polygon("known_cracked_surface_body_right", right_polygon, block_depth, material),
    ]


def add_crack_debris(points, widths, material, render):
    detail = render.get("render_detail", {}).get("crack_debris", {})
    if not detail.get("enabled", False) or len(points) < 2:
        return []
    rng = random.Random(int(defect["seed"]) ^ 0x6D657472)
    if rng.random() > float(detail.get("probability", 0.75)):
        return []

    length = 0.0
    cumulative = [0.0]
    for left, right in zip(points, points[1:]):
        length += math.hypot(float(right[0]) - float(left[0]), float(right[1]) - float(left[1]))
        cumulative.append(length)
    if length <= 0.0:
        return []

    count_range = detail.get("count_per_100mm_range", [4.0, 16.0])
    target_count = int(round(length / 100.0 * rng.uniform(float(count_range[0]), float(count_range[1]))))
    depth_range = detail.get("depth_range", [0.25, 3.0])
    size_range = detail.get("size_range", [0.12, 1.4])
    vertex_count_range = detail.get("vertex_count_range", [5, 9])
    width_fraction_max = float(detail.get("width_fraction_max", 0.8))

    created = []
    for debris_index in range(max(0, target_count)):
        for _attempt in range(30):
            station = rng.uniform(0.0, length)
            segment_index = 0
            while segment_index < len(cumulative) - 2 and cumulative[segment_index + 1] < station:
                segment_index += 1
            left = points[segment_index]
            right = points[segment_index + 1]
            segment_length = max(cumulative[segment_index + 1] - cumulative[segment_index], 1.0e-9)
            fraction = (station - cumulative[segment_index]) / segment_length
            x = float(left[0]) + (float(right[0]) - float(left[0])) * fraction
            y = float(left[1]) + (float(right[1]) - float(left[1])) * fraction
            width = interpolate_profile(widths, station / length)
            if width < 0.18:
                continue
            tangent_x = float(right[0]) - float(left[0])
            tangent_y = float(right[1]) - float(left[1])
            tangent_length = math.hypot(tangent_x, tangent_y) or 1.0
            normal_x = -tangent_y / tangent_length
            normal_y = tangent_x / tangent_length
            lateral = rng.uniform(-0.35, 0.35) * width
            center_x = x + normal_x * lateral
            center_y = y + normal_y * lateral
            max_size = min(float(size_range[1]), max(0.03, width * width_fraction_max))
            min_size = min(float(size_range[0]), max_size)
            radius = rng.uniform(min_size, max_size)
            z = -rng.uniform(float(depth_range[0]), float(depth_range[1]))
            vertex_count = rng.randint(int(vertex_count_range[0]), int(vertex_count_range[1]))
            verts = []
            for vertex_index in range(vertex_count):
                angle = math.tau * float(vertex_index) / float(vertex_count) + rng.uniform(-0.18, 0.18)
                local_radius = radius * rng.uniform(0.45, 1.0)
                along = math.cos(angle) * local_radius
                across = math.sin(angle) * local_radius * rng.uniform(0.35, 0.85)
                verts.append(
                    (
                        center_x + tangent_x / tangent_length * along + normal_x * across,
                        center_y + tangent_y / tangent_length * along + normal_y * across,
                        z + rng.uniform(-0.08, 0.08),
                    )
                )
            mesh = bpy.data.meshes.new("render_only_crack_debris_mesh_" + str(debris_index + 1))
            mesh.from_pydata(verts, [], [tuple(range(vertex_count))])
            mesh.update()
            obj = bpy.data.objects.new("render_only_crack_debris_" + str(debris_index + 1), mesh)
            obj.data.materials.append(material)
            obj["metrodef3d_truth_affecting"] = False
            obj["metrodef3d_render_role"] = "subsurface_crack_debris"
            bpy.context.collection.objects.link(obj)
            created.append(obj)
            break
    return created


def add_crack_edge_falloff(points, left_boundary, right_boundary, widths, material, render):
    detail = render.get("render_detail", {}).get("crack_edge_falloff", {})
    if not detail.get("enabled", False) or len(points) < 2:
        return []
    if not left_boundary or not right_boundary:
        return []
    count = min(len(points), len(left_boundary), len(right_boundary), len(widths))
    if count < 2:
        return []

    rng = random.Random(int(defect["seed"]) ^ 0x66616C6C)
    min_fraction = float(detail.get("min_width_fraction", 0.015))
    max_fraction = float(detail.get("max_width_fraction", 0.10))
    if max_fraction <= 0.0:
        return []
    if min_fraction > max_fraction:
        min_fraction = max_fraction
    depth_multiplier = float(detail.get("depth_multiplier", 1.35))
    roughness = float(detail.get("roughness", 0.45))
    coarse_period = max(float(detail.get("coarse_period_mm", 24.0)), 0.001)
    fine_period = max(float(detail.get("fine_period_mm", 4.5)), 0.001)
    lateral_jitter_fraction = float(detail.get("lateral_jitter_fraction", 0.35))

    length = 0.0
    cumulative = [0.0]
    for left, right in zip(points, points[1:]):
        length += math.hypot(float(right[0]) - float(left[0]), float(right[1]) - float(left[1]))
        cumulative.append(length)
    if length <= 0.0:
        return []

    phases = [rng.uniform(0.0, math.tau) for _ in range(4)]

    def modulation(station):
        coarse = math.sin(math.tau * station / coarse_period + phases[0])
        coarse += 0.45 * math.sin(math.tau * station / (coarse_period * 0.47) + phases[1])
        fine = math.sin(math.tau * station / fine_period + phases[2])
        fine += 0.35 * math.sin(math.tau * station / (fine_period * 0.41) + phases[3])
        value = 0.5 + 0.28 * coarse + 0.15 * fine
        return max(0.0, min(1.0, value))

    created = []
    for side_name, boundary in (("left", left_boundary), ("right", right_boundary)):
        top_verts = []
        lower_verts = []
        for index in range(count):
            point = points[index]
            edge = boundary[index]
            width = max(float(widths[index]), 0.0)
            top_x = float(edge[0])
            top_y = float(edge[1])
            center_x = float(point[0])
            center_y = float(point[1])
            inward_x = center_x - top_x
            inward_y = center_y - top_y
            inward_len = math.hypot(inward_x, inward_y)
            if inward_len <= 1.0e-9:
                if index < count - 1:
                    tx = float(points[index + 1][0]) - center_x
                    ty = float(points[index + 1][1]) - center_y
                else:
                    tx = center_x - float(points[index - 1][0])
                    ty = center_y - float(points[index - 1][1])
                tangent_len = math.hypot(tx, ty) or 1.0
                normal_x = -ty / tangent_len
                normal_y = tx / tangent_len
                sign = 1.0 if side_name == "left" else -1.0
                inward_x = -normal_x * sign
                inward_y = -normal_y * sign
                inward_len = 1.0
            inward_x /= inward_len
            inward_y /= inward_len

            local = modulation(cumulative[index])
            radius = width * (min_fraction + (max_fraction - min_fraction) * local)
            jitter = radius * lateral_jitter_fraction * roughness * rng.uniform(-1.0, 1.0)
            depth = max(0.015, radius * depth_multiplier * rng.uniform(0.75, 1.35))
            top_verts.append((top_x, top_y, 0.0))
            lower_verts.append(
                (
                    top_x + inward_x * max(0.0, radius + jitter),
                    top_y + inward_y * max(0.0, radius + jitter),
                    -depth,
                )
            )

        verts = top_verts + lower_verts
        faces = []
        for index in range(count - 1):
            faces.append((index, index + 1, count + index + 1, count + index))
        mesh = bpy.data.meshes.new("render_only_crack_edge_falloff_" + side_name + "_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new("render_only_crack_edge_falloff_" + side_name, mesh)
        obj.data.materials.append(material)
        obj["metrodef3d_truth_affecting"] = False
        obj["metrodef3d_render_role"] = "subsurface_crack_edge_falloff"
        obj["metrodef3d_max_width_fraction"] = max_fraction
        bpy.context.collection.objects.link(obj)
        created.append(obj)
    return created


def cleanup_boolean_slab(obj, block_depth):
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    above_surface_faces = [face for face in bm.faces if face.calc_center_median().z > 1.0e-6]
    if above_surface_faces:
        bmesh.ops.delete(bm, geom=above_surface_faces, context="FACES")
    for vert in bm.verts:
        if vert.co.z > 0.0:
            vert.co.z = 0.0
        elif vert.co.z < -block_depth:
            vert.co.z = -block_depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def separate_loose_crack_bodies(obj, material):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = [part for part in bpy.context.selected_objects if part.type == "MESH"]
    parts.sort(key=lambda part: part.location.x)
    if len(parts) < 2:
        obj.name = "known_cracked_surface_block_unsplit"
        return parts
    for index, part in enumerate(parts):
        part.name = "known_cracked_surface_body_" + ("left" if index == 0 else "right" if index == len(parts) - 1 else str(index + 1))
        part.data.name = part.name + "_mesh"
        if len(part.data.materials) == 0:
            part.data.materials.append(material)
    return parts


def average_crack_normal(points):
    start = points[0]
    end = points[-1]
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.sqrt(dx * dx + dy * dy) or 1.0
    return (-dy / length, dx / length)


def interpolate_profile(profile, fraction):
    if not profile:
        return 0.0
    if len(profile) == 1:
        return float(profile[0])
    position = max(0.0, min(1.0, fraction)) * float(len(profile) - 1)
    left_index = int(math.floor(position))
    right_index = min(left_index + 1, len(profile) - 1)
    local = position - float(left_index)
    return float(profile[left_index]) + (float(profile[right_index]) - float(profile[left_index])) * local


def station_fraction_from_average_tangent(point, points):
    start = points[0]
    end = points[-1]
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-12:
        return 0.0
    projection = (float(point.x) - float(start[0])) * dx + (float(point.y) - float(start[1])) * dy
    return max(0.0, min(1.0, projection / length_sq))


def apply_hinged_split_profile(parts, points, width_profile, vertical_offset):
    if len(parts) < 2:
        return
    nx, ny = average_crack_normal(points)
    for part in parts:
        if part.name.endswith("_left"):
            part_sign = 1.0
        elif part.name.endswith("_right"):
            part_sign = -1.0
        else:
            part_sign = 1.0
        for vertex in part.data.vertices:
            fraction = station_fraction_from_average_tangent(vertex.co, points)
            half_width = interpolate_profile(width_profile, fraction) / 2.0
            vertex.co.x += nx * part_sign * half_width
            vertex.co.y += ny * part_sign * half_width
            vertex.co.z += float(vertical_offset) / 2.0 * part_sign * fraction
        part.data.update()
        part["metrodef3d_split_moving_side"] = "both"
        part["metrodef3d_hinged_profile"] = True
        part["metrodef3d_max_opening_mm"] = max(float(value) for value in width_profile) if width_profile else 0.0


def move_split_body(parts, points, moving_side, offset, vertical_offset, width_profile=None, opening_model=None):
    if len(parts) < 2 or offset == 0.0:
        return
    if opening_model == "surface_split_hinged_symmetric":
        apply_hinged_split_profile(parts, points, width_profile or [], vertical_offset)
        return
    nx, ny = average_crack_normal(points)
    half_offset = float(offset) / 2.0
    sign = 1.0 if moving_side == "left" else -1.0
    center_x = sum(float(point[0]) for point in points) / float(len(points))
    center_y = sum(float(point[1]) for point in points) / float(len(points))
    if moving_side == "both":
        for part in parts:
            if part.name.endswith("_left"):
                part_sign = 1.0
            elif part.name.endswith("_right"):
                part_sign = -1.0
            else:
                local_center = sum((Vector(corner) for corner in part.bound_box), Vector()) / 8.0
                world_center = part.matrix_world @ local_center
                projection = (world_center.x - center_x) * nx + (world_center.y - center_y) * ny
                part_sign = 1.0 if projection >= 0.0 else -1.0
            part.location.x += nx * part_sign * half_offset
            part.location.y += ny * part_sign * half_offset
            part.location.z += float(vertical_offset) / 2.0 * part_sign
            part["metrodef3d_split_moving_side"] = "both"
            part["metrodef3d_rigid_offset_mm"] = float(offset)
            part["metrodef3d_half_offset_mm"] = half_offset
        return
    selected = None
    selected_projection = None
    for part in parts:
        local_center = sum((Vector(corner) for corner in part.bound_box), Vector()) / 8.0
        world_center = part.matrix_world @ local_center
        projection = (world_center.x - center_x) * nx + (world_center.y - center_y) * ny
        if selected is None or projection * sign > selected_projection * sign:
            selected = part
            selected_projection = projection
    if selected is not None:
        selected.location.x += nx * sign * float(offset)
        selected.location.y += ny * sign * float(offset)
        selected.location.z += float(vertical_offset)
        selected["metrodef3d_split_moving_side"] = moving_side
        selected["metrodef3d_rigid_offset_mm"] = float(offset)


def add_lighting(lighting):
    if lighting["type"] == "multi":
        for index, light in enumerate(lighting["lights"]):
            add_single_light(light, str(index + 1))
        for index, occluder in enumerate(lighting.get("shadow_occluders", [])):
            add_shadow_occluder(occluder, str(index + 1))
    else:
        add_single_light(lighting, "1")


def add_single_light(lighting, suffix):
    light_type = lighting["type"]
    if light_type == "area":
        bpy.ops.object.light_add(type="AREA", location=lighting["position"])
        light = bpy.context.object
        light.name = "configured_area_light_" + suffix
        shape = str(lighting.get("shape", "square")).upper()
        if shape in {"RECTANGLE", "ELLIPSE"}:
            light.data.shape = shape
            light.data.size_y = float(lighting.get("size_y", lighting["size"]))
        else:
            light.data.shape = shape if shape in {"SQUARE", "DISK"} else "SQUARE"
        light.data.energy = float(lighting["energy"])
        light.data.size = float(lighting["size"])
    elif light_type == "sun":
        bpy.ops.object.light_add(type="SUN", location=lighting.get("position", [0.0, 0.0, 500.0]))
        light = bpy.context.object
        light.name = "configured_sun_light_" + suffix
        light.data.energy = float(lighting["energy"])
        light.data.angle = math.radians(float(lighting.get("angle_degrees", 1.0)))
    elif light_type == "spot":
        bpy.ops.object.light_add(type="SPOT", location=lighting["position"])
        light = bpy.context.object
        light.name = "configured_spot_light_" + suffix
        light.data.energy = float(lighting["energy"])
        light.data.spot_size = math.radians(float(lighting.get("spot_size_degrees", 45.0)))
        light.data.spot_blend = float(lighting.get("spot_blend", 0.35))
        light.data.shadow_soft_size = float(lighting.get("shadow_soft_size", 8.0))
    elif light_type == "point":
        bpy.ops.object.light_add(type="POINT", location=lighting["position"])
        light = bpy.context.object
        light.name = "configured_point_light_" + suffix
        light.data.energy = float(lighting["energy"])
        light.data.shadow_soft_size = float(lighting.get("shadow_soft_size", 8.0))
    else:
        raise ValueError("Unsupported resolved lighting type: " + light_type)
    if "target" in lighting:
        look_at(light, lighting["target"])


def add_shadow_occluder(occluder, suffix):
    if occluder["type"] == "polygon":
        verts = [(float(point[0]), float(point[1]), 0.0) for point in occluder["vertices"]]
    else:
        half_x = float(occluder["size"][0]) / 2.0
        half_y = float(occluder["size"][1]) / 2.0
        verts = [(-half_x, -half_y, 0.0), (half_x, -half_y, 0.0), (half_x, half_y, 0.0), (-half_x, half_y, 0.0)]
    mesh = bpy.data.meshes.new("shadow_occluder_mesh_" + suffix)
    mesh.from_pydata(verts, [], [tuple(range(len(verts)))])
    mesh.update()
    obj = bpy.data.objects.new("configured_shadow_occluder_" + suffix, mesh)
    obj.location = occluder["position"]
    obj.rotation_euler = (0.0, 0.0, math.radians(float(occluder.get("rotation_degrees", 0.0))))
    if hasattr(obj, "visible_camera"):
        obj.visible_camera = False
    if hasattr(obj, "visible_diffuse"):
        obj.visible_diffuse = False
    if hasattr(obj, "visible_glossy"):
        obj.visible_glossy = False
    bpy.context.collection.objects.link(obj)


def add_debug_polyline(name, points, material, z_offset=0.35):
    if not points or len(points) < 2:
        return None
    verts = [(float(point[0]), float(point[1]), float(point[2]) + z_offset) for point in points]
    edges = [(index, index + 1) for index in range(len(verts) - 1)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    obj.show_in_front = True
    obj.hide_render = True
    obj.display_type = "WIRE"
    bpy.context.collection.objects.link(obj)
    return obj


def add_debug_point_markers(name, points, material, z_offset=0.45, stride=25):
    if not points:
        return None
    verts = []
    for index, point in enumerate(points):
        if index == 0 or index == len(points) - 1 or index % stride == 0:
            verts.append((float(point[0]), float(point[1]), float(point[2]) + z_offset))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    obj.show_in_front = True
    obj.hide_render = True
    obj.display_type = "WIRE"
    bpy.context.collection.objects.link(obj)
    return obj


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

surface = SCENE["surface"]
defect = SCENE["defect"]
material = RECIPE["material"]
render = RECIPE["render"]

surface_mat = make_material(
    "surface_material",
    hex_to_rgba(material["surface_color"]),
    float(material["roughness"]),
)
add_concrete_texture(surface_mat, material, int(defect["seed"]), None)

bounds = surface["bounds"]
block_depth = float(render.get("block_depth", 1000.0))
block_width = bounds["x_max"] - bounds["x_min"]
block_height = bounds["y_max"] - bounds["y_min"]

points = defect["centerline"]
widths = defect["width_profile"]
left_openings = defect.get("left_opening_profile")
right_openings = defect.get("right_opening_profile")
if left_openings is None or right_openings is None:
    left_offsets = [max(float(width), 0.001) / 2.0 for width in widths]
    right_offsets = left_offsets[:]
else:
    left_offsets = [max(float(value), 0.0) for value in left_openings]
    right_offsets = [max(float(value), 0.0) for value in right_openings]
    for index, (left_offset, right_offset) in enumerate(zip(left_offsets, right_offsets)):
        if left_offset + right_offset < 0.001:
            right_offsets[index] = 0.001

if defect.get("construction_parameters", {}).get("construction_model") == "split_displacement":
    split_parts = create_centerline_split_bodies(points, bounds, block_depth, surface_mat)
    opening = defect.get("construction_parameters", {}).get("opening_model", {})
    move_split_body(
        split_parts,
        points,
        str(opening.get("moving_side", "right")),
        float(opening.get("rigid_offset", opening.get("max_opening", 0.0))),
        float(opening.get("vertical_offset", 0.0)),
        widths,
        str(opening.get("physical_model", "")),
    )
    add_crack_edge_falloff(
        points,
        defect.get("left_boundary"),
        defect.get("right_boundary"),
        widths,
        surface_mat,
        render,
    )
    add_crack_debris(points, widths, surface_mat, render)
else:
    left_edge = offset_polyline_edge(points, left_offsets, 1.0)
    right_edge = offset_polyline_edge(points, right_offsets, -1.0)
    crack_boundary = left_edge + list(reversed(right_edge))
    make_block_with_crack_hole("known_cracked_surface_block", bounds, crack_boundary, block_depth, surface_mat)
    add_crack_edge_falloff(
        points,
        defect.get("left_boundary"),
        defect.get("right_boundary"),
        widths,
        surface_mat,
        render,
    )
    add_crack_debris(points, widths, surface_mat, render)

debug_center_mat = make_debug_material("debug_skeleton_material", (1.0, 0.08, 0.02, 1.0))
debug_left_mat = make_debug_material("debug_left_boundary_material", (0.1, 0.45, 1.0, 1.0))
debug_right_mat = make_debug_material("debug_right_boundary_material", (0.1, 1.0, 0.35, 1.0))
add_debug_polyline("debug_crack_skeleton_points_connected", defect["centerline"], debug_center_mat)
add_debug_point_markers("debug_crack_skeleton_station_markers", defect["centerline"], debug_center_mat)
if "left_boundary" in defect:
    add_debug_polyline("debug_crack_left_truth_boundary", defect["left_boundary"], debug_left_mat, 0.25)
if "right_boundary" in defect:
    add_debug_polyline("debug_crack_right_truth_boundary", defect["right_boundary"], debug_right_mat, 0.3)

if hasattr(bpy.context.scene.render, "engine"):
    bpy.context.scene.render.engine = str(render.get("engine", "CYCLES"))
if bpy.context.scene.render.engine == "CYCLES":
    bpy.context.scene.cycles.samples = int(render.get("samples", 64))
    bpy.context.scene.cycles.max_bounces = int(render.get("max_bounces", 4))
    configure_cycles_gpu(render)
elif hasattr(bpy.context.scene, "eevee"):
    bpy.context.scene.eevee.taa_render_samples = int(render.get("samples", 64))
bpy.context.scene.view_settings.view_transform = "Standard"
bpy.context.scene.view_settings.look = "None"
bpy.context.scene.view_settings.exposure = float(render.get("exposure", -1.0))
bpy.context.scene.view_settings.gamma = 1.0
world_color = render.get("world_color", [0.0, 0.0, 0.0])
world_rgb = (
    float(world_color[0]),
    float(world_color[1]),
    float(world_color[2]),
)
bpy.context.scene.world.color = world_rgb
bpy.context.scene.world.use_nodes = True
background_node = bpy.context.scene.world.node_tree.nodes.get("Background")
if background_node is not None:
    background_node.inputs["Color"].default_value = (world_rgb[0], world_rgb[1], world_rgb[2], 1.0)
    background_node.inputs["Strength"].default_value = float(render.get("world_strength", 1.0))

def make_surface_material_for_output(render_item, index):
    mat = make_material(
        "surface_material_render_" + str(index + 1),
        hex_to_rgba(material["surface_color"]),
        float(material["roughness"]),
    )
    add_concrete_texture(mat, material, int(defect["seed"]), render_item.get("render_variant"))
    return mat


def assign_surface_material(mat):
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.hide_render:
            continue
        if obj.name.startswith("configured_shadow_occluder_"):
            continue
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            for index in range(len(obj.data.materials)):
                obj.data.materials[index] = mat


def clear_render_lighting():
    for obj in list(bpy.context.scene.objects):
        if obj.type == "LIGHT" or obj.name.startswith("configured_shadow_occluder_"):
            bpy.data.objects.remove(obj, do_unlink=True)


def configure_camera(camera, suffix):
    bpy.ops.object.camera_add(location=camera["position"])
    cam = bpy.context.object
    cam.name = "configured_camera_" + suffix
    look_at(cam, camera["target"])
    if "roll_degrees" in camera:
        cam.rotation_euler.rotate_axis("Z", math.radians(float(camera["roll_degrees"])))
    if camera["type"] == "orthographic":
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = float(camera["orthographic_scale"])
    else:
        cam.data.type = "PERSP"
        cam.data.angle = math.radians(float(camera["fov_degrees"]))
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()
    return cam


def configure_render(camera, image_path):
    bpy.context.scene.render.resolution_x = int(camera["resolution"][0])
    bpy.context.scene.render.resolution_y = int(camera["resolution"][1])
    image_format = render["image_format"].lower()
    if image_format in {"jpg", "jpeg"}:
        bpy.context.scene.render.image_settings.file_format = "JPEG"
        bpy.context.scene.render.image_settings.quality = int(render.get("quality", 95))
    else:
        bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.filepath = image_path


written_truth_paths = set()
for index, render_item in enumerate(RENDER_ITEMS):
    camera = render_item["capture"]["camera"]
    lighting = render_item["capture"]["lighting"]
    clear_render_lighting()
    add_lighting(lighting)
    cam = configure_camera(camera, str(index + 1))
    output_mat = make_surface_material_for_output(render_item, index)
    assign_surface_material(output_mat)
    configure_render(camera, render_item["image_path"])
    truth_key = render_item["visible_defect_path"] + "|" + render_item["pixel_scale_path"]
    if render_item.get("write_truth", True) and truth_key not in written_truth_paths:
        write_visible_defect(render_item["visible_defect_path"], bpy.context.scene, cam, defect, camera)
        write_nominal_surface_pixel_scale(render_item["pixel_scale_path"], bpy.context.scene, cam, camera)
        written_truth_paths.add(truth_key)
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
'''
