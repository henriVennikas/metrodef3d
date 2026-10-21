"""Generate article scalar error and prediction diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


TARGETS = [
    ("centerline_length", "Centerline length", "mm"),
    ("mean_width", "Mean width", "mm"),
    ("max_width", "Maximum width", "mm"),
    ("crack_area", "Crack area", r"mm$^2$"),
]


def _format_small(value):
    value = float(value)
    if value == 0:
        return "0"
    if abs(value) >= 10:
        return f"{value:.0f}"
    if abs(value) >= 1:
        return f"{value:.1f}"
    return f"{value:.2g}"


def _physical_boxplot(
    ax,
    values,
    color,
    unit,
    xlim,
    *,
    zero_line=False,
    row_label=None,
    show_xlabel=True,
    show_bottom_ticks=True,
):
    ax.boxplot(
        values,
        orientation="horizontal",
        widths=0.38,
        patch_artist=True,
        showmeans=True,
        boxprops={"facecolor": color, "edgecolor": "#3f4a56", "linewidth": 0.8},
        medianprops={"color": "#20242a", "linewidth": 1.1},
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
    if zero_line:
        ax.axvline(0, color="#222222", linestyle=(0, (2, 2)), linewidth=0.8, alpha=0.7)
    ax.set_xlim(xlim)
    ax.text(
        0.99,
        0.80,
        f"med. {_format_small(np.median(values))} {unit}",
        ha="right",
        va="center",
        fontsize=6.2,
        color="#20242a",
        transform=ax.transAxes,
    )
    if row_label is not None:
        ax.text(
            -0.050,
            0.50,
            row_label,
            ha="right",
            va="center",
            fontsize=7.0,
            fontweight="bold",
            color="#20242a",
            transform=ax.transAxes,
            clip_on=False,
        )
    ax.set_xlabel(unit if show_xlabel else "", fontsize=6.6, labelpad=0.8)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=6.2, pad=0.8, labelbottom=show_bottom_ticks)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.grid(axis="x", color="#dfe4ea", linewidth=0.55, alpha=0.85)

    # Physical-unit distributions have no per-observation relative-error axis.

    for spine in ax.spines.values():
        spine.set_color("#7c858f")
        spine.set_linewidth(0.7)


def _physical_error_panel(
    ax,
    signed_values,
    absolute_values,
    unit,
    xlim,
    *,
    annotate_medians=True,
    show_row_labels=True,
):
    box = ax.boxplot(
        [signed_values, absolute_values],
        orientation="horizontal",
        positions=[1.32, 0.68],
        widths=0.34,
        patch_artist=True,
        showmeans=True,
        boxprops={"edgecolor": "#3f4a56", "linewidth": 0.8},
        medianprops={"color": "#20242a", "linewidth": 1.1},
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
            "alpha": 0.22,
            "markersize": 2.0,
        },
    )
    colors = ["#86a8c9", "#d7a35f"]
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
    for flier, color in zip(box["fliers"], colors):
        flier.set_markerfacecolor(color)
        flier.set_markeredgecolor(color)

    ax.axvline(0, color="#222222", linestyle=(0, (2, 2)), linewidth=0.8, alpha=0.7)
    ax.set_xlim(xlim)
    ax.set_ylim(0.30, 1.70)
    ax.set_yticks([1.32, 0.68])
    ax.set_yticklabels(
        ["signed", "absolute"] if show_row_labels else [],
        fontsize=7.0,
        fontweight="bold",
    )
    ax.tick_params(axis="y", length=0, pad=4)
    ax.set_xlabel(unit, fontsize=6.8, labelpad=1.0)
    ax.tick_params(axis="x", labelsize=6.4, pad=1.0)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.grid(axis="x", color="#dfe4ea", linewidth=0.55, alpha=0.85)

    if annotate_medians:
        for y, values in [(1.32, signed_values), (0.68, absolute_values)]:
            ax.text(
                0.985,
                y,
                f"med. {_format_small(np.median(values))} {unit}",
                ha="right",
                va="center",
                fontsize=6.1,
                color="#20242a",
                transform=ax.get_yaxis_transform(),
            )

    # Physical-unit distributions have no per-observation relative-error axis.

    for spine in ax.spines.values():
        spine.set_color("#7c858f")
        spine.set_linewidth(0.7)


def _prediction_panel(ax, actual, pred, unit, *, show_axis_names=True):
    ax.scatter(actual, pred, s=6, color="#405a76", alpha=0.25, linewidths=0)
    finite = np.asarray([actual, pred])
    lo = np.percentile(finite, 0.5)
    hi = np.percentile(finite, 99.5)
    span = hi - lo
    lo -= span * 0.05
    hi += span * 0.05
    ax.plot([lo, hi], [lo, hi], color="#20242a", linewidth=0.8, linestyle=(0, (3, 2)))
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(f"truth ({unit})" if show_axis_names else unit, fontsize=7)
    ax.set_ylabel(f"prediction ({unit})" if show_axis_names else unit, fontsize=7)
    ax.tick_params(axis="both", labelsize=6.5, pad=1.5)
    ax.grid(color="#dfe4ea", linewidth=0.55, alpha=0.85)
    for spine in ax.spines.values():
        spine.set_color("#7c858f")
        spine.set_linewidth(0.7)


def build_figure(predictions_csv: Path, output_stem: Path) -> None:
    df = pd.read_csv(predictions_csv)
    df = df[df["visible_actual"] > 0].copy()

    fig = plt.figure(figsize=(10.8, 9.0))
    outer = GridSpec(
        nrows=len(TARGETS),
        ncols=1,
        figure=fig,
        hspace=0.25,
    )

    summaries = {"n_visible_positive": int(len(df)), "targets": {}}
    signed_errors_by_target = []
    abs_errors_by_target = []
    signed_rel_by_target = []
    abs_rel_by_target = []
    actual_by_target = []
    pred_by_target = []

    for name, _label, _unit in TARGETS:
        actual = df[f"{name}_actual"].to_numpy(float)
        pred = df[f"{name}_mu"].to_numpy(float)
        signed_error = pred - actual
        abs_error = np.abs(signed_error)
        signed_rel = signed_error / actual * 100.0
        abs_rel = np.abs(signed_rel)
        signed_errors_by_target.append(signed_error)
        abs_errors_by_target.append(abs_error)
        signed_rel_by_target.append(signed_rel)
        abs_rel_by_target.append(abs_rel)
        actual_by_target.append(actual)
        pred_by_target.append(pred)

        summaries["targets"][name] = {
            "median_truth": float(np.median(actual)),
            "bias": float(np.mean(signed_error)),
            "median_signed_error": float(np.median(signed_error)),
            "mae": float(np.mean(abs_error)),
            "median_absolute_error": float(np.median(abs_error)),
            "mean_signed_relative_error_percent": float(np.mean(signed_rel)),
            "median_signed_relative_error_percent": float(np.median(signed_rel)),
            "mare_percent": float(np.mean(abs_rel)),
            "median_absolute_relative_error_percent": float(np.median(abs_rel)),
            "under_prediction_fraction": float(np.mean(signed_error < 0)),
            "over_prediction_fraction": float(np.mean(signed_error > 0)),
        }

    for row, ((name, label, unit), signed_error, abs_error, signed_rel, abs_rel, actual, pred) in enumerate(
        zip(
            TARGETS,
            signed_errors_by_target,
            abs_errors_by_target,
            signed_rel_by_target,
            abs_rel_by_target,
            actual_by_target,
            pred_by_target,
        )
    ):
        block = outer[row, 0].subgridspec(
            nrows=2,
            ncols=2,
            height_ratios=[0.24, 1.0],
            width_ratios=[2.25, 1.75],
            hspace=0.18,
            wspace=0.26,
        )

        title_ax = fig.add_subplot(block[0, :])
        title_ax.axis("off")
        title_ax.text(
            0.5,
            0.66,
            f"{label} ({unit})",
            ha="center",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            transform=title_ax.transAxes,
        )

        median_truth = float(np.median(actual))
        error_xlim = (-0.20 * median_truth, 0.20 * median_truth)

        error_ax = fig.add_subplot(block[1, 0])
        _physical_error_panel(
            error_ax,
            signed_error,
            abs_error,
            unit,
            error_xlim,
        )

        pred_ax = fig.add_subplot(block[1, 1])
        _prediction_panel(pred_ax, actual, pred, unit)

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)

    output_stem.with_suffix(".json").write_text(json.dumps(summaries, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions-csv", type=Path, required=True)
    parser.add_argument("--output-stem", type=Path, required=True)
    args = parser.parse_args()
    build_figure(args.predictions_csv, args.output_stem)


if __name__ == "__main__":
    main()
