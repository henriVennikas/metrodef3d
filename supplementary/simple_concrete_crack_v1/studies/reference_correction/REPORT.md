# Reference correction and benchmark impact

7 November 2026. **Local correction overlay. The original dataset, predictions, weights and published results are preserved.**

## Corrected export and reference version

Generator 0.1.1 uses visible-defect schema 2 and `reference_export_revision=component-aware-2`. The Blender exporter records half-open component ranges and calculates length within each component, without connecting across invisible segments. Mean width remains visible polygon area divided by the summed visible length. Station-profile extrema retain their construction definition.

If an opening polygon is visible but no centreline station is visible, area is retained and missing width/depth extrema are `null`. Mean width is `null` when visible length is zero. Explicit validity flags distinguish these cases from a genuinely empty observation with defined zero quantities. The preview fallback and overlay viewer also respect disconnected components. Projection, clipping thresholds, coordinate rounding and polygon-area arithmetic remain unchanged, so the small numerical conditioning discrepancies from the earlier verification have not been represented as fixed.

The 72 independent analytical/stress fixtures now execute without exceptions. All 65 ordinary fixture measurands are unchanged. The exit/re-entry fixture has two components and exported length 115.175100 mm (analytical value 115.175111 mm) instead of 138.032242 mm. Three previous empty-profile exceptions produce explicit undefined quantities. The existing generator tests and new component regression tests pass. The earlier failing verification is preserved separately.

## Dataset correction

A broader scan of all 10,000 original sidecars selected 142 candidates using original source-segment gaps and consecutive boundary intersections, with no fractional-gap threshold. The production-camera replay confirms disconnected visible components in all 142: **92 training, 24 validation and 26 test observations**. Seed 6861, previously unconfirmed by the ideal-camera audit, is now resolved using the actual Blender camera. Its length changes from 114.251014 to 92.664450 mm. Multi-component cases also expose short gaps missed by the earlier conservative subtraction audit.

Corrected sidecars are written only under `overlay/visible_defect/`, with original hashes, source-metadata hashes, old quantities and same-runtime original-export quantities. The overlay manifest identifies every replacement. Unlisted observations continue to use their unchanged original sidecars. The original metadata files still contain original references; consumers must explicitly select the overlay rather than mix old embedded values with corrected sidecars.

Replaying the old exporter in the current Blender runtime shows small differences from archived exports. Maximum absolute replay differences over 150 candidate/control observations are 0.000657 mm length, 0.000502 mm mean width, 0.000003 mm maximum width and 0.006004 mm² area. `reference_changes.csv` separates this replay difference from the topology-only change measured with both exporters in the same runtime. The full corrected sidecars retain regenerated values rather than silently combining parts from different executions. No images or pixel-scale maps were regenerated.

## Point predictions: before and after

All central predictions are identical to the saved benchmark outputs. Test identities remain the same 1494 observations. MARE uses the same 1493 positive references. Entries below show **original → corrected reference** results.

| Method | Length MARE (%) | Mean-width MARE (%) | Maximum-width MARE (%) | Area MARE (%) |
|---|---:|---:|---:|---:|
| Transformer | 2.04 → 1.94 | 2.05 → 1.88 | 2.54 → 2.54 | 2.44 → 2.44 |
| ResNet-50 | 4.60 → 4.44 | 4.13 → 3.94 | 5.04 → 5.04 | 6.34 → 6.34 |
| ConvNeXt-Tiny | 6.37 → 6.27 | 4.00 → 3.73 | 4.88 → 4.88 | 7.34 → 7.34 |
| Conventional | 8.60 → 8.50 | 18.06 → 18.22 | 27.05 → 27.05 | 20.24 → 20.24 |

Length and mean-width MARE decrease for all three learned systems. Conventional length MARE also decreases, while its mean-width MARE increases slightly. Maximum-width and area MARE are unchanged at two decimals. The transformer retains the lowest MARE for every quantity. This remains a comparison of the retained runs, not a statistically established architecture ranking.

## Interval performance

Three distinct comparisons are preserved:

1. Original references and original calibration: reproduces the saved benchmark metrics and calibration factors.
2. Corrected references with the same calibrated bounds: isolates the reference change at fixed prediction intervals.
3. Corrected references with validation-only recalibration: keeps raw network outputs and conventional estimates fixed, but refits interval expansion factors or residual radii from corrected validation references.

Learned-model recalibration excludes the previously documented invalid validation seed 551, leaving 1493 observations. The complete table also contains same-cohort recalibration including that seed solely to isolate label correction, and an old-reference valid-cohort control. It therefore does not attribute the cohort adjustment to the topology fix. No test observations are excluded. The conventional pipeline retains its original disjoint 1237-case residual-calibration subset, which already excluded 551, and its original selected settings.

| Method | Quantity | Original coverage (%) | Corrected, fixed bounds (%) | Corrected, recalibrated (%) | Original / new mean width | Original / new normalized score (%) |
|---|---|---:|---:|---:|---:|---:|
| Transformer | Length | 95.18 | 95.78 | 94.31 | 10.4786 / 8.9857 | 25.51 / 23.19 |
| Transformer | Mean width | 93.37 | 93.98 | 93.51 | 0.0823 / 0.0779 | 27.43 / 22.78 |
| Transformer | Maximum width | 94.44 | 94.44 | 94.44 | 0.1233 / 0.1234 | 28.58 / 28.58 |
| Transformer | Area | 94.71 | 94.71 | 94.71 | 10.3471 / 10.3475 | 26.34 / 26.34 |
| ResNet-50 | Length | 95.31 | 96.25 | 95.72 | 24.0812 / 23.0787 | 67.11 / 66.13 |
| ResNet-50 | Mean width | 93.78 | 94.65 | 94.44 | 0.1655 / 0.1605 | 84.91 / 82.32 |
| ResNet-50 | Maximum width | 95.31 | 95.31 | 95.31 | 0.2414 / 0.2414 | 81.99 / 81.99 |
| ResNet-50 | Area | 94.91 | 94.91 | 94.91 | 27.1093 / 27.1118 | 51.45 / 51.45 |
| ConvNeXt-Tiny | Length | 95.78 | 96.25 | 95.85 | 32.6958 / 31.2914 | 54.13 / 52.62 |
| ConvNeXt-Tiny | Mean width | 93.44 | 94.38 | 93.78 | 0.1737 / 0.1650 | 39.92 / 35.94 |
| ConvNeXt-Tiny | Maximum width | 95.05 | 95.05 | 95.05 | 0.2419 / 0.2419 | 39.02 / 39.02 |
| ConvNeXt-Tiny | Area | 95.98 | 95.98 | 95.98 | 30.6461 / 30.6495 | 59.66 / 59.67 |
| Conventional | Length | 94.51 | 94.51 | 94.51 | 105.4330 / 105.4330 | 208.18 / 209.53 |
| Conventional | Mean width | 95.85 | 95.78 | 95.72 | 0.5921 / 0.5919 | 108.10 / 108.41 |
| Conventional | Maximum width | 96.18 | 96.18 | 96.18 | 2.5375 / 2.5375 | 506.32 / 506.32 |
| Conventional | Area | 94.24 | 94.24 | 94.24 | 81.0933 / 81.0933 | 216.89 / 216.89 |

For the transformer, unchanged bounds increase length coverage from 95.18% to 95.78%. Recalibration reduces its mean length-interval width from 10.48 to 8.99 mm, with test coverage 94.31%. Thus improved reference agreement need not increase coverage after bounds are narrowed. Mean-width coverage is 93.51% after recalibration. These remain empirical synthetic-population results, not guaranteed per-observation or field coverage.

## Interpretation and limits

The reference correction does not overturn the main comparison. Some measurement predictions agree better with the corrected geometry than with the original erroneous labels. That observation does not establish what retraining would achieve.

The learned weights, training normalization, selected checkpoints and auxiliary supervision were obtained with the original labels. The conventional settings were selected using the original tuning references. This study reevaluates those fixed systems and separately recalibrates their bounds; it is not a retrained benchmark. Ninety-two corrected training observations and 24 corrected validation observations may affect future training or selection. Training-derived interval-score floors remain frozen to isolate the comparison. Newly calibrated intervals must not be described as part of the original frozen model release without a new calibration identifier.

New references use their six-decimal physical values. Unchanged learned-model references retain the original CSV float32 representation. The original metrics reproduce exactly before correction; the earlier audit bounds the original float32 conversion differences. All per-observation predictions, references, bounds and full-precision aggregate metrics are saved.

The updated comparison uses the corrected references and valid-cohort validation recalibration. Historical studies and the original dataset remain unchanged. The [supporting recalculations](manuscript_integration/README.md) supply corrected-reference mask diagnostics and updated real-image bounds. Training and checkpoint selection remain based on original references.

## Artifacts

- `overlay/manifest.json`, `overlay/visible_defect/`: additive versioned reference overlay and provenance.
- `load_overlay.py`: explicit read-only selection of corrected or original references.
- `reference_changes.csv`, `regeneration.json`: every old/new quantity, component count and same-runtime comparison.
- `benchmark_comparison.csv`: point and interval metrics under all comparison modes.
- `calibration_comparison.json`: original, corrected and cohort-control factors/radii.
- `predictions/`: corrected-reference test tables with fixed or recalibrated bounds.
- `fixture_results/`, `fixture_regression.log`: corrected export regression outputs.
- `candidate_screen.json`, `original_sidecar_hashes.json`, `original_metadata_hashes.json`: original input identities and hashes.
- `source_manifest.json`, `corrected_export.py`, `code/`: exact implementation used and staged source files.
- `protocol.json`, `benchmark_verification.json`, `verification.json`: frozen analysis decisions and verification.

No changes have been published and no model training was launched.
