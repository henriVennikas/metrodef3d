# Three-model measurement benchmark

Benchmark study accompanying the third manuscript submission.

The benchmark compares direct scalar predictions and asymmetric intervals from a
transformer, an adapted ResNet-50, and an adapted ConvNeXt-Tiny. Length, mean width,
maximum width and area use the same construction references. These are individual
trained systems under a shared recipe, not architecture-wide rankings.

Archived run identifiers in the configurations use public labels. Checkpoint
hashes and numerical results are unchanged.

## Results and files

`comparison.csv` contains the common test metrics for all models. Each model
folder contains validation/test predictions, the split manifest, configuration,
validation-derived interval factors, `statistics.md`/`.json`, and `diagnostics.pdf`
/`.png`. The per-model diagnostics retain the detailed distribution and calibration
views; their numerical summaries include quartiles, RMSE, R² and interval metrics. Distribution panels use 1493 positive-reference observations;
aggregate RMSE, R² and interval statistics include all 1494 test observations.
Interval-width axes expand to include every plotted width; their ranges vary by
model. Error and interval-width panels use physical-unit axes only (mm or mm²).
Error panels retain limits of ±0.20 times the median reference, expressed in
physical units. No percentage axis is inferred from that population median.
Per-observation relative errors use each observation's own reference and remain
in the statistics and separate comparative plots. Normalized-residual panels
retain ±3; observations outside the displayed ranges remain in the supplied
predictions and statistics.
`interval_tail_diagnostics.json` retains the ResNet zero-reference failure.

`intermodel_comparison.pdf` / `.png` retain the full four-by-three comparative
figure: signed relative errors, calibrated coverage with Wilson intervals, and
calibrated interval widths. Edge markers and counts indicate off-scale values;
all observations remain in the statistics. `intermodel_comparison.json` records
the display limits and tail counts. `intermodel_table.tex` contains the compact
comparative manuscript table; `comparison.csv` supplies its full-precision metrics.
The paper itself uses a compact two-by-two absolute-relative-error figure.
Regenerate the full supplementary view with `python tools/make_intermodel_comparison.py`.

| Model | Length MARE | Mean width MARE | Maximum width MARE | Area MARE |
|---|---:|---:|---:|---:|
| Transformer | 2.04% | 2.05% | 2.54% | 2.44% |
| ResNet-50, per-image BatchNorm | 4.60% | 4.13% | 5.04% | 6.34% |
| ConvNeXt-Tiny | 6.37% | 4.00% | 4.88% | 7.34% |

The transformer has lower errors and interval scores in these runs. Raw and
calibrated coverage, mean interval width and normalized interval score are in the
CSV. Calibration targets 95% validation coverage, not a guarantee of test or
real-image coverage.

## Shared protocol

- Dataset: MetroDef3D Simple Concrete Crack Dataset v1.0, perspective-area.
- 40 quality-manifest exclusions; 6972/1494/1494 geometry-disjoint split,
  split seed 20260702. Validation/test identities and numerical references match.
- RGB [0,1] plus geometric-mean physical pixel scale; four channels, 1024² input.
- Training-derived target standardization; no ImageNet pretraining.
- Four direct scalar heads with positive asymmetric interval deltas, plus dense
  defect, centreline, boundary and width supervision. CNN heads are adaptations,
  not stock classifiers or segmentation-plus-morphology pipelines.
- AdamW, learning rate 2e-4, weight decay 0.05, five warmup epochs then cosine;
  50 epochs, batch one, accumulation 24, bfloat16 on H100, seed 20260702.
- Selected epochs: transformer 49, ConvNeXt-Tiny 50, final ResNet-50 47.
- Each model/target has an expansion-only factor from the validation 0.95 quantile.
  Interval score uses alpha 0.05; relative denominator floor is 2% of the training
  mean. The zero-reference test sample remains in all metrics except MARE.

ResNet requires **per-image BatchNorm statistics with batch size one**, dropout
disabled and no weight or stored-buffer updates. Ordinary `model.eval()` with
stored BatchNorm statistics does not reproduce the reported result. A diagnostic
using training/validation data identified the mismatch; its epoch-10 lineage was
continued through epoch 50 with the original schedule. The final checkpoint and
calibration were frozen before test evaluation. The same test set had previously
been used for the initial benchmark; it was excluded from the diagnostic and
continuation, but is not newly acquired data. The recipe was developed around the
transformer; no equal architecture-specific tuning or repeated-seed ranking is
claimed. The failed stored-statistics result is diagnostic history, not the
ResNet result in this comparison.

## Reproduce the diagnostics

Python with NumPy, pandas and matplotlib:

```sh
python tools/make_fig4_combined_diagnostics.py \
  --predictions-csv resnet50/test_predictions.csv \
  --calibration-metrics resnet50/calibration.json \
  --output-stem resnet50/diagnostics
```

Use `verify_metrics.py` to recompute common metrics and check paired references.
The model/config records describe the adapters and inference policy. Retained
model implementations are provided in the [inference package](../../inference/README.md). No model checkpoints or training dataset images
are duplicated in this supplement. Supplied predictions support reanalysis
without training. Code follows the repository Apache-2.0 license; result data and
figures are provided under CC BY 4.0.

## Retained-model inference

The optional [inference package](../../inference/README.md) supplies the frozen
model implementations, input conventions and commands to re-run this test
partition. Its [validation report](../../inference/VALIDATION.md) separates exact
export/source checks from cross-device inference differences. Checkpoints are
prepared as separate release assets; this local release candidate is awaiting
review and has not yet been published.
