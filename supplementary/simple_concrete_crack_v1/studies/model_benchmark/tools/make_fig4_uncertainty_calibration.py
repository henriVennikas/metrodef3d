"""Generate article uncertainty calibration diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator, MaxNLocator


TARGETS = [
    ("centerline_length", "Centerline length", "mm"),
    ("mean_width", "Mean width", "mm"),
    ("max_width", "Maximum width", "mm"),
    ("crack_area", "Crack area", r"mm$^2$"),
]


def _load_interval_scales(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    metrics = json.loads(path.read_text())
    scales = metrics.get("posthoc_calibration", {}).get("interval_scales")
    if scales is None:
        scales = metrics.get("selected", {}).get("interval_scales")
    if scales is None:
        scales = metrics.get("per_target", {}).get("interval_scales")
    if scales is None:
        raise ValueError(f"No posthoc_calibration/selected/per_target interval_scales found in {path}")
    return {str(target): float(scale) for target, scale in scales.items()}


def _format_small(value: float) -> str:
    value = float(value)
    if value == 0:
        return "0"
    if abs(value) >= 10:
        return f"{value:.0f}"
    if abs(value) >= 1:
        return f"{value:.2g}"
    return f"{value:.2g}"


def _style_axes(ax):
    for spine in ax.spines.values():
        spine.set_color("#7c858f")
        spine.set_linewidth(0.7)
    ax.tick_params(labelsize=6.4, pad=1.2)


def _horizontal_box(ax, values, color, xlim=None, median_label=None):
    ax.boxplot(
        values,
        orientation="horizontal",
        widths=0.42,
        patch_artist=True,
        showmeans=True,
        boxprops={"facecolor": color, "edgecolor": "#3f4a56", "linewidth": 0.8},
        medianprops={"color": "#20242a", "linewidth": 1.05},
        meanprops={
            "marker": "D",
            "markerfacecolor": "#20242a",
            "markeredgecolor": "#20242a",
            "markersize": 3.0,
        },
        whiskerprops={"color": "#66717d", "linewidth": 0.8},
        capprops={"color": "#66717d", "linewidth": 0.8},
        flierprops={
            "marker": ".",
            "markerfacecolor": color,
            "markeredgecolor": color,
            "alpha": 0.22,
            "markersize": 2.0,
        },
    )
    if xlim is not None:
        ax.set_xlim(xlim)
    ax.set_yticks([])
    ax.grid(axis="x", color="#dfe4ea", linewidth=0.55, alpha=0.85)
    if median_label is not None:
        ax.text(
            0.985,
            0.82,
            median_label,
            ha="right",
            va="center",
            fontsize=6.2,
            color="#20242a",
            transform=ax.transAxes,
        )
    _style_axes(ax)


def _two_horizontal_boxes(ax, raw_values, calibrated_values, xlim, raw_color, calibrated_color):
    box = ax.boxplot(
        [raw_values, calibrated_values],
        orientation="horizontal",
        positions=[1.32, 0.68],
        widths=0.34,
        patch_artist=True,
        showmeans=True,
        boxprops={"edgecolor": "#3f4a56", "linewidth": 0.8},
        medianprops={"color": "#20242a", "linewidth": 1.05},
        meanprops={
            "marker": "D",
            "markerfacecolor": "#20242a",
            "markeredgecolor": "#20242a",
            "markersize": 3.0,
        },
        whiskerprops={"color": "#66717d", "linewidth": 0.8},
        capprops={"color": "#66717d", "linewidth": 0.8},
        flierprops={
            "marker": ".",
            "alpha": 0.20,
            "markersize": 2.0,
        },
    )
    for patch, color in zip(box["boxes"], [raw_color, calibrated_color]):
        patch.set_facecolor(color)
    for flier, color in zip(box["fliers"], [raw_color, calibrated_color]):
        flier.set_markerfacecolor(color)
        flier.set_markeredgecolor(color)
    ax.set_xlim(xlim)
    ax.set_ylim(0.30, 1.70)
    ax.set_yticks([1.32, 0.68])
    ax.set_yticklabels([])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#dfe4ea", linewidth=0.55, alpha=0.85)
    _style_axes(ax)


def _interval_width_panel(
    ax,
    raw_widths,
    calibrated_widths,
    median_truth,
    unit,
    *,
    annotate_medians=True,
):
    xlim = (0, max(0.30 * median_truth, 1.05 * float(np.max(raw_widths)),
                   1.05 * float(np.max(calibrated_widths))))
    _two_horizontal_boxes(ax, raw_widths, calibrated_widths, xlim, "#d6b07b", "#d8933f")
    if annotate_medians:
        for y, widths in [(1.32, raw_widths), (0.68, calibrated_widths)]:
            ax.text(
                0.985,
                y,
                f"med. {_format_small(np.median(widths))} {unit}",
                ha="right",
                va="center",
                fontsize=6.0,
                color="#20242a",
                transform=ax.get_yaxis_transform(),
            )
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.set_xlabel(unit, fontsize=6.4, fontweight="bold", labelpad=1.0)

    # Physical-unit distributions have no per-observation relative-error axis.


def _normalized_residual_panel(
    ax,
    raw_normalized,
    calibrated_normalized,
    *,
    annotate_medians=True,
):
    ax.axvspan(-1, 1, color="#e9f3ec", alpha=0.9, zorder=0)
    ax.axvline(0, color="#20242a", linestyle=(0, (2, 2)), linewidth=0.8, alpha=0.75)
    ax.axvline(-1, color="#7aa889", linestyle=(0, (2, 2)), linewidth=0.75, alpha=0.9)
    ax.axvline(1, color="#7aa889", linestyle=(0, (2, 2)), linewidth=0.75, alpha=0.9)
    _two_horizontal_boxes(ax, raw_normalized, calibrated_normalized, (-3, 3), "#abcdb8", "#70ad86")
    if annotate_medians:
        for y, normalized in [(1.32, raw_normalized), (0.68, calibrated_normalized)]:
            ax.text(
                0.985,
                y,
                f"med. {_format_small(np.median(normalized))}",
                ha="right",
                va="center",
                fontsize=6.0,
                color="#20242a",
                transform=ax.get_yaxis_transform(),
            )
    ax.xaxis.set_major_locator(FixedLocator([-3, -1, 0, 1, 3]))


def _diagnostics(actual, pred, lower, upper):
    interval_width = upper - lower
    lower_delta = pred - lower
    upper_delta = upper - pred
    residual = actual - pred
    normalized = np.where(residual < 0, residual / lower_delta, residual / upper_delta)
    covered = (actual >= lower) & (actual <= upper)
    return {
        "interval_width": interval_width,
        "normalized": normalized,
        "coverage": float(np.mean(covered)),
    }


def _coverage_label(ax, raw_coverage, calibrated_coverage):
    ax.axis("off")
    ax.text(
        0.50,
        0.73,
        f"Raw {raw_coverage * 100:.0f}%",
        ha="center",
        va="center",
        fontsize=7.4,
        fontweight="bold",
        color="#6f879f",
        transform=ax.transAxes,
    )
    ax.text(
        0.50,
        0.27,
        f"Cal. {calibrated_coverage * 100:.0f}%",
        ha="center",
        va="center",
        fontsize=7.4,
        fontweight="bold",
        color="#4f8a61",
        transform=ax.transAxes,
    )


def _target_summary(diag, actual):
    interval_width = diag["interval_width"]
    normalized = diag["normalized"]
    return {
        "coverage": diag["coverage"],
        "mean_interval_width": float(np.mean(interval_width)),
        "median_interval_width": float(np.median(interval_width)),
        "mean_relative_interval_width_percent": float(np.mean(interval_width / actual * 100.0)),
        "median_relative_interval_width_percent": float(np.median(interval_width / actual * 100.0)),
        "median_normalized_residual": float(np.median(normalized)),
        "fraction_abs_normalized_residual_le_1": float(np.mean(np.abs(normalized) <= 1)),
        "fraction_abs_normalized_residual_gt_3": float(np.mean(np.abs(normalized) > 3)),
    }


def build_figure(predictions_csv: Path, output_stem: Path, calibration_metrics: Path | None = None) -> None:
    df = pd.read_csv(predictions_csv)
    df = df[df["visible_actual"] > 0].copy()
    interval_scales = _load_interval_scales(calibration_metrics)

    fig = plt.figure(figsize=(10.8, 6.1))
    outer = fig.add_gridspec(
        nrows=len(TARGETS),
        ncols=1,
        hspace=0.42,
    )

    summaries = {
        "n_visible_positive": int(len(df)),
        "calibration_metrics": str(calibration_metrics) if calibration_metrics else None,
        "interval_scales": interval_scales,
        "targets": {},
    }
    first_row_axes = None

    for row, (name, label, unit) in enumerate(TARGETS):
        actual = df[f"{name}_actual"].to_numpy(float)
        pred = df[f"{name}_mu"].to_numpy(float)
        raw_lower = df[f"{name}_lower"].to_numpy(float)
        raw_upper = df[f"{name}_upper"].to_numpy(float)
        calibrated_lower = raw_lower.copy()
        calibrated_upper = raw_upper.copy()
        if interval_scales is not None:
            scale = interval_scales[name]
            calibrated_lower = pred - (pred - raw_lower) * scale
            calibrated_upper = pred + (raw_upper - pred) * scale

        raw_diag = _diagnostics(actual, pred, raw_lower, raw_upper)
        calibrated_diag = _diagnostics(actual, pred, calibrated_lower, calibrated_upper)
        median_truth = float(np.median(actual))

        block = outer[row, 0].subgridspec(
            nrows=2,
            ncols=3,
            height_ratios=[0.24, 1.0],
            width_ratios=[0.62, 2.95, 2.95],
            hspace=0.18,
            wspace=0.28,
        )

        title_ax = fig.add_subplot(block[0, :])
        title_ax.axis("off")
        title_ax.text(
            0.5,
            0.66,
            label,
            ha="center",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            transform=title_ax.transAxes,
        )

        label_ax = fig.add_subplot(block[1, 0])
        _coverage_label(label_ax, raw_diag["coverage"], calibrated_diag["coverage"])
        width_ax = fig.add_subplot(block[1, 1])
        _interval_width_panel(
            width_ax,
            raw_diag["interval_width"],
            calibrated_diag["interval_width"],
            median_truth,
            unit,
        )
        residual_ax = fig.add_subplot(block[1, 2])
        _normalized_residual_panel(residual_ax, raw_diag["normalized"], calibrated_diag["normalized"])

        if first_row_axes is None:
            first_row_axes = (label_ax, width_ax, residual_ax, title_ax)

        summaries["targets"][name] = {
            "interval_scale": interval_scales.get(name) if interval_scales else None,
            "raw": _target_summary(raw_diag, actual),
            "calibrated": _target_summary(calibrated_diag, actual),
        }

    if first_row_axes is not None:
        for ax, text in zip(first_row_axes[:3], ("Coverage", "Interval width", "Normalized residual")):
            bbox = ax.get_position()
            title_bbox = first_row_axes[3].get_position()
            fig.text(
                (bbox.x0 + bbox.x1) / 2,
                title_bbox.y1 + 0.030,
                text,
                ha="center",
                va="bottom",
                fontsize=8.2,
                fontweight="bold",
            )

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)

    output_stem.with_suffix(".json").write_text(json.dumps(summaries, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions-csv", type=Path, required=True)
    parser.add_argument("--output-stem", type=Path, required=True)
    parser.add_argument("--calibration-metrics", type=Path, default=None)
    args = parser.parse_args()
    build_figure(args.predictions_csv, args.output_stem, args.calibration_metrics)


if __name__ == "__main__":
    main()
