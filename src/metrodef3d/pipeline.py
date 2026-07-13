from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict, List, Mapping, Tuple

from .camera import resolve_cameras
from .export import export_metadata
from .geometry import construct_scene
from .illumination import resolve_lighting
from .material import resolve_material
from .recipe import Recipe
from .render import render_blender_seed_batch, render_outputs


def generate(recipe: Recipe, out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_recipe = resolve_material(resolve_lighting(resolve_cameras(recipe.data)))
    scene = construct_scene(resolved_recipe)
    scene_dict = {"surface": scene.surface, "defect": scene.defect, "seeds": scene.seeds}
    output_plan = _output_plan(resolved_recipe, out_dir)
    _write_resolved_recipe(resolved_recipe, output_plan["recipe_yaml"])
    outputs = render_outputs(resolved_recipe, scene_dict, output_plan["captures"])
    metadata_path = export_metadata(
        resolved_recipe,
        recipe.path,
        scene,
        outputs,
        output_plan["metadata"],
        output_plan["recipe_yaml"],
        out_dir,
    )
    return outputs[0]["image_path"], metadata_path


def generate_many(recipe: Recipe, out_dir: Path, count: int, seed_step: int = 1) -> List[Tuple[Path, Path]]:
    if count < 1:
        raise ValueError("count must be >= 1")
    if seed_step < 1:
        raise ValueError("seed_step must be >= 1")
    base_seed = int(recipe.data["run"]["seed"])
    results = []
    for index in range(count):
        seed = base_seed + index * seed_step
        variant_data = dict(recipe.data)
        variant_run = dict(recipe.data["run"])
        variant_run["seed"] = seed
        variant_run["id"] = str(recipe.data["run"]["id"]) + "-seed-" + str(seed)
        variant_data["run"] = variant_run
        variant = Recipe(path=recipe.path, data=variant_data)
        results.append(generate(variant, out_dir))
    return results


def generate_many_blender_batched(
    recipe: Recipe,
    out_dir: Path,
    count: int,
    seed_step: int = 1,
    blender_batch_size: int = 1,
) -> List[Tuple[Path, Path]]:
    if blender_batch_size <= 1 or recipe.data["render"]["backend"] != "blender":
        return generate_many(recipe, out_dir, count, seed_step)
    if count < 1:
        raise ValueError("count must be >= 1")
    if seed_step < 1:
        raise ValueError("seed_step must be >= 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    base_seed = int(recipe.data["run"]["seed"])
    results = []
    for chunk_start in range(0, count, blender_batch_size):
        prepared = []
        chunk_count = min(blender_batch_size, count - chunk_start)
        for chunk_index in range(chunk_count):
            index = chunk_start + chunk_index
            seed = base_seed + index * seed_step
            variant = _seed_variant(recipe, seed)
            resolved_recipe = resolve_material(resolve_lighting(resolve_cameras(variant.data)))
            scene = construct_scene(resolved_recipe)
            scene_dict = {"surface": scene.surface, "defect": scene.defect, "seeds": scene.seeds}
            output_plan = _output_plan(resolved_recipe, out_dir)
            _write_resolved_recipe(resolved_recipe, output_plan["recipe_yaml"])
            prepared.append(
                {
                    "recipe": resolved_recipe,
                    "recipe_path": variant.path,
                    "scene": scene,
                    "scene_dict": scene_dict,
                    "output_plan": output_plan,
                }
            )
        first_seed = str(prepared[0]["recipe"]["run"]["seed"])
        last_seed = str(prepared[-1]["recipe"]["run"]["seed"])
        batch_script_path = out_dir / "blender_script" / "chunks" / (first_seed + "_" + last_seed + ".py")
        render_outputs_by_seed = render_blender_seed_batch(
            [
                {
                    "recipe": item["recipe"],
                    "scene": item["scene_dict"],
                    "capture_paths": item["output_plan"]["captures"],
                }
                for item in prepared
            ],
            batch_script_path,
        )
        for item, outputs in zip(prepared, render_outputs_by_seed):
            metadata_path = export_metadata(
                item["recipe"],
                item["recipe_path"],
                item["scene"],
                outputs,
                item["output_plan"]["metadata"],
                item["output_plan"]["recipe_yaml"],
                out_dir,
            )
            results.append((outputs[0]["image_path"], metadata_path))
    return results


def generate_many_blender_parallel(
    recipe: Recipe,
    out_dir: Path,
    count: int,
    seed_step: int = 1,
    blender_batch_size: int = 1,
    workers: int = 1,
) -> List[Tuple[Path, Path]]:
    if workers <= 1 or count <= 1 or recipe.data["render"]["backend"] != "blender":
        return generate_many_blender_batched(recipe, out_dir, count, seed_step, blender_batch_size)
    if count < 1:
        raise ValueError("count must be >= 1")
    if seed_step < 1:
        raise ValueError("seed_step must be >= 1")
    if blender_batch_size < 1:
        raise ValueError("blender_batch_size must be >= 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    worker_count = min(max(1, workers), count)
    ranges = _parallel_work_ranges(count, worker_count)
    results_by_index: Dict[int, Tuple[Path, Path]] = {}
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                _generate_seed_range_worker,
                recipe.path,
                recipe.data,
                out_dir,
                start_index,
                range_count,
                seed_step,
                blender_batch_size,
            )
            for start_index, range_count in ranges
        ]
        for future in as_completed(futures):
            for index, image_path, metadata_path in future.result():
                results_by_index[index] = (image_path, metadata_path)
    return [results_by_index[index] for index in range(count)]


def _parallel_work_ranges(count: int, workers: int) -> List[Tuple[int, int]]:
    workers = min(max(1, workers), count)
    base = count // workers
    remainder = count % workers
    ranges = []
    start = 0
    for worker_index in range(workers):
        range_count = base + (1 if worker_index < remainder else 0)
        ranges.append((start, range_count))
        start += range_count
    return ranges


def _generate_seed_range_worker(
    recipe_path: Path,
    recipe_data: Mapping[str, Any],
    out_dir: Path,
    start_index: int,
    count: int,
    seed_step: int,
    blender_batch_size: int,
) -> List[Tuple[int, Path, Path]]:
    base_seed = int(recipe_data["run"]["seed"])
    worker_data = dict(recipe_data)
    worker_run = dict(recipe_data["run"])
    worker_run["seed"] = base_seed + start_index * seed_step
    worker_data["run"] = worker_run
    worker_recipe = Recipe(path=recipe_path, data=worker_data)
    generated = generate_many_blender_batched(worker_recipe, out_dir, count, seed_step, blender_batch_size)
    return [(start_index + index, image_path, metadata_path) for index, (image_path, metadata_path) in enumerate(generated)]


def _seed_variant(recipe: Recipe, seed: int) -> Recipe:
    variant_data = dict(recipe.data)
    variant_run = dict(recipe.data["run"])
    variant_run["seed"] = seed
    variant_run["id"] = str(recipe.data["run"]["id"]) + "-seed-" + str(seed)
    variant_data["run"] = variant_run
    return Recipe(path=recipe.path, data=variant_data)


def _output_plan(recipe: Mapping[str, Any], out_dir: Path) -> Dict[str, Any]:
    seed = str(recipe["run"]["seed"])
    extension = _image_extension(recipe)
    captures = recipe["captures"]
    is_blender = recipe["render"]["backend"] == "blender"
    capture_outputs = {}
    if is_blender:
        capture_outputs["__batch__"] = {
            "blender_script": out_dir / "blender_script" / (seed + ".py"),
            "blend": out_dir / "blend" / (seed + ".blend"),
        }
    for capture in captures:
        capture_id = str(capture["id"])
        if len(captures) == 1:
            capture_outputs[capture_id] = {
                "image": out_dir / "img" / (seed + extension),
            }
        else:
            capture_outputs[capture_id] = {
                "image": out_dir / "img" / capture_id / (seed + extension),
            }
        if is_blender and len(captures) == 1:
            capture_outputs[capture_id]["visible_defect"] = out_dir / "visible_defect" / (seed + ".json")
            capture_outputs[capture_id]["pixel_scale"] = out_dir / "pixel_scale" / (seed + ".npz")
        elif is_blender:
            capture_outputs[capture_id]["visible_defect"] = out_dir / "visible_defect" / capture_id / (seed + ".json")
            capture_outputs[capture_id]["pixel_scale"] = out_dir / "pixel_scale" / capture_id / (seed + ".npz")
        if is_blender:
            variants = {}
            for variant in capture.get("render_variants", []):
                if not variant.get("enabled", True):
                    continue
                variant_id = str(variant["id"])
                output_id = str(variant.get("output_id", capture_id + "-" + variant_id))
                variants[variant_id] = {
                    "image": out_dir / "img" / output_id / (seed + extension),
                    "visible_defect": capture_outputs[capture_id]["visible_defect"],
                    "pixel_scale": capture_outputs[capture_id]["pixel_scale"],
                }
            if variants:
                capture_outputs[capture_id]["variants"] = variants
    return {
        "captures": capture_outputs,
        "metadata": out_dir / "json" / (seed + ".json"),
        "recipe_yaml": out_dir / "yaml" / (seed + ".yaml"),
    }


def _image_extension(recipe: Mapping[str, Any]) -> str:
    image_format = str(recipe["render"]["image_format"]).lower()
    if image_format in {"jpg", "jpeg"}:
        return ".jpg"
    if image_format == "png":
        return ".png"
    if image_format == "ppm":
        return ".ppm"
    return "." + image_format


def _write_resolved_recipe(recipe: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml(recipe), encoding="utf-8")


def _to_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, Mapping):
        lines = []
        for key, item in value.items():
            if isinstance(item, (Mapping, list)):
                lines.append(prefix + str(key) + ":")
                lines.append(_to_yaml(item, indent + 2).rstrip())
            else:
                lines.append(prefix + str(key) + ": " + _format_yaml_scalar(item))
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, Mapping):
                lines.append(prefix + "-")
                lines.append(_to_yaml(item, indent + 2).rstrip())
            elif isinstance(item, list):
                lines.append(prefix + "- " + _format_yaml_scalar(item))
            else:
                lines.append(prefix + "- " + _format_yaml_scalar(item))
        return "\n".join(lines) + "\n"
    return prefix + _format_yaml_scalar(value) + "\n"


def _format_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_yaml_scalar(item) for item in value) + "]"
    text = str(value)
    if not text or any(char in text for char in [":", "#", "[", "]", "{", "}", ","]):
        return '"' + text.replace('"', '\\"') + '"'
    return text
