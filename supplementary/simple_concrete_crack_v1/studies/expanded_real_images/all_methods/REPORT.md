# Common real-image comparison

All four retained methods evaluated on the same 26 annotated images at original orientation. Original adopted references, scale maps, checkpoints, processing settings and synthetic-validation calibration are unchanged. All 416 scalar comparisons were checked. No training or real-image tuning was performed.

These descriptive averages depend on this selected mixture of appearances and openings. Several images share a physical fracture. They are not population performance estimates or statistically stable architecture rankings. Prediction bounds exclude scale and annotation uncertainty. The separate repeat-annotation and Metrosert uncertainty studies do not replace these adopted references.

## Absolute relative differences

Each cell is mean / median absolute relative difference in percent.

| Method | Length | Mean width | Maximum width | Area |
|---|---:|---:|---:|---:|
| Transformer | 19.32 / 18.50 | 32.49 / 15.71 | 40.50 / 41.26 | 35.32 / 21.13 |
| ResNet-50 | 11.03 / 11.40 | 32.90 / 18.57 | 46.37 / 46.05 | 38.56 / 37.04 |
| ConvNeXt-Tiny | 19.88 / 9.79 | 32.31 / 16.52 | 43.53 / 43.97 | 33.74 / 19.53 |
| Conventional | 41.18 / 5.29 | 24.29 / 19.18 | 23.46 / 17.25 | 22.84 / 17.22 |

For this selected set, ResNet-50 has the lowest mean length difference. The conventional pipeline has the lowest mean width and area differences. Its median length difference is also the lowest, but its mean is dominated by a large miss on IMG_8569. The saved path overlay shows many surface-texture components in addition to the main crack. The pipeline retains 333 components, giving a total length of 1092.88 mm against the annotated 125.06 mm (773.9% difference). This observation is retained without tuning or exclusion. The mean and median therefore describe substantially different aspects of its length performance.


## Bounds and runtime

Counts below are reference inclusions out of 26. Higher inclusion should be considered together with interval width and score, reported in [summary.csv](summary.csv). Conventional residual bounds have fixed physical radii and can be very wide for short cracks. They were calibrated on synthetic observations, as were the learned-model bounds.

| Method | Length | Mean width | Maximum width | Area | Runtime (s) |
|---|---:|---:|---:|---:|---:|
| Transformer | 4/26 | 5/26 | 8/26 | 7/26 | 33.9 |
| ResNet-50 | 17/26 | 7/26 | 3/26 | 6/26 | 14.4 |
| ConvNeXt-Tiny | 17/26 | 10/26 | 7/26 | 14/26 | 92.0 |
| Conventional | 23/26 | 17/26 | 20/26 | 20/26 | 6.8 |

## Per-image results

Cells list absolute relative differences (%) in order: length / mean width / maximum width / area. The [full paired table](comparison.csv) retains predictions, references, physical units, raw/calibrated bounds, interval widths and scores.

| Image | Transformer | ResNet-50 | ConvNeXt-Tiny | Conventional |
|---|---|---|---|---|
| [IMG_8117](../inputs/IMG_8117/IMG_8117.jpeg) | 11.6 / 67.2 / 44.4 / 89.0 | 13.2 / 87.3 / 48.1 / 62.5 | 25.0 / 83.1 / 46.4 / 28.7 | 52.7 / 4.2 / 11.5 / 54.7 |
| [IMG_8139](../inputs/IMG_8139/IMG_8139.jpeg) | 51.7 / 78.7 / 19.4 / 8.2 | 7.3 / 82.7 / 15.3 / 67.8 | 7.7 / 49.0 / 0.3 / 32.1 | 1.3 / 4.7 / 46.6 / 6.1 |
| [IMG_8162](../inputs/IMG_8162/IMG_8162.jpeg) | 3.6 / 9.1 / 1.9 / 3.2 | 11.5 / 9.9 / 20.7 / 21.1 | 6.9 / 1.6 / 12.1 / 1.5 | 19.5 / 22.6 / 3.6 / 7.5 |
| [IMG_8169](../inputs/IMG_8169/IMG_8169.jpeg) | 25.0 / 10.0 / 24.3 / 13.2 | 1.7 / 3.3 / 34.3 / 3.3 | 6.8 / 18.2 / 19.7 / 24.4 | 1.3 / 23.3 / 2.2 / 24.3 |
| [IMG_8182](../inputs/IMG_8182/IMG_8182.jpeg) | 2.4 / 12.5 / 3.4 / 8.3 | 12.8 / 19.1 / 0.9 / 35.5 | 5.2 / 5.2 / 8.6 / 2.3 | 0.3 / 18.4 / 15.7 / 18.7 |
| [IMG_8184](../inputs/IMG_8184/IMG_8184.jpeg) | 3.8 / 9.5 / 1.6 / 6.6 | 13.3 / 14.0 / 7.9 / 31.9 | 1.2 / 4.8 / 1.4 / 6.6 | 0.9 / 9.5 / 8.2 / 10.3 |
| [IMG_8485](../inputs/IMG_8485/IMG_8485.jpeg) | 31.6 / 4.3 / 49.4 / 27.8 | 6.6 / 58.3 / 57.2 / 41.6 | 47.8 / 67.1 / 53.3 / 12.9 | 22.2 / 11.6 / 28.4 / 31.3 |
| [IMG_8487](../inputs/IMG_8487/IMG_8487.jpeg) | 7.6 / 0.8 / 38.4 / 6.7 | 12.8 / 3.2 / 44.0 / 15.3 | 8.5 / 7.8 / 40.0 / 13.4 | 0.8 / 12.0 / 18.4 / 11.3 |
| [IMG_8490](../inputs/IMG_8490/IMG_8490.jpeg) | 12.7 / 7.2 / 36.4 / 16.3 | 6.1 / 13.6 / 42.8 / 20.0 | 4.4 / 12.8 / 41.6 / 11.1 | 1.4 / 13.8 / 11.5 / 12.6 |
| [IMG_8493](../inputs/IMG_8493/IMG_8493.jpeg) | 21.9 / 60.5 / 54.7 / 69.3 | 14.3 / 45.1 / 55.7 / 54.6 | 51.7 / 51.9 / 59.4 / 75.9 | 1.3 / 25.4 / 25.4 / 24.4 |
| [IMG_8495](../inputs/IMG_8495/IMG_8495.jpeg) | 29.0 / 70.7 / 72.3 / 77.8 | 8.2 / 72.5 / 77.4 / 70.8 | 59.1 / 74.5 / 77.5 / 90.2 | 16.1 / 58.4 / 49.0 / 65.1 |
| [IMG_8497](../inputs/IMG_8497/IMG_8497.jpeg) | 15.8 / 16.5 / 53.4 / 27.8 | 6.0 / 12.1 / 63.1 / 11.4 | 4.4 / 4.6 / 58.5 / 15.1 | 2.2 / 17.5 / 12.8 / 15.8 |
| [IMG_8500](../inputs/IMG_8500/IMG_8500.jpeg) | 19.4 / 41.8 / 67.8 / 52.1 | 11.3 / 37.3 / 72.0 / 45.8 | 10.6 / 38.6 / 71.3 / 50.8 | 6.1 / 34.8 / 46.8 / 30.9 |
| [IMG_8502](../inputs/IMG_8502/IMG_8502.jpeg) | 28.1 / 61.0 / 78.5 / 70.1 | 1.7 / 58.6 / 80.2 / 59.2 | 36.0 / 57.0 / 78.9 / 73.3 | 7.9 / 49.0 / 64.6 / 53.1 |
| [IMG_8505](../inputs/IMG_8505/IMG_8505.jpeg) | 18.1 / 13.3 / 44.1 / 26.0 | 9.1 / 13.5 / 53.9 / 24.0 | 0.7 / 10.7 / 50.4 / 17.9 | 2.4 / 21.9 / 25.9 / 20.0 |
| [IMG_8507](../inputs/IMG_8507/IMG_8507.jpeg) | 22.5 / 57.2 / 72.8 / 64.4 | 5.6 / 56.3 / 73.4 / 60.0 | 32.6 / 61.5 / 75.8 / 74.6 | 8.6 / 40.4 / 46.3 / 45.6 |
| [IMG_8509](../inputs/IMG_8509/IMG_8509.jpeg) | 24.5 / 75.9 / 84.1 / 79.8 | 5.9 / 64.0 / 74.6 / 63.2 | 58.3 / 70.9 / 77.9 / 88.4 | 6.6 / 48.4 / 49.6 / 51.9 |
| [IMG_8512](../inputs/IMG_8512/IMG_8512.jpeg) | 38.6 / 73.6 / 84.9 / 82.3 | 5.7 / 54.7 / 80.3 / 54.2 | 25.0 / 55.9 / 80.1 / 68.3 | 82.6 / 64.2 / 48.5 / 34.7 |
| [IMG_8518](../inputs/IMG_8518/IMG_8518.jpeg) | 18.9 / 6.2 / 7.0 / 14.8 | 2.7 / 2.2 / 34.2 / 6.3 | 9.1 / 6.2 / 37.1 / 1.4 | 23.3 / 20.0 / 16.1 / 1.3 |
| [IMG_8519](../inputs/IMG_8519/IMG_8519.jpeg) | 43.5 / 39.7 / 34.9 / 65.8 | 22.6 / 32.9 / 38.7 / 48.3 | 43.4 / 37.8 / 40.8 / 65.2 | 16.0 / 22.4 / 11.5 / 10.0 |
| [IMG_8563](../inputs/IMG_8563/IMG_8563.jpeg) | 10.5 / 0.4 / 74.6 / 10.4 | 31.3 / 5.2 / 77.9 / 38.5 | 16.0 / 4.3 / 77.2 / 21.1 | 2.0 / 2.5 / 0.4 / 4.5 |
| [IMG_8569](../inputs/IMG_8569/IMG_8569.jpeg) | 11.3 / 81.7 / 83.5 / 82.9 | 12.1 / 79.0 / 79.5 / 82.1 | 34.9 / 83.9 / 84.8 / 77.9 | 773.9 / 82.4 / 2.0 / 53.6 |
| [IMG_8579](../inputs/IMG_8579/IMG_8579.jpeg) | 2.7 / 6.3 / 1.4 / 3.7 | 12.6 / 0.7 / 5.1 / 11.8 | 1.3 / 1.9 / 5.7 / 1.7 | 10.5 / 11.2 / 3.6 / 1.9 |
| [IMG_8581](../inputs/IMG_8581/IMG_8581.jpeg) | 22.0 / 20.5 / 5.9 / 1.5 | 21.1 / 2.4 / 22.5 / 20.8 | 5.6 / 14.9 / 12.7 / 6.2 | 3.5 / 4.2 / 34.7 / 0.9 |
| [IMG_8603](../inputs/IMG_8603/IMG_8603.jpeg) | 12.3 / 5.3 / 7.2 / 8.2 | 15.5 / 18.1 / 24.0 / 29.7 | 4.3 / 6.8 / 13.5 / 12.6 | 4.5 / 6.8 / 21.9 / 2.6 |
| [IMG_8605](../inputs/IMG_8605/IMG_8605.jpeg) | 13.1 / 14.9 / 6.9 / 2.0 | 15.8 / 9.3 / 22.0 / 22.9 | 10.5 / 8.8 / 7.1 / 3.4 | 2.6 / 1.5 / 4.8 / 1.0 |

## Verification

All 26 observations use identical image/scale inputs across methods. Source hashes and model states remained unchanged. The maximum absolute difference from historical predictions or interval endpoints was 0 in the respective physical unit. Checks cover all 104 transformer quantities and all 80 quantities in the previous five-image four-method comparison. The previous five-image study remains available as an archive. The current common evaluation covers all 26 images.
