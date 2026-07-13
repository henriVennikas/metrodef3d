#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a metrodef3d run for likely render geometry failures.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--black-threshold", type=int, default=8)
    parser.add_argument("--max-frame-black-component-frac", type=float, default=0.04)
    parser.add_argument("--max-black-frac", type=float, default=0.12)
    parser.add_argument("--max-boundary-outside-frac", type=float, default=0.0)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    findings = scan_run(
        args.run_dir,
        black_threshold=args.black_threshold,
        max_frame_black_component_frac=args.max_frame_black_component_frac,
        max_black_frac=args.max_black_frac,
        max_boundary_outside_frac=args.max_boundary_outside_frac,
    )
    flagged = [finding for finding in findings if finding["flags"]]
    print("Scanned", len(findings), "samples")
    print("Flagged", len(flagged), "samples")
    for finding in flagged:
        print(
            str(finding["seed"])
            + " flags="
            + ",".join(finding["flags"])
            + " black="
            + _fmt(finding.get("black_fraction"))
            + " frame_black_component="
            + _fmt(finding.get("largest_frame_touching_black_component_fraction"))
            + " boundary_outside="
            + _fmt(finding.get("boundary_outside_fraction"))
        )
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("Wrote", args.json_out)
    return 1 if flagged else 0


def scan_run(
    run_dir: Path,
    *,
    black_threshold: int,
    max_frame_black_component_frac: float,
    max_black_frac: float,
    max_boundary_outside_frac: float,
) -> List[Dict[str, Any]]:
    metadata_paths = sorted((run_dir / "json").glob("*.json"))
    findings = []
    for metadata_path in metadata_paths:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        seed = int(metadata["run"]["seed"])
        image_path = _image_path(run_dir, metadata)
        geometry = _geometry_risk(metadata)
        image_metrics = _image_black_metrics(image_path, black_threshold)
        flags = []
        boundary_fraction = geometry["boundary_outside_fraction"]
        if boundary_fraction > max_boundary_outside_frac:
            flags.append("boundary_exits_surface")
        black_fraction = image_metrics.get("black_fraction")
        frame_component = image_metrics.get("largest_frame_touching_black_component_fraction")
        if black_fraction is not None and black_fraction > max_black_frac:
            flags.append("large_black_fraction")
        if frame_component is not None and frame_component > max_frame_black_component_frac:
            flags.append("large_frame_touching_black_component")
        findings.append(
            {
                "seed": seed,
                "metadata": str(metadata_path),
                "image": str(image_path) if image_path is not None else None,
                "flags": flags,
                **geometry,
                **image_metrics,
            }
        )
    return findings


def _image_path(run_dir: Path, metadata: Mapping[str, Any]) -> Optional[Path]:
    captures = metadata.get("outputs", {}).get("captures", [])
    if not captures:
        return None
    image = captures[0].get("image")
    if not image:
        return None
    path = Path(image)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return run_dir / path.relative_to(run_dir) if str(path).startswith(str(run_dir)) else run_dir / path


def _geometry_risk(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    preflight = (
        metadata.get("defect", {})
        .get("construction_parameters", {})
        .get("render_geometry_preflight")
    )
    if isinstance(preflight, Mapping):
        return {
            "boundary_outside_count": int(preflight.get("outside_boundary_point_count", 0)),
            "boundary_outside_fraction": float(preflight.get("outside_boundary_point_fraction", 0.0)),
            "boundary_preflight_risk": str(preflight.get("risk", "none")),
        }
    bounds = metadata["surface"]["bounds"]
    points = metadata["defect"].get("left_boundary", []) + metadata["defect"].get("right_boundary", [])
    outside = 0
    for point in points:
        if not (
            float(bounds["x_min"]) <= float(point[0]) <= float(bounds["x_max"])
            and float(bounds["y_min"]) <= float(point[1]) <= float(bounds["y_max"])
        ):
            outside += 1
    return {
        "boundary_outside_count": outside,
        "boundary_outside_fraction": outside / float(len(points)) if points else 0.0,
        "boundary_preflight_risk": "explicit_hole_boundary_exits_surface" if outside else "none",
    }


def _image_black_metrics(image_path: Optional[Path], black_threshold: int) -> Dict[str, Any]:
    if image_path is None or not image_path.exists():
        return {
            "black_fraction": None,
            "largest_frame_touching_black_component_fraction": None,
            "image_error": "missing_image",
        }
    try:
        from PIL import Image
    except Exception as exc:
        return {
            "black_fraction": None,
            "largest_frame_touching_black_component_fraction": None,
            "image_error": "Pillow is required for image scan: " + str(exc),
        }
    image = Image.open(image_path).convert("L")
    width, height = image.size
    values = image.tobytes()
    mask = bytearray(1 if value <= black_threshold else 0 for value in values)
    total = width * height
    black_count = sum(mask)
    largest_frame_component = _largest_frame_touching_component(mask, width, height)
    return {
        "black_threshold": black_threshold,
        "black_fraction": round(black_count / float(total), 8),
        "largest_frame_touching_black_component_fraction": round(largest_frame_component / float(total), 8),
    }


def _largest_frame_touching_component(mask: bytearray, width: int, height: int) -> int:
    total = width * height
    seen = bytearray(total)
    starts = []
    for x in range(width):
        starts.append(x)
        starts.append((height - 1) * width + x)
    for y in range(1, height - 1):
        starts.append(y * width)
        starts.append(y * width + width - 1)
    largest = 0
    for start in starts:
        if not mask[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        size = 0
        while stack:
            index = stack.pop()
            size += 1
            x = index % width
            y = index // width
            neighbors = []
            if x > 0:
                neighbors.append(index - 1)
            if x < width - 1:
                neighbors.append(index + 1)
            if y > 0:
                neighbors.append(index - width)
            if y < height - 1:
                neighbors.append(index + width)
            for neighbor in neighbors:
                if mask[neighbor] and not seen[neighbor]:
                    seen[neighbor] = 1
                    stack.append(neighbor)
        largest = max(largest, size)
    return largest


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
