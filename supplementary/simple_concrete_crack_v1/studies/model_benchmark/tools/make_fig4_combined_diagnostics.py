#!/usr/bin/env python3
"""Generate a compact combined accuracy and uncertainty diagnostic figure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from make_fig3_error_boxplots import (
    TARGETS,
    _physical_error_panel,
    _prediction_panel,
)
from make_fig4_uncertainty_calibration import (
    _coverage_label,
    _diagnostics,
    _interval_width_panel,
    _load_interval_scales,
    _normalized_residual_panel,
    _target_summary,
)


def build_figure(
    predictions_csv: Path,
    calibration_metrics: Path,
    output_stem: Path,
) -> None:
    df = pd.read_csv(predictions_csv)
    df = df[(df[[name + "_actual" for name, _, _ in TARGETS]] > 0).all(axis=1)].copy()
    interval_scales = _load_interval_scales(calibration_metrics)

    fig = plt.figure(figsize=(10.8, 6.25))
    outer = fig.add_gridspec(
        nrows=len(TARGETS),
        ncols=1,
        left=0.055,
        right=0.985,
        top=0.900,
        bottom=0.055,
        hspace=0.30,
    )
    summaries = {
        "n_visible_positive": int(len(df)),
        "calibration_metrics": calibration_metrics.name,
        "interval_scales": interval_scales,
        "targets": {},
    }
    first_axes = None

    for row, (name, label, unit) in enumerate(TARGETS):
        actual = df[f"{name}_actual"].to_numpy(float)
        pred = df[f"{name}_mu"].to_numpy(float)
        signed_error = pred - actual
        absolute_error = np.abs(signed_error)
        median_truth = float(np.median(actual))

        raw_lower = df[f"{name}_lower"].to_numpy(float)
        raw_upper = df[f"{name}_upper"].to_numpy(float)
        scale = interval_scales[name]
        calibrated_lower = pred - (pred - raw_lower) * scale
        calibrated_upper = pred + (raw_upper - pred) * scale
        raw_diag = _diagnostics(actual, pred, raw_lower, raw_upper)
        calibrated_diag = _diagnostics(actual, pred, calibrated_lower, calibrated_upper)

        block = outer[row, 0].subgridspec(
            nrows=2,
            ncols=5,
            height_ratios=[0.18, 1.0],
            width_ratios=[2.20, 1.35, 0.62, 1.90, 1.90],
            hspace=0.08,
            wspace=0.34,
        )
        title_ax = fig.add_subplot(block[0, :])
        title_ax.axis("off")
        title_ax.text(
            0.5,
            0.58,
            label,
            ha="center",
            va="center",
            fontsize=8.4,
            fontweight="bold",
            transform=title_ax.transAxes,
        )

        error_ax = fig.add_subplot(block[1, 0])
        _physical_error_panel(
            error_ax,
            signed_error,
            absolute_error,
            unit,
            (-0.20 * median_truth, 0.20 * median_truth),
            annotate_medians=False,
            show_row_labels=False,
        )
        prediction_ax = fig.add_subplot(block[1, 1])
        _prediction_panel(prediction_ax, actual, pred, unit, show_axis_names=False)
        coverage_ax = fig.add_subplot(block[1, 2])
        _coverage_label(coverage_ax, raw_diag["coverage"], calibrated_diag["coverage"])
        width_ax = fig.add_subplot(block[1, 3])
        _interval_width_panel(
            width_ax,
            raw_diag["interval_width"],
            calibrated_diag["interval_width"],
            median_truth,
            unit,
            annotate_medians=False,
        )
        residual_ax = fig.add_subplot(block[1, 4])
        _normalized_residual_panel(
            residual_ax,
            raw_diag["normalized"],
            calibrated_diag["normalized"],
            annotate_medians=False,
        )

        if first_axes is None:
            first_axes = (error_ax, prediction_ax, coverage_ax, width_ax, residual_ax, title_ax)
        summaries["targets"][name] = {
            "median_truth": median_truth,
            "median_signed_error": float(np.median(signed_error)),
            "median_absolute_error": float(np.median(absolute_error)),
            "raw": _target_summary(raw_diag, actual),
            "calibrated": _target_summary(calibrated_diag, actual),
        }

    if first_axes is not None:
        headings = (
            "Signed and absolute\nerror distribution",
            "Prediction (vert.) vs\ntruth (horiz.)",
            "Coverage",
            "Interval width",
            "Normalized residual",
        )
        title_bbox = first_axes[-1].get_position()
        for ax, heading in zip(first_axes[:-1], headings):
            bbox = ax.get_position()
            fig.text(
                (bbox.x0 + bbox.x1) / 2,
                title_bbox.y1 + 0.045,
                heading,
                ha="center",
                va="bottom",
                fontsize=8.0,
                fontweight="bold",
                linespacing=0.95,
            )

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    output_stem.with_suffix(".json").write_text(
        json.dumps(summaries, indent=2) + "\n",
        encoding="utf-8",
    )
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions-csv", type=Path, required=True)
    parser.add_argument("--calibration-metrics", type=Path, required=True)
    parser.add_argument("--output-stem", type=Path, required=True)
    args = parser.parse_args()
    build_figure(args.predictions_csv, args.calibration_metrics, args.output_stem)


if __name__ == "__main__":
    main()
