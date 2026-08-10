#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from metrodef3d.export import export_metadata
from metrodef3d.geometry import ConstructedScene
from metrodef3d.pipeline import _output_plan, _write_resolved_recipe
from metrodef3d.recipe import Recipe, validate_recipe
from metrodef3d.render import render_blender_seed_batch


def main() -> int:
    args = parse_args()
    reference = json.loads(args.reference_metadata.read_text(encoding="utf-8"))
    source_recipe = reference["recipe"]["resolved"]
    source_scene = ConstructedScene(
        surface=reference["surface"],
        defect=reference["defect"],
        seeds=reference["seeds"],
    )
    photos = resolve_photos(args.photo_dir, args.photos)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    prepared = []
    manifest_entries = []
    for index, photo_path in enumerate(photos, start=1):
        output_seed = args.output_seed_start + index - 1
        recipe = copy.deepcopy(source_recipe)
        recipe["run"] = {
            "id": f"seed-{args.defect_seed}-photographic-{photo_path.stem.lower()}",
            "seed": output_seed,
            "defect_seed": args.defect_seed,
            "photographic_background": photo_path.name,
            "photographic_background_index": index,
            "reference_output_seed": int(reference["run"]["seed"]),
        }
        recipe["material"] = {
            "surface_color": "#d8d2c8",
            "crack_color": "#181513",
            "roughness": args.roughness,
            "texture_model": "photographic",
            "photographic_texture": {
                "path": str(photo_path.resolve()),
                "physical_width_mm": args.physical_width_mm,
                "physical_height_mm": args.physical_height_mm,
                "center_mm": [0.0, 0.0],
                "rotation_degrees": 0.0,
                "interpolation": "Linear",
                "extension": "CLIP",
                "color_space": "sRGB",
            },
        }
        recipe["render"] = copy.deepcopy(recipe["render"])
        recipe["render"].update(
            {
                "executable": args.blender,
                "use_gpu": True,
                "compute_device_type_order": args.compute_device_type_order,
                "samples": args.samples,
            }
        )
        validate_recipe(Recipe(path=args.reference_metadata, data=recipe))
        output_plan = _output_plan(recipe, args.out_dir)
        _write_resolved_recipe(recipe, output_plan["recipe_yaml"])
        prepared.append((recipe, output_plan))
        manifest_entries.append(
            {
                "index": index,
                "output_seed": output_seed,
                "photo": str(photo_path.resolve()),
                "photo_sha256": sha256(photo_path),
            }
        )

    batch_script = args.out_dir / "blender_script" / "chunks" / "photographic_pilot.py"
    outputs_by_seed = render_blender_seed_batch(
        [
            {
                "recipe": recipe,
                "scene": {
                    "surface": source_scene.surface,
                    "defect": source_scene.defect,
                    "seeds": source_scene.seeds,
                },
                "capture_paths": output_plan["captures"],
            }
            for recipe, output_plan in prepared
        ],
        batch_script,
    )
    for (recipe, output_plan), outputs in zip(prepared, outputs_by_seed):
        export_metadata(
            recipe,
            args.reference_metadata,
            source_scene,
            outputs,
            output_plan["metadata"],
            output_plan["recipe_yaml"],
            args.out_dir,
        )

    manifest = {
        "id": f"seed-{args.defect_seed}-photographic-background-sensitivity",
        "interpretation": "Fixed saved geometry and camera; only the physically sized surface photograph changes.",
        "reference_metadata": str(args.reference_metadata.resolve()),
        "reference_output_seed": int(reference["run"]["seed"]),
        "defect_seed": args.defect_seed,
        "physical_size_mm": [args.physical_width_mm, args.physical_height_mm],
        "samples": args.samples,
        "entries": manifest_entries,
    }
    (args.out_dir / "photographic_pilot_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_dir": str(args.out_dir), "images": len(photos)}, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render one saved defect scene over physically sized photographic backgrounds.")
    parser.add_argument("--reference-metadata", type=Path, required=True)
    parser.add_argument("--photo-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--photos", nargs="+", required=True, help="Photo filenames relative to --photo-dir.")
    parser.add_argument("--defect-seed", type=int, default=10316)
    parser.add_argument("--output-seed-start", type=int, default=10316901)
    parser.add_argument("--physical-width-mm", type=float, default=200.0)
    parser.add_argument("--physical-height-mm", type=float, default=200.0)
    parser.add_argument("--roughness", type=float, default=0.65)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--blender", default="blender")
    parser.add_argument(
        "--compute-device-type-order",
        nargs="+",
        default=["OPTIX", "CUDA", "METAL"],
        help="Cycles device backends to try in order.",
    )
    return parser.parse_args()


def resolve_photos(photo_dir: Path, names: list[str]) -> list[Path]:
    paths = []
    for name in names:
        path = photo_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Photographic background not found: {path}")
        paths.append(path)
    return paths


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
