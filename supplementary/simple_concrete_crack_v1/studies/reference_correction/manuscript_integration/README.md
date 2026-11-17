# Reference-mask and real-image interval recalculation

7 November 2026. Local review material. No model execution, training or publication.

The updated synthetic comparison uses `corrected_recalibrated_valid_cohort` from the parent study. It retains all 1494 test observations and the original model predictions, normalization and selected checkpoints. Learned interval calibration uses the 1493 eligible validation cases. The parent report provides controls for the reference correction and exclusion of invalid validation seed 551. Original studies remain historical records.

The reference-mask diagnostic is also reevaluated using the same saved geometric estimates and corrected scalar references. Length, mean-width, maximum-width and area MARE are respectively **0.37%, 0.38%, 5.42% and 0.11%**. This changes 26 reference rows. It does not regenerate the raster masks or rerun their geometric estimator. Full-precision metrics and paired estimates accompany this note.

The existing four real-image predictions use the updated transformer factors calculated solely from corrected synthetic validation data. Central predictions, raw bounds, annotations and scale maps remain unchanged. No image reference changes its inside/outside-interval classification. `real_image_corrected_calibration.csv` supplies the recalibrated real-image bounds. Original published bounds reproduce to within 0.000002 in their respective physical units using the archived raw values and old factors. This tolerance accommodates saved numerical precision.

Reproduce these supporting calculations from this folder with:

```sh
python recalculate_support.py --classical-study ../../classical_benchmark --real-study ../../real_image_transfer
```

The analytical fixture discrepancies in the parent validation study are observed numerical errors under the tested conditions. They are not uncertainty bounds or a claim of six-decimal accuracy. The topology fix does not remove the ordinary-fixture numerical discrepancies. The original dataset remains intact and the correction requires explicit adoption through the parent overlay.
