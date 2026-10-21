# Simple Concrete Crack Dataset v1.0 — supplementary material

This material accompanies the **MetroDef3D Simple Concrete Crack Dataset v1.0**
(seeds 1–10,000), published on Zenodo:
[DOI 10.5281/zenodo.21340378](https://doi.org/10.5281/zenodo.21340378).
The dataset images remain distributed through Zenodo.

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
| [Three-model benchmark](studies/model_benchmark/README.md) | Common test references and predictions, configurations, point-error and interval statistics, diagnostics and verification scripts. |
| [Real-image transfer](studies/real_image_transfer/README.md) | Four crack photographs, paired scale targets, calibration records, annotations, physical scale maps and measurement-prediction comparisons. |
| [Background sensitivity](studies/fixed_geometry_background_sensitivity/README.md) | Eight fixed geometries across eight procedural and sixteen photographic surface conditions, with all 192 observations and their results. |

The background study combines surface photographs with synthetic crack geometry;
its observations are controlled appearance tests. The real-image study provides
exploratory transfer examples. Synthetic prediction bounds exclude scale and
annotation uncertainty and do not establish field coverage.

The [background-study browser](studies/fixed_geometry_background_sensitivity/results/full_study/report.html)
provides an interactive overview; open the downloaded HTML locally to use it.
Study-specific commands and file descriptions are in the linked READMEs.

## Manuscript access and licences

The former [studies entry point](../../studies/README.md) remains available so
reviewers following the submitted manuscript can find the relocated material.

Software uses [Apache-2.0](../../LICENSE). Documentation and study data use
[CC BY 4.0](../../LICENSE-DATA.md), subject to the stated scope and any identified
third-party terms. Model cards document the prepared weight assets.
