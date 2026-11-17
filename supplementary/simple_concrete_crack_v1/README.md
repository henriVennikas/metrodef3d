# Simple Concrete Crack Dataset — supplementary material

This material accompanies the **MetroDef3D Simple Concrete Crack Dataset**
(seeds 1–10,000). Dataset **v2** has version DOI
[10.5281/zenodo.24326086](https://doi.org/10.5281/zenodo.24326086) and supplies
updated reference values alongside the unchanged image archives. Follow the
[v2 loading instructions](../../docs/dataset-v2.md) to select these references
without overwriting the original files.

The retained models were trained and selected using **v1.0** references
([DOI 10.5281/zenodo.21340378](https://doi.org/10.5281/zenodo.21340378)).
The v2 comparison re-evaluates fixed predictions and records interval calibration
separately. It does not retrain the models. The directory name
`simple_concrete_crack_v1` is retained as a stable path for this dataset family.

The models and studies form an initial feasibility study of synthetic data for
training AI/ML measurement-prediction systems and benchmarking their performance.
The images have explicitly defined geometric reference quantities. These support
comparison of both measurement predictions and prediction intervals.

MetroDef3D itself is the data generator. This directory groups the additional
models, experiments and supporting material for its first dataset. The
[generator recipes](../../examples/) remain separate, and installing the generator
does not install the model package or its PyTorch dependencies.

## Models and reproducible inference

- [Inference package](inference/README.md): the retained transformer, adapted
  ResNet-50 and adapted ConvNeXt-Tiny; workflows for the frozen test partition,
  generated samples and photographs with known physical scale.
- [Release validation](inference/VALIDATION.md): exact export/source checks and
  full-test comparisons between original H100 and local Mac inference.
- [Model asset manifest](inference/models_manifest.json): separate weight
  archives with configurations, frozen calibration, seed partitions and hashes.

The model release and this directory reorganization are currently prepared
locally for review. No model release has been published. Weight files are kept
outside Git. Inference on new appearances or real photographs is an exploratory
extension of the synthetic benchmark.

## Supporting studies

| Study | Contents |
|---|---|
| [Three-model benchmark](studies/model_benchmark/README.md) | Original v1.0 test references and predictions, configurations, point-error and interval statistics, diagnostics and verification scripts. |
| [Conventional image-processing benchmark](studies/classical_benchmark/README.md) | Frozen thresholding, component filtering, skeletonization and geometric measurement pipeline, validation selection, common-test comparison and separate reference-mask diagnostic. |
| [Independent reference verification](studies/reference_validation/README.md) | Analytical export checks, numerical sensitivity and a read-only dataset audit. Dated record of clipping defects, followed by the separate correction study. |
| [Reference correction and benchmark impact](studies/reference_correction/README.md) | v2 reference correction for 142 observations and frozen-prediction comparisons, including validation-only recalibration. Original data and results retained. |
| [Real-image transfer](studies/real_image_transfer/README.md) | Four crack photographs, paired scale targets, calibration records, annotations, physical scale maps and measurement-prediction comparisons. |
| [Background sensitivity](studies/fixed_geometry_background_sensitivity/README.md) | Eight fixed geometries across eight procedural and sixteen photographic surface conditions, with all 192 observations and their results. |

The background study combines surface photographs with synthetic crack geometry;
its observations are controlled appearance tests. The real-image study provides
exploratory transfer examples. Synthetic prediction bounds exclude scale and
annotation uncertainty and do not establish field coverage.

The [background-study browser](studies/fixed_geometry_background_sensitivity/results/full_study/report.html)
provides an interactive overview; open the downloaded HTML locally to use it.
Study-specific commands and file descriptions are in the linked READMEs.

## Navigation and licences

The [study index](../../studies/README.md) provides direct access to the experiments and supporting records.

Software uses [Apache-2.0](../../LICENSE). Documentation and study data use
[CC BY 4.0](../../LICENSE-DATA.md), subject to the stated scope and any identified
third-party terms. Model cards document the prepared weight assets.

## Common real-image comparison of retained methods

The [common real-image comparison](studies/expanded_real_images/all_methods/README.md) evaluates the three retained learned models and the frozen conventional pipeline on the same 26 annotated images. It provides paired errors, bounds and descriptive summaries with the stated training-variability and sampling limitations. The earlier five-image study is preserved as an archive. The study is prepared locally for review.

## Scale and annotation uncertainty example

The [IMG_8579 uncertainty study](studies/uncertainty_example/README.md) propagates independent Metrosert measurements through the scanner, paper target and image scale, and compares five annotations. It separates evaluated reference components, shared-scale model sensitivity and remaining unquantified effects. This local example preserves the earlier studies and their original results.

- [Expanded real-image evaluation and rotation sensitivity](studies/expanded_real_images/README.md): 26 original-orientation observations evaluated by all four methods, frozen annotations and scale maps, plus a separate four-real/ten-synthetic rotation panel. Local study supplement.

- [Repeated annotation comparison](studies/annotation_repeatability/README.md): four new passes plus the adopted original for IMG_8184 and IMG_8162, with IMG_8579 as a separate comparison. Includes within-operator spread and annotation-order sensitivity. Local study supplement.

- [Evaluated uncertainty of individual real-image references](studies/reference_uncertainty/README.md): image-specific scale propagation and single-annotation variability for IMG_8184 and IMG_8162, retaining the original reference values.
