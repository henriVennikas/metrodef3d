# Classical image-processing baseline: frozen test results

Study results, 6 November 2026.

The same 1494 synthetic test identities were evaluated, including the zero-reference seed 1625. MARE uses 1493 positive references. The neural results below are the original retained benchmark predictions, not newly trained models. Test results have not been used to adjust the classical pipeline.

## Point predictions

| Method | Length MARE (%) | Mean-width MARE (%) | Max-width MARE (%) | Area MARE (%) |
|---|---:|---:|---:|---:|
| Transformer | 2.04 | 2.05 | 2.54 | 2.44 |
| ResNet-50 | 4.60 | 4.13 | 5.04 | 6.34 |
| ConvNeXt-Tiny | 6.37 | 4.00 | 4.88 | 7.34 |
| Classical image-only | 8.60 | 18.06 | 27.05 | 20.24 |
| Reference-mask diagnostic | 0.51 | 0.57 | 5.42 | 0.11 |

The reference-mask diagnostic receives privileged geometric information. It isolates the geometric extraction stage and is not an image-only competitor or an independent validation of the generator.

## Classical errors and empirical bounds

| Quantity | MAE | RMSE | Bias | Residual radius | Test coverage (%) | Mean bound width |
|---|---:|---:|---:|---:|---:|---:|
| Length (mm) | 9.595 | 29.04 | 5.56 | 53.16 | 94.51 | 105.4 |
| Mean width (mm) | 0.1464 | 0.1874 | -0.1349 | 0.2964 | 95.85 | 0.5921 |
| Maximum width (mm) | 0.2475 | 0.6857 | 0.1396 | 1.534 | 96.18 | 2.537 |
| Area (mm2) | 18.35 | 35.36 | -10.39 | 41.34 | 94.24 | 81.09 |

The selected configuration is `closing_s15_r0.35_c0`. Selection used 256 validation cases. Residual radii use a separate 1237 validation cases. Seed 551 was excluded from validation under the development instructions, leaving the original test partition unchanged. Bounds are symmetric empirical absolute-residual bounds clipped at zero, rather than learned observation-dependent bounds. Their coverage does not include physical measurement-chain uncertainty or imply coverage on real photographs.

There were **3 empty predictions** in the common test partition. All predictions and references, including failures and the zero-reference case, are retained in `results/`.

## Development record and limitations

The first local-brightness implementation gave very large validation errors on broad dark rendered regions. Its complete settings, code and results are retained in `development/iteration_1_local_brightness/`. Before any test evaluation, the same tuning subset was used to compare Gaussian and morphological-closing background estimates with a minimum contrast condition. The final selection searched 32 configurations. This makes the tuning subset a development resource, not an independent performance estimate. The residual-calibration and test sets were not used for algorithm development.

The estimator assumes simple elongated components. It traces one dominant path per component, may confuse texture or dark surface regions with cracks, and can omit small or fragmented regions. Maximum width uses image-derived normals and can differ from construction-normal widths. Rasterization and skeletonization remain visible even with the reference mask. Directional scale maps are treated as locally orthogonal; perspective shear is not encoded by those sidecars. These assumptions must accompany the comparison. Large dark rendered regions observed during development also warrant a separate image-quality review. Disagreement with a construction reference does not alone establish whether an individual case is a segmentation failure or a rendering/reference mismatch. No new test exclusions were introduced.

The baseline demonstrates a reproducible conventional pipeline on common images and references. It does not establish the performance of all classical algorithms, or a general model ranking. Real-image application remains a separate next step.

## Runtime and verification

- Parameter selection: 360.6 s for 256 images x 32 configurations.
- Residual calibration: 44.8 s for 1237 images.
- Test plus reference-mask diagnostic: 373.5 s for 1494 paired evaluations.
- Four local CPU workers; no GPU, paid compute or neural training. Wall times include data loading and computation. They are not directly comparable with earlier GPU inference timings.
- Exact test identity agreement and reference agreement within float32 rounding tolerance verified against the retained model CSVs.
- Metrics recomputed from exported CSVs; frozen source hashes and split disjointness verified.
- `qa/` shows the first six test IDs and the largest-error cases, explicitly chosen after evaluation for diagnosis. They illustrate diagnostic cases rather than a representative performance sample.

See `README.md` for the method, assumptions, citations and reproduction commands, and `verification.json` for numerical checks.
