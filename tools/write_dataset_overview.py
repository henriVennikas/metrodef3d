#!/usr/bin/env python3
"""Write a human and machine-readable overview for a metrodef3d run directory."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


COUNT_PATTERNS = {
    "images": "img/*/*.jpg",
    "metadata_json": "json/*.json",
    "visible_defect_sidecars": "visible_defect/*/*.json",
    "pixel_scale_sidecars": "pixel_scale/*/*.npz",
    "blend_files": "blend/*.blend",
    "seed_scripts": "blender_script/*.py",
    "chunk_scripts": "blender_script/chunks/*.py",
    "seed_yamls": "yaml/*.yaml",
}

MEASURANDS = ("centerline_length", "mean_width", "max_width", "crack_area")


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    summary = build_summary(run_dir)
    write_json(run_dir / args.summary_name, summary)
    (run_dir / args.readme_name).write_text(render_readme(summary), encoding="utf-8")
    print(f"Wrote {run_dir / args.readme_name}")
    print(f"Wrote {run_dir / args.summary_name}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--readme-name", default="README.md")
    parser.add_argument("--summary-name", default="dataset_summary.json")
    return parser.parse_args()


def build_summary(run_dir: Path) -> Dict[str, Any]:
    json_paths = sorted((run_dir / "json").glob("*.json"), key=lambda path: int(path.stem))
    metadata = [json.loads(path.read_text(encoding="utf-8")) for path in json_paths]
    seeds = [int(item["run"]["seed"]) for item in metadata]
    captures = capture_summary(run_dir, metadata)
    counts = {name: len(list(run_dir.glob(pattern))) for name, pattern in COUNT_PATTERNS.items()}
    recipe = metadata[0]["recipe"]["resolved"] if metadata else {}
    generator = metadata[0].get("generator", {}) if metadata else {}
    render = metadata[0].get("render", {}) if metadata else {}
    material = metadata[0].get("material", {}) if metadata else {}
    defect = metadata[0].get("defect", {}) if metadata else {}
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_directory": str(run_dir),
        "run_id": metadata[0]["run"]["id"] if metadata else None,
        "generator": generator,
        "seed_range": {
            "min": min(seeds) if seeds else None,
            "max": max(seeds) if seeds else None,
            "count": len(seeds),
            "contiguous": seeds == list(range(min(seeds), max(seeds) + 1)) if seeds else False,
        },
        "counts": counts,
        "captures": captures,
        "surface": metadata[0].get("surface", {}) if metadata else {},
        "defect_construction": {
            "type": defect.get("type"),
            "construction_model": defect.get("construction_parameters", {}).get("construction_model"),
            "measurands_source": "construction_metadata",
            "visible_truth_model": "per_capture_visible_defect",
        },
        "render": {
            "backend": render.get("backend"),
            "image_format": render.get("image_format"),
            "resolution": first_resolution(metadata),
        },
        "material": {
            "texture_model": material.get("texture_model"),
            "concrete_texture_enabled": bool(material.get("concrete_texture")),
        },
        "important_paths": {
            "images": "img/<capture_id>/<seed>.jpg",
            "metadata": "json/<seed>.json",
            "visible_defect": "visible_defect/<capture_id>/<seed>.json",
            "pixel_scale": "pixel_scale/<capture_id>/<seed>.npz",
            "blend": "blend/<seed>.blend",
            "recipe": "yaml/<seed>.yaml",
            "seed_script": "blender_script/<seed>.py",
            "chunk_script": "blender_script/chunks/<first_seed>_<last_seed>.py",
        },
        "notes": [
            "Ground truth is not recovered from rendered pixels.",
            "Use each capture's visible_defect measurands for image-specific scalar targets.",
            "Per-pixel nominal surface scale maps are available for perspective geometry context.",
            "Orthographic overhead captures are retained mainly as truth/debug views; perspective captures are the main camera-like flow.",
        ],
        "recipe_excerpt": {
            "surface": recipe.get("surface"),
            "defect": recipe.get("defect"),
        },
    }


def capture_summary(run_dir: Path, metadata: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    per_capture: Dict[str, Dict[str, Any]] = {}
    values: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    visible_counts = defaultdict(int)
    for item in metadata:
        for capture in item["outputs"]["captures"]:
            capture_id = capture["capture_id"]
            if capture_id not in per_capture:
                per_capture[capture_id] = {
                    "source_capture_id": capture.get("source_capture_id"),
                    "render_variant": capture.get("render_variant"),
                    "camera_type": capture.get("camera", {}).get("type"),
                    "lens_model": capture.get("camera", {}).get("lens_model"),
                    "image_count": 0,
                    "visible_count": 0,
                    "measurands": {},
                    "paths": {
                        "images": f"img/{capture_id}/<seed>.jpg",
                        "visible_defect": f"visible_defect/{capture_id}/<seed>.json",
                        "pixel_scale": f"pixel_scale/{capture_id}/<seed>.npz",
                    },
                }
            per_capture[capture_id]["image_count"] += 1
            visible = capture.get("visible_defect", {})
            if visible.get("visible"):
                visible_counts[capture_id] += 1
            measurands = visible.get("measurands", {})
            for key in MEASURANDS:
                if key in measurands:
                    values[capture_id][key].append(float(measurands[key]))
    for capture_id, target_values in values.items():
        per_capture[capture_id]["visible_count"] = visible_counts[capture_id]
        per_capture[capture_id]["measurands"] = {
            name: numeric_summary(numbers) for name, numbers in target_values.items()
        }
    return per_capture


def numeric_summary(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": round(ordered[0], 6),
        "max": round(ordered[-1], 6),
        "mean": round(statistics.fmean(ordered), 6),
        "median": round(statistics.median(ordered), 6),
    }


def first_resolution(metadata: Sequence[Mapping[str, Any]]) -> Any:
    if not metadata:
        return None
    captures = metadata[0].get("outputs", {}).get("captures", [])
    if not captures:
        return None
    return captures[0].get("camera", {}).get("resolution")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_readme(summary: Mapping[str, Any]) -> str:
    seed_range = summary["seed_range"]
    counts = summary["counts"]
    lines = [
        f"# {summary['run_id'] or 'metrodef3d dataset run'}",
        "",
        "This directory contains a metrodef3d generated cracked-concrete dataset run.",
        "The defect truth is construction metadata, not pixel-derived annotation.",
        "",
        "## Dataset State",
        "",
        f"- Seeds: `{seed_range['min']}..{seed_range['max']}`",
        f"- Seed count: `{seed_range['count']}`",
        f"- Contiguous: `{seed_range['contiguous']}`",
        f"- Images: `{counts['images']}`",
        f"- Metadata JSON files: `{counts['metadata_json']}`",
        f"- Visible-defect sidecars: `{counts['visible_defect_sidecars']}`",
        f"- Pixel-scale sidecars: `{counts['pixel_scale_sidecars']}`",
        f"- Blend files: `{counts['blend_files']}`",
        f"- Seed YAML files: `{counts['seed_yamls']}`",
        f"- Blender seed scripts: `{counts['seed_scripts']}`",
        f"- Blender chunk scripts: `{counts['chunk_scripts']}`",
        "",
        "## Directory Layout",
        "",
        "```text",
        "img/<capture_id>/<seed>.jpg",
        "json/<seed>.json",
        "visible_defect/<capture_id>/<seed>.json",
        "pixel_scale/<capture_id>/<seed>.npz",
        "blend/<seed>.blend",
        "yaml/<seed>.yaml",
        "blender_script/<seed>.py",
        "blender_script/chunks/<first_seed>_<last_seed>.py",
        "```",
        "",
        "## Captures",
        "",
    ]
    for capture_id, capture in summary["captures"].items():
        lines.extend(
            [
                f"### `{capture_id}`",
                "",
                f"- Camera type: `{capture.get('camera_type')}`",
                f"- Source capture: `{capture.get('source_capture_id')}`",
                f"- Image count: `{capture.get('image_count')}`",
                f"- Visible defect count: `{capture.get('visible_count')}`",
                "",
                "| Measurand | Min | Median | Mean | Max |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, stats in capture.get("measurands", {}).items():
            lines.append(
                f"| `{name}` | {stats.get('min')} | {stats.get('median')} | {stats.get('mean')} | {stats.get('max')} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Ground Truth Use",
            "",
            "- Use `json/<seed>.json` as the canonical sample metadata entry.",
            "- Use `outputs.captures[*].visible_defect.measurands` for per-image scalar targets.",
            "- Use `visible_defect/<capture_id>/<seed>.json` when a sidecar truth file is more convenient.",
            "- Use `pixel_scale/<capture_id>/<seed>.npz` for per-pixel nominal-surface scale maps.",
            "- Do not re-estimate crack width, length, or area from rendered pixels for ground truth.",
            "",
            "## Companion Summary",
            "",
            "A machine-readable overview is available at `dataset_summary.json`.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
