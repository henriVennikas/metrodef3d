# Release validation — 21 October 2026

This report concerns the local release candidate. No weights were retrained,
no interval factors were refitted and no test samples were removed. The submitted
manuscript and original benchmark remain unchanged.

## What was checked

- All exported tensors equal their original checkpoint tensors exactly. The
  selected epochs are 49 (transformer), 50 (ConvNeXt) and 47 (ResNet).
- On a fixed test image, the original training implementations and the release
  implementations produce bitwise-identical CPU float32 scalar outputs for all
  three models. Preprocessed inputs and physical-unit denormalisation also match.
- Dense-head enabled/disabled scalar parity, order independence, disabled dropout
  and unchanged buffers were checked for each retained model.
- Fourteen automated tests cover resizing, original/model-grid scale conventions,
  invalid scales, portable paths, duplicate seeds, zero-reference metrics,
  checkpoint integrity, batch size, RGB range and frozen calibration.
- All 84 saved table-value audit checks pass. This audit is separate from inference.
- Each model was actually run on all 1,494 test images on the local Apple Metal
  GPU in float32. Test identities and geometric reference values match exactly.
- Each model also ran the generated-data workflow on existing rendered seed 12345
  outside the frozen split and the image workflow on IMG_8184, with dense outputs.
  The latter uses the archived 1024-grid scale map. Transformer point outputs
  differ from the archived CPU study by at most 0.00000763 mm. The generated
  example is a workflow check, not a new generalisation assessment.

## Full test inference comparison

The original H100 evaluation used bfloat16 autocast; the local Mac evaluation
uses float32. Accordingly these are close numerical reproductions, not bitwise
replays of the H100 output. The CUDA/bfloat16 command is included but was not
executed on a CUDA GPU during this local preparation. No tolerance was selected
to conceal a discrepancy; all changes are recorded in the comparison JSONs.

All MARE and coverage values below are percentages. MARE excludes the single
zero-reference observation; coverage and the other metrics include it.

| Model | Measurand | Original MARE | Local MARE | Original calibrated coverage | Local coverage |
|---|---|---:|---:|---:|---:|
| Transformer | Length | 2.0360 | 2.0258 | 95.1807 | 95.2477 |
| Transformer | Mean width | 2.0473 | 2.0417 | 93.3735 | 93.4404 |
| Transformer | Maximum width | 2.5421 | 2.5330 | 94.4444 | 94.7122 |
| Transformer | Area | 2.4411 | 2.4092 | 94.7122 | 95.1138 |
| ConvNeXt-Tiny | Length | 6.3663 | 6.3462 | 95.7831 | 95.9170 |
| ConvNeXt-Tiny | Mean width | 4.0002 | 4.0005 | 93.4404 | 93.4404 |
| ConvNeXt-Tiny | Maximum width | 4.8814 | 4.8737 | 95.0469 | 95.0469 |
| ConvNeXt-Tiny | Area | 7.3438 | 7.3318 | 95.9839 | 95.9839 |
| ResNet-50 | Length | 4.6005 | 4.6312 | 95.3146 | 95.1807 |
| ResNet-50 | Mean width | 4.1309 | 4.1496 | 93.7751 | 93.8420 |
| ResNet-50 | Maximum width | 5.0384 | 5.0922 | 95.3146 | 95.0469 |
| ResNet-50 | Area | 6.3422 | 6.4364 | 94.9130 | 94.9130 |

The largest MARE change is **0.0942 percentage points**; the largest
calibrated coverage change is **0.4016 percentage points**. The original
point-error ordering of these retained models is preserved for each measurand.
Coverage differences can arise when small numerical shifts move references
across a bound. The original calibration factors were retained in every case.

| Model | Full-test inference time | Samples |
|---|---:|---:|
| Transformer | 360.6 s | 1494 |
| ConvNeXt-Tiny | 166.2 s | 1494 |
| ResNet-50 | 161.0 s | 1494 |

Total measured evaluation-loop time: 687.9 s. This includes input loading
and CSV writing, excludes model startup, and is not training time. It is a local
runtime observation rather than a hardware benchmark; other checks ran alongside
parts of the evaluation.

## Recheck or inspect

`validation/<model>/` contains the new prediction CSV, metric JSON, environment,
completion record and full original/local comparison. Every point-error and
interval metric is included: MAE, RMSE, R², positive-reference MARE, bias, raw
and calibrated coverage/width, and calibrated relative interval score. The
original predictions remain under `reference/<model>/`.

`validation/source_parity.json`, `workflow_checks.json`,
`reference_metric_audit.json` and `package_versions.json` record the other checks.
The model archives have internal file checksums and an external asset manifest;
every compressed member was read back and verified against its staged source.

Use the README commands to re-run on the released dataset. On CUDA, select
`--precision bfloat16` to match the original precision policy; device and library
versions may still affect numerical reproducibility. The supplied comparison
script requires the complete frozen partition and exact paired references.
