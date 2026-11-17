# Expanded real-image evaluation and rotation sensitivity

This study records the real-image evaluations and input-rotation tests of the retained measurement methods. The models were trained on [MetroDef3D Simple Concrete Crack Dataset v1.0](https://doi.org/10.5281/zenodo.21340378). They demonstrate synthetic-reference training and benchmarking; they were not trained for these real surfaces.

## Observations and scope

The [per-image results](RESULTS.md) cover **26 images**: six field observations and 20 photographs of split paving stones with varied openings. Several tile photographs share a physical fracture. This is a selected, iteratively acquired set, not 26 independent cracks or a representative field population. Unfinished width-only annotation IMG_8571 is excluded. Different orientations are repeated observations, not additional physical samples.

The [common four-method comparison](all_methods/README.md) evaluates the transformer, ResNet-50, ConvNeXt-Tiny and conventional pipeline on all 26 images. The original transformer-only table remains as a historical overview. The earlier [five-image comparison](../real_model_comparison/README.md) is preserved as an archive. No additional training, field calibration of prediction intervals, or model tuning was performed for this consolidation.

All completed results are retained. The observations include close agreement and substantial discrepancies; no new good/bad acceptance threshold is imposed. Interpretation of visible boundaries and acquisition choices were not uniformly blind to earlier model outputs. The images do not establish a population transfer rate or a statistically stable model ranking.

## Images, annotations and scale

`inputs/<image>/` contains the surface and paired target photographs, the adopted frozen annotation, calculated reference quantities, target-fit records and the actual scale array used at inference. The paper targets were compared with a glass calibration target through scanner measurements. The camera was held fixed between the paired target and surface photographs. Several photographs can share a target exposure.

These historical predictions retain their original scale maps and single adopted annotations. The later Metrosert calibration is propagated in the separate [uncertainty example](../uncertainty_example/README.md), not silently substituted into all 26 results. In particular, IMG_8579 here uses its original annotation; the uncertainty example uses a five-annotation mean and the updated scale. They answer different questions and should not be mixed. Additional repeat annotations of IMG_8184 and IMG_8162 are not included in this frozen overview.

Scale and annotation uncertainty are not included in the synthetic-calibrated model bounds. Calibration establishes a dimensional reference for image scale, but does not eliminate mapping, pose, surface-plane or boundary interpretation errors. Detailed chain documentation is retained in the [original real-image study](../real_image_transfer/README.md) and [uncertainty example](../uncertainty_example/README.md).

`predictions_and_references.json` contains raw and calibrated bounds, predictions, adopted references and the four individual relative differences. `interval_factors.json` contains the frozen transformer factors from corrected, valid synthetic validation references. References for width and length are in millimetres; area is in square millimetres. Public model configurations and inference are documented in [the inference workflow](../../inference/README.md).

## Rotation experiment

The separate `rotation/` records contain **168 outputs**: three retained models × four orientations × 14 source images. The real panel is IMG_8184, IMG_8162, IMG_8169 and IMG_8139. Ten positive-reference synthetic test observations were sampled without replacement with random seed 20261117: 1804, 2517, 2736, 6861, 7080, 7217, 7949, 8036, 8421 and 9701.

Inference used CPU float32. Clockwise angles were 0°, 90°, 180° and −90°. Quarter-turns were exact array rotations applied jointly to RGB and physical-scale inputs. Directional scale axes were exchanged for odd quarter-turns when applicable. Scalar construction/annotation references stayed fixed. Input checks and comparison with retained baseline outputs are included. Models and weights were unchanged.

For each image and measurand, rotation range is `(largest prediction − smallest prediction) / reference × 100`. For transformer length, mean ranges were 6.98% on the four real images and 4.45% on the ten synthetic images. Maxima were 16.16% (IMG_8139) and 12.32% (seed 8036). Both domains exhibited orientation sensitivity. These small panels do not establish a general domain difference. Other architectures did not all show greater sensitivity on the real panel.

The result motivates evaluating rotation and reflection augmentation, omitted from the retained training. It does not establish that augmentation will solve transfer errors. Reflection was not tested in this experiment.

## Recompute the summary

Run `python3 summarize.py` in this folder. It verifies the 104 original-orientation quantity comparisons and recomputes all 24 model/domain/quantity rotation-range summaries from saved outputs. This verifies the reporting arithmetic, not a new inference run. `checksums.json` records the frozen files. Complete prediction vectors, raw bounds, calibrated bounds and fixed references remain available for alternative summaries.

Run `python3 all_methods/summarize.py` to verify and regenerate the common comparison of 416 quantities, including exact parity with the saved transformer results and the earlier five-image comparison.

The analytical reference checks and export-correction history are documented in [reference validation](../reference_validation/README.md) and [reference correction](../reference_correction/README.md).
