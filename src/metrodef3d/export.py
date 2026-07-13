import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import (
    METADATA_SCHEMA_VERSION,
    PIXEL_SCALE_SCHEMA_VERSION,
    RECIPE_SCHEMA_VERSION,
    VISIBLE_DEFECT_SCHEMA_VERSION,
    __version__,
)
from .geometry import ConstructedScene, visible_defect_for_capture


def export_metadata(
    recipe: Mapping[str, Any],
    recipe_path: Optional[Path],
    scene: ConstructedScene,
    outputs: List[Mapping[str, Any]],
    metadata_path: Path,
    recipe_yaml_path: Path,
    out_dir: Path,
) -> Path:
    metadata = build_metadata(recipe, recipe_path, scene, outputs, metadata_path, recipe_yaml_path, out_dir)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata_path


def build_metadata(
    recipe: Mapping[str, Any],
    recipe_path: Optional[Path],
    scene: ConstructedScene,
    outputs: List[Mapping[str, Any]],
    metadata_path: Path,
    recipe_yaml_path: Path,
    out_dir: Path,
) -> Dict[str, Any]:
    capture_outputs = []
    for output in outputs:
        visible_defect = output.get("visible_defect")
        if visible_defect is None:
            visible_defect = visible_defect_for_capture(scene.defect, output["camera"])
        capture_output = {
            "capture_id": output["capture_id"],
            "image": str(output["image_path"]),
            "camera": dict(output["camera"]),
            "lighting": dict(output["lighting"]),
            "visible_defect": visible_defect,
        }
        if "source_capture_id" in output:
            capture_output["source_capture_id"] = output["source_capture_id"]
        if "render_variant" in output:
            capture_output["render_variant"] = dict(output["render_variant"])
        if "visible_defect_path" in output:
            capture_output["visible_defect_sidecar"] = str(output["visible_defect_path"])
        if "pixel_scale_path" in output:
            capture_output["pixel_scale_sidecar"] = str(output["pixel_scale_path"])
        if "nominal_surface_pixel_scale" in output:
            capture_output["nominal_surface_pixel_scale"] = dict(output["nominal_surface_pixel_scale"])
        if "blender_script_path" in output:
            capture_output["blender_script"] = str(output["blender_script_path"])
        if "blend_path" in output:
            capture_output["blend"] = str(output["blend_path"])
        capture_outputs.append(capture_output)
    first_image = capture_outputs[0]["image"] if capture_outputs else None
    git_commit = _git_commit()
    return {
        "schema": {
            "name": "metrodef3d.metadata",
            "version": METADATA_SCHEMA_VERSION,
        },
        "generator": {
            "name": "metrodef3d",
            "version": __version__,
            "git_commit": git_commit,
            "commit": git_commit,
            "recipe_schema_version": RECIPE_SCHEMA_VERSION,
            "metadata_schema_version": METADATA_SCHEMA_VERSION,
            "visible_defect_schema_version": VISIBLE_DEFECT_SCHEMA_VERSION,
            "pixel_scale_schema_version": PIXEL_SCALE_SCHEMA_VERSION,
        },
        "recipe": {
            "path": str(recipe_path) if recipe_path is not None else None,
            "resolved": dict(recipe),
        },
        "run": dict(recipe["run"]),
        "seeds": scene.seeds,
        "surface": scene.surface,
        "defect": scene.defect,
        "camera": dict(recipe["camera"]),
        "lighting": dict(recipe["lighting"]),
        "captures": list(recipe["captures"]),
        "material": dict(recipe["material"]),
        "render": dict(recipe["render"]),
        "outputs": {
            "directory": str(out_dir),
            "image": first_image,
            "captures": capture_outputs,
            "metadata": str(metadata_path),
            "recipe_yaml": str(recipe_yaml_path),
        },
    }


def _git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None
