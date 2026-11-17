# Conventional image-processing benchmark

Conventional image processing on the first MetroDef3D dataset. Frozen evaluation results and their limits are summarized in [REPORT.md](REPORT.md).

## Purpose and input

Compare a conventional image-processing pipeline against the same construction-defined quantities used for the trained transformer, ResNet-50 and ConvNeXt-Tiny. The input is the native 1024 x 1024 RGB image and two directional physical pixel-scale arrays from **MetroDef3D Simple Concrete Crack Dataset v1.0**, [Zenodo DOI 10.5281/zenodo.21340378](https://doi.org/10.5281/zenodo.21340378). The image-only estimator never receives reference quantities, boundaries, centreline points or defect masks.

This is a documented classical baseline, not an implementation claimed to represent the best available traditional crack measurement algorithm.

## Pipeline

1. Convert RGB to luminance using OpenCV RGB-to-gray conversion.
2. Estimate local background brightness with a Gaussian filter or a grayscale morphological closing (black top-hat background). Classify a pixel as dark crack when its luminance is below a fixed fraction of the local estimate and the background-minus-pixel contrast exceeds 0.02 on the [0, 1] luminance scale. Avoid assuming a single global brightness under shadows.
3. Optionally close one-pixel gaps with a 3 x 3 square kernel. Identify 8-connected components and discard components smaller than 32 pixels.
4. Thin each component with the scikit-image 2D Zhang skeletonization implementation. Build an 8-neighbour graph, suppressing redundant diagonal shortcuts where an orthogonal connection exists. Extract a dominant path with two geodesic sweeps. This returns the diameter of a tree; it is a heuristic for loops. Retain paths of at least 20 pixels and length-to-median-opening ratio at least 3.
5. Trim terminal thinning artefacts by one estimated local opening width, capped at 25 path samples and limited by available path length. Smooth coordinates with Gaussian sigma 2 path samples. Estimate tangent direction using a +/-5-sample neighbourhood and extend the terminal points back to the observed opening or image boundary. These constants were fixed during training-image/analytical-fixture development before validation selection.
6. Sum physical segment lengths on retained dominant paths. All eligible components are included. For a component with branches, the area includes its retained mask but length follows only its dominant path. This is a stated limitation of this simple-crack baseline.
7. Sum local pixel areas for crack area. Calculate mean width as area divided by total estimated length, matching the published reference definition.
8. Measure mask-boundary crossings along normals to the smoothed pixel-space path, at 0.5-pixel search increments with interpolation, searching at most 128 pixels in each direction. Convert using directional scale and take the maximum. Exclude cross-sections clipped by the image border where other complete cross-sections exist. Pixel-space normals are an approximation to physical normals under anisotropy. This estimate need not equal the generator's construction-normal width at bends, corners or clipping.

The directional-scale metric uses `sqrt((dx*sx)^2 + (dy*sy)^2)` for length and `sx*sy` for pixel area. The sidecars contain axis lengths but no angle between projected axes. We therefore assume local orthogonality. These formulas are not exact for arbitrary perspective shear. The reference-mask diagnostic shows the effects of this assumption and rasterization. We do not use construction geometry to correct image-only predictions.

Method references: [OpenCV filtering and morphology documentation](https://docs.opencv.org/doc/doxygen/html/d4/d86/group__imgproc__filter.html) and [scikit-image skeletonization documentation](https://scikit-image.org/docs/stable/auto_examples/edges/plot_skeleton.html), which identifies the Zhang and Suen thinning method. The complete pipeline and geometric estimator are the baseline assembled for this study.

## Split discipline

- Preserve the original 6972/1494/1494 train/validation/test manifest and its 40 exclusions.
- Seed 551 occurs in the retained validation manifest but was previously identified as a failed Boolean-cut geometry. It is excluded from this baseline's selection/calibration. This leaves 1493 eligible validation observations; the common 1494 test identities are unchanged.
- Inspect only the first 12 training images for implementation development. Validate the geometry routines on independent analytical binary strips and empty images.
- Use PRNG seed 20261106 to select 256 validation observations for parameter selection. The remaining 1237 form a disjoint residual-calibration set.
- Compare 32 settings: Gaussian sigma or elliptical grayscale-closing radius 15 or 31 pixels, dark ratio 0.20/0.35/0.50/0.65, and binary closing off/on. Minimize the unweighted mean of the four positive-reference MARE values. Break a tie by candidate identifier.
- Freeze the selected configuration and source hashes before residual calibration and test evaluation. Freeze residual radii before test evaluation. No test-result tuning.

The first local-brightness trial was inadequate on broad dark regions in the tuning images. Its code, protocol and results are preserved in `development/iteration_1_local_brightness/`. The revised candidate grid adds closing-based background estimation and a minimum contrast condition, using the same tuning subset and no test images. The protocol, exact identities and all current candidates are in `protocol.json`. `selected.json` records the configuration and code hashes. `calibration.json` records validation residual radii. These files must not be overwritten to disguise further experiments.

## Bounds and metric interpretation

The classical estimator has no intrinsic uncertainty head. For comparison, a separate empirical calibration uses the per-measurand 95th percentile (`higher` sample quantile) of absolute errors on the 1237 reserved validation observations. The resulting interval is `[max(0, prediction-radius), prediction+radius]`. It has constant radius for each measurand, unlike the learned models' observation-dependent asymmetric outputs. These are residual-based prediction bounds, not a metrological uncertainty budget or a promised coverage level in a different domain.

MAE, RMSE, bias and R-squared use all test observations. MARE uses positive reference values only. Keep the valid zero-reference test observation; do not divide its error by zero. Interval score uses alpha 0.05 and the same training-derived normalization floors as the retained benchmark. Bounds exclude physical-scale and annotation uncertainty, as do the original model bounds.

References in original prediction CSVs were stored as float32. This baseline retains the six-decimal JSON references. Verification checks agreement to float32 rounding tolerance and reports the difference. No rows may be silently dropped.

## Reference-mask diagnostic

Rasterize the exported visible polygon at pixel centres, then run the same frozen geometric estimator without RGB segmentation or morphological closing. This uses privileged reference geometry and must be labelled **reference-mask diagnostic**, never counted as an image-only competitor. It separates rasterization, skeletonization, width-definition and scale-metric effects from segmentation errors. It does not independently validate the generator's references, and is not a mathematical lower bound on every estimator's errors.

## Reproduction

Install the versions in `requirements-frozen.txt` into an isolated Python environment. Run from this directory:

```sh
python -m pytest test_pipeline.py -q
python run_benchmark.py prepare --dataset PATH_TO_DATASET --split PATH_TO_SPLIT_JSON --model-config PATH_TO_TRANSFORMER_CONFIG
python run_benchmark.py pilot --dataset PATH_TO_DATASET --split PATH_TO_SPLIT_JSON --model-config PATH_TO_TRANSFORMER_CONFIG
python run_benchmark.py tune --dataset PATH_TO_DATASET --split PATH_TO_SPLIT_JSON --model-config PATH_TO_TRANSFORMER_CONFIG
python run_benchmark.py calibrate --dataset PATH_TO_DATASET --split PATH_TO_SPLIT_JSON --model-config PATH_TO_TRANSFORMER_CONFIG
python run_benchmark.py test --dataset PATH_TO_DATASET --split PATH_TO_SPLIT_JSON --model-config PATH_TO_TRANSFORMER_CONFIG
```

Use a fresh copy without generated protocol/results to reproduce the entire selection sequence; the commands refuse to overwrite existing run outputs. To repeat only frozen inference, use an isolated copy preserving `protocol.json`, `selected.json` and `calibration.json` but with a fresh `results/` directory. The current outputs and original model/data archives remain untouched.

`results/` holds all candidate predictions, selection scores, calibration and test tables, reference-mask diagnostics and timing logs. `environment.json` records the local CPU environment. Parameters use pixels and must not be transferred to other input resolutions without explicit reconsideration.

## Interpretation of difficult rendered cases

Development images include large dark regions that can dominate a thresholded mask. Keep these cases in the common test population. A large prediction-reference discrepancy does not by itself distinguish an estimator error from a rendering/reference consistency issue. Review those images separately before making a causal attribution; this implementation does not validate the rendering geometry or add new test exclusions.

## Recreate the summary and diagnostics

The adjacent [learned-model benchmark](../model_benchmark/README.md) supplies the retained neural predictions for comparison. After reproducing the frozen outputs, regenerate the report and overlays with:

```sh
python make_report.py --dataset PATH_TO_DATASET
```

The retained [split manifest](../../inference/reference/transformer/split_seeds.json) and [transformer configuration](../../inference/reference/transformer/config.json) can be supplied to the benchmark commands above. Local filesystem paths were removed from the published protocol metadata. The processing code, numeric settings, split identities and saved predictions are unchanged. `export_notes.json` records the metadata relocation.

Software follows the repository [Apache 2.0 licence](../../../../LICENSE). Documentation, data and figures follow [CC BY 4.0](../../../../LICENSE-DATA.md).

## Subsequent reference verification

The [independent export study](../reference_validation/README.md) identified disconnected-visibility reference defects in the released dataset, including 25 test observations. The frozen results here retain the original v1.0 references. The separate [correction study](../reference_correction/README.md) provides the overlay included in **dataset v2**, [DOI 10.5281/zenodo.24326086](https://doi.org/10.5281/zenodo.24326086), and the before/after comparison, without replacing these historical results. Follow the [v2 loading guide](../../../../docs/dataset-v2.md) for current reference loading. The reproduction commands above retain the original references and calibration. The reference-mask diagnostic is not an independent validation of those references.
