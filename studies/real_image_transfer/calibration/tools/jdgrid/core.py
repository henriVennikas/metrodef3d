from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json
import math

import cv2
import numpy as np
import tifffile


ROWS = 50
COLS = 50
DOT_DIAMETER_MM = 1.0002
A1_TOP_MM = 97.9994
A2_BOTTOM_MM = 97.9994
A3_LEFT_MM = 97.9992
A4_RIGHT_MM = 97.9993
A5_DIAGONAL_MM = 138.5915


@dataclass(frozen=True)
class AnalysisResult:
    metrics: dict
    points: np.ndarray
    reference_mm: np.ndarray
    residual_um: np.ndarray
    detected_mask: np.ndarray


def read_dpi(path: Path) -> tuple[float, float]:
    """Read X/Y pixels per inch from the first TIFF page."""
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        x_tag = page.tags.get("XResolution")
        y_tag = page.tags.get("YResolution")
        unit_tag = page.tags.get("ResolutionUnit")
        if x_tag is None or y_tag is None:
            raise ValueError("TIFF has no XResolution/YResolution metadata; pass --dpi")
        unit = int(unit_tag.value) if unit_tag is not None else 2
        if unit not in (2, 3):
            raise ValueError("TIFF resolution unit is not inch or centimetre; pass --dpi")

        def rational(value) -> float:
            return float(value[0]) / float(value[1]) if isinstance(value, tuple) else float(value)

        x = rational(x_tag.value)
        y = rational(y_tag.value)
        if unit == 3:  # pixels/cm -> pixels/inch
            x *= 2.54
            y *= 2.54
        return x, y


def _make_blob_detector(diameter_px: float) -> cv2.SimpleBlobDetector:
    expected_area = math.pi * (diameter_px / 2.0) ** 2
    params = cv2.SimpleBlobDetector_Params()
    params.minThreshold = 0
    params.maxThreshold = 230
    params.thresholdStep = 8
    params.filterByColor = True
    params.blobColor = 0
    params.filterByArea = True
    params.minArea = 0.30 * expected_area
    params.maxArea = 2.20 * expected_area
    params.filterByCircularity = True
    params.minCircularity = 0.50
    params.filterByInertia = True
    params.minInertiaRatio = 0.45
    params.filterByConvexity = True
    params.minConvexity = 0.70
    params.minDistBetweenBlobs = 0.65 * diameter_px
    return cv2.SimpleBlobDetector_create(params)


def _refine_dark_centres(gray: np.ndarray, points: np.ndarray, diameter_px: float) -> np.ndarray:
    refined = []
    radius = max(3, int(round(0.70 * diameter_px)))
    height, width = gray.shape
    gray_f = gray.astype(np.float64)
    for x, y in points:
        cx, cy = int(round(x)), int(round(y))
        x0, x1 = max(0, cx - radius), min(width, cx + radius + 1)
        y0, y1 = max(0, cy - radius), min(height, cy + radius + 1)
        patch = gray_f[y0:y1, x0:x1]
        background = float(np.percentile(patch, 90))
        weights = np.clip(background - patch, 0.0, None)
        total = float(weights.sum())
        if total <= 0:
            refined.append((x, y))
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        refined.append((float((xx * weights).sum() / total), float((yy * weights).sum() / total)))
    return np.asarray(refined, dtype=np.float64)


def _grid_angle(points: np.ndarray, expected_pitch_px: float) -> float:
    """Find grid-axis angle modulo 90 degrees from local neighbour vectors."""
    harmonics = []
    lo, hi = 0.70 * expected_pitch_px, 1.30 * expected_pitch_px
    for i, point in enumerate(points):
        delta = points[i + 1 :] - point
        if not len(delta):
            continue
        distance = np.hypot(delta[:, 0], delta[:, 1])
        near = delta[(distance >= lo) & (distance <= hi)]
        if len(near):
            angles = np.arctan2(near[:, 1], near[:, 0])
            harmonics.extend(np.exp(4j * angles))
    if not harmonics:
        raise ValueError("Could not estimate grid orientation from neighbouring dots")
    return float(np.angle(np.mean(harmonics)) / 4.0)


def order_grid(points: np.ndarray, expected_pitch_px: float) -> tuple[np.ndarray, np.ndarray]:
    """Reject non-grid blobs, index solid dots, and infer intentional hollow fiducials."""
    if len(points) < ROWS * COLS - 20:
        raise ValueError(f"Detected only {len(points)} dot-like blobs; most of the 50 x 50 grid must be visible")
    theta = _grid_angle(points, expected_pitch_px)

    # Logos/dust can look circular. Grid dots have at least two neighbours at one
    # pitch along the two grid axes (corners have exactly two).
    scores = []
    for point in points:
        delta = points - point
        distance = np.linalg.norm(delta, axis=1)
        angle = np.arctan2(delta[:, 1], delta[:, 0])
        axis_error = np.abs(np.sin(2.0 * (angle - theta)))
        scores.append(np.count_nonzero(
            (distance >= 0.70 * expected_pitch_px)
            & (distance <= 1.30 * expected_pitch_px)
            & (axis_error < 0.25)
        ))
    points = points[np.asarray(scores) >= 2]
    if len(points) < ROWS * COLS - 20 or len(points) > ROWS * COLS:
        raise ValueError(f"Found {len(points)} spatially consistent solid grid dots; expected approximately 2497")

    centre = points.mean(axis=0)
    c, s = math.cos(-theta), math.sin(-theta)
    rotation = np.array([[c, -s], [s, c]])
    aligned = (points - centre) @ rotation.T
    pitch_x = (float(aligned[:, 0].max()) - float(aligned[:, 0].min())) / (COLS - 1)
    pitch_y = (float(aligned[:, 1].max()) - float(aligned[:, 1].min())) / (ROWS - 1)
    cols = np.rint((aligned[:, 0] - aligned[:, 0].min()) / pitch_x).astype(int)
    rows = np.rint((aligned[:, 1] - aligned[:, 1].min()) / pitch_y).astype(int)
    if np.any(cols < 0) or np.any(cols >= COLS) or np.any(rows < 0) or np.any(rows >= ROWS):
        raise ValueError("Grid indexing fell outside the expected 50 x 50 array")
    keys = rows * COLS + cols
    if len(np.unique(keys)) != len(keys):
        raise ValueError("Two detected dots mapped to the same grid position")

    # Fit image coordinates from integer grid coordinates. This supplies centres
    # for the three intentional hollow orientation marks, which the solid-blob
    # detector correctly omits. Inferred marks are excluded from error metrics.
    design = np.column_stack((cols, rows, np.ones(len(points))))
    model, *_ = np.linalg.lstsq(design, points, rcond=None)
    rr, cc = np.mgrid[0:ROWS, 0:COLS]
    all_design = np.column_stack((cc.ravel(), rr.ravel(), np.ones(ROWS * COLS)))
    grid = (all_design @ model).reshape(ROWS, COLS, 2)
    mask = np.zeros((ROWS, COLS), dtype=bool)
    for point, row, col in zip(points, rows, cols):
        grid[row, col] = point
        mask[row, col] = True

    neighbour_x = np.linalg.norm(np.diff(grid, axis=1), axis=2)
    neighbour_y = np.linalg.norm(np.diff(grid, axis=0), axis=2)
    if not (0.75 * expected_pitch_px <= np.median(neighbour_x) <= 1.25 * expected_pitch_px):
        raise ValueError("Invalid horizontal grid pitch")
    if not (0.75 * expected_pitch_px <= np.median(neighbour_y) <= 1.25 * expected_pitch_px):
        raise ValueError("Invalid vertical grid pitch")
    return grid, mask


def orient_grid(grid: np.ndarray, rotation_cw: int) -> np.ndarray:
    """Return points indexed in the target's upright certificate orientation."""
    if rotation_cw not in (0, 90, 180, 270):
        raise ValueError("rotation_cw must be one of 0, 90, 180, 270")
    return np.rot90(grid, k=rotation_cw // 90, axes=(0, 1)).copy()


def infer_rotation_cw(detected_mask: np.ndarray) -> int:
    """Infer visible rotation from the SL12-4's three central hollow dots."""
    canonical_hollow = {(24, 24), (25, 24), (25, 25)}
    for rotation in (0, 90, 180, 270):
        candidate = orient_grid(detected_mask, rotation)
        hollow = set(map(tuple, np.argwhere(~candidate)))
        if hollow == canonical_hollow:
            return rotation
    raise ValueError(
        "Could not infer orientation from the three hollow central dots; "
        "supply --rotation-cw explicitly"
    )


def reference_coordinates() -> np.ndarray:
    """Idealized grid using the mean of the certified opposing edge spans."""
    width = (A1_TOP_MM + A2_BOTTOM_MM) / 2.0
    height = (A3_LEFT_MM + A4_RIGHT_MM) / 2.0
    x = np.linspace(0.0, width, COLS)
    y = np.linspace(0.0, height, ROWS)
    xx, yy = np.meshgrid(x, y)
    return np.dstack((xx, yy))


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def calculate(
    grid: np.ndarray,
    source: Path,
    metadata_dpi: tuple[float, float],
    detected_mask: np.ndarray | None = None,
) -> AnalysisResult:
    reference = reference_coordinates()
    if detected_mask is None:
        detected_mask = np.ones((ROWS, COLS), dtype=bool)
    pixels = grid.reshape(-1, 2)
    mm = reference.reshape(-1, 2)
    valid = detected_mask.ravel()
    design = np.column_stack((pixels, np.ones(len(pixels))))
    transform, *_ = np.linalg.lstsq(design[valid], mm[valid], rcond=None)
    predicted = design @ transform
    residual_um = (mm - predicted) * 1000.0
    error_um = np.linalg.norm(residual_um[valid], axis=1)

    spans = {
        "A1_top": (A1_TOP_MM, _distance(grid[0, 0], grid[0, -1])),
        "A2_bottom": (A2_BOTTOM_MM, _distance(grid[-1, 0], grid[-1, -1])),
        "A3_left": (A3_LEFT_MM, _distance(grid[0, 0], grid[-1, 0])),
        "A4_right": (A4_RIGHT_MM, _distance(grid[0, -1], grid[-1, -1])),
        "A5_diagonal": (A5_DIAGONAL_MM, _distance(grid[-1, 0], grid[0, -1])),
    }
    span_metrics = {}
    for name, (certified_mm, observed_px) in spans.items():
        pitch_um = certified_mm * 1000.0 / observed_px
        span_metrics[name] = {
            "certified_mm": certified_mm,
            "observed_px": observed_px,
            "um_per_px": pitch_um,
            "effective_dpi": 25400.0 / pitch_um,
        }

    x_um = np.mean([span_metrics["A1_top"]["um_per_px"], span_metrics["A2_bottom"]["um_per_px"]])
    y_um = np.mean([span_metrics["A3_left"]["um_per_px"], span_metrics["A4_right"]["um_per_px"]])
    linear = transform[:2, :].T
    x_axis = linear[:, 0]
    y_axis = linear[:, 1]
    orthogonality_deg = math.degrees(
        math.acos(float(np.clip(np.dot(x_axis, y_axis) / (np.linalg.norm(x_axis) * np.linalg.norm(y_axis)), -1, 1)))
    )
    metrics = {
        "source": str(source),
        "target": "JD Photo Data SL12-4, certificate 008/194821-001",
        "grid_shape": [ROWS, COLS],
        "detected_solid_dots": int(np.count_nonzero(detected_mask)),
        "inferred_hollow_fiducials": int(detected_mask.size - np.count_nonzero(detected_mask)),
        "metadata_dpi": {"x": metadata_dpi[0], "y": metadata_dpi[1]},
        "calibrated_scale": {
            "x_um_per_px": x_um,
            "y_um_per_px": y_um,
            "x_effective_dpi": 25400.0 / x_um,
            "y_effective_dpi": 25400.0 / y_um,
        },
        "spans": span_metrics,
        "affine_pixel_to_mm": transform.T.tolist(),
        "axis_angle_degrees": orthogonality_deg,
        "affine_residual_um": {
            "rms_radial": float(np.sqrt(np.mean(error_um**2))),
            "p95_radial": float(np.percentile(error_um, 95)),
            "maximum_radial": float(np.max(error_um)),
            "mean_x": float(np.mean(residual_um[valid, 0])),
            "mean_y": float(np.mean(residual_um[valid, 1])),
        },
        "interpretation_warning": (
            "Local residuals include scanner error and unreported local target placement error; "
            "the certificate supplies only the listed outer spans, diagonal, and dot diameter."
        ),
    }
    return AnalysisResult(metrics, grid, reference, residual_um.reshape(ROWS, COLS, 2), detected_mask)


def detect(gray: np.ndarray, dpi: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    mean_dpi = sum(dpi) / 2.0
    diameter_px = mean_dpi * DOT_DIAMETER_MM / 25.4
    pitch_px = mean_dpi * 2.0 / 25.4
    detector = _make_blob_detector(diameter_px)
    keypoints = detector.detect(gray)
    points = np.asarray([kp.pt for kp in keypoints], dtype=np.float64)
    points = _refine_dark_centres(gray, points, diameter_px)
    return order_grid(points, pitch_px)


def write_outputs(image: np.ndarray, result: AnalysisResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(result.metrics, indent=2) + "\n")

    residual = result.residual_um
    error = np.linalg.norm(residual, axis=2)
    with (output_dir / "dots.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", "column", "pixel_x", "pixel_y", "reference_x_mm", "reference_y_mm", "residual_x_um", "residual_y_um", "radial_error_um"])
        for row in range(ROWS):
            for col in range(COLS):
                writer.writerow([
                    row, col,
                    f"{result.points[row, col, 0]:.6f}", f"{result.points[row, col, 1]:.6f}",
                    f"{result.reference_mm[row, col, 0]:.7f}", f"{result.reference_mm[row, col, 1]:.7f}",
                    f"{residual[row, col, 0]:.4f}" if result.detected_mask[row, col] else "",
                    f"{residual[row, col, 1]:.4f}" if result.detected_mask[row, col] else "",
                    f"{error[row, col]:.4f}" if result.detected_mask[row, col] else "",
                ])

    if image.ndim == 2:
        overlay = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        overlay = image[:, :, :3].copy()
    scale = min(1.0, 2200.0 / max(overlay.shape[:2]))
    if scale < 1.0:
        overlay = cv2.resize(overlay, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    max_error = max(float(np.percentile(error, 99)), 1e-9)
    for row in range(ROWS):
        for col in range(COLS):
            x, y = result.points[row, col] * scale
            if not result.detected_mask[row, col]:
                cv2.circle(overlay, (int(round(x)), int(round(y))), max(2, int(round(4 * scale))), (255, 128, 0), 1, cv2.LINE_AA)
                continue
            fraction = min(float(error[row, col]) / max_error, 1.0)
            color = (0, int(255 * (1.0 - fraction)), int(255 * fraction))
            cv2.circle(overlay, (int(round(x)), int(round(y))), max(1, int(round(2 * scale))), color, -1, cv2.LINE_AA)
    cv2.polylines(
        overlay,
        [np.round(result.points[[0, 0, -1, -1], [0, -1, -1, 0]] * scale).astype(np.int32)],
        True,
        (255, 0, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(output_dir / "qa_overlay.png"), overlay)


def analyze(path: Path, output_dir: Path, dpi_override: float | None, rotation_cw: int | None) -> AnalysisResult:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"OpenCV could not read {path}")
    if image.ndim == 3:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    dpi = (dpi_override, dpi_override) if dpi_override else read_dpi(path)
    grid, detected_mask = detect(gray, dpi)
    inferred_rotation = infer_rotation_cw(detected_mask)
    explicit_override = rotation_cw is not None
    if rotation_cw is None:
        rotation_cw = inferred_rotation
    grid = orient_grid(grid, rotation_cw)
    detected_mask = orient_grid(detected_mask, rotation_cw)
    result = calculate(grid, path, dpi, detected_mask)
    result.metrics["orientation"] = {
        "rotation_cw_applied": rotation_cw,
        "rotation_cw_inferred_from_hollow_dots": inferred_rotation,
        "explicit_override": explicit_override,
    }
    write_outputs(image, result, output_dir)
    return result
