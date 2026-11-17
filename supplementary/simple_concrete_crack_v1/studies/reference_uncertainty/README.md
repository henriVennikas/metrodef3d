# Evaluated uncertainty of individual real-image references

This study evaluates scale and annotation uncertainty for the retained single-annotation references of IMG_8184 and IMG_8162. The original reference values, photographs, annotations, image mappings and model predictions are preserved. No training or model inference is performed.

The reported terms are **standard uncertainties of the evaluated components**, in the same physical units as the reference values. They are not 95% intervals, model prediction bounds, or a complete uncertainty budget. Uncertainty for IMG_8169 and IMG_8139 is **not evaluated** because no image-specific repeat-annotation estimate is available for those observations. Missing components are not assigned zero.

## Results

The original estimates with evaluated standard uncertainties are:

| Image | Length (mm) | Mean width (mm) | Maximum width (mm) | Area (mm²) |
|---|---:|---:|---:|---:|
| IMG_8184 | 88.84 ± 0.43 | 0.934 ± 0.031 | 1.160 ± 0.033 | 82.99 ± 3.06 |
| IMG_8162 | 81.13 ± 0.18 | 1.081 ± 0.139 | 1.460 ± 0.178 | 87.74 ± 11.07 |

Individual component contributions and the full-precision retained references are in [components.csv](components.csv). Joint scale contributions are:

| Image | Length (mm) | Mean width (mm) | Maximum width (mm) | Area (mm²) |
|---|---:|---:|---:|---:|
| IMG_8184 | 0.014286 | 0.000065 | 0.000739 | 0.017723 |
| IMG_8162 | 0.012980 | 0.000076 | 0.000809 | 0.018738 |

Annotation variability dominates all eight evaluated budgets. The additional scale contribution changes none of the annotation-only uncertainties at the displayed precision. All values remain estimates of the specified components.

## Reference estimate and annotation contribution

The estimate remains the original annotation evaluated using its original physical image mapping. Four later annotations and that original provide five observations of each quantity. All five are evaluated with the same mapping and geometric definitions within each image.

The sample covariance across the five observations estimates the variability of an **individual annotation**. It is not divided by five. The reference is not replaced by the repeated-annotation mean, and the uncertainty of that mean is not substituted for individual-annotation variability. The four-new-only sensitivity remains available in the [repeat-annotation study](../annotation_repeatability/README.md).

The operator reported varying the starting location and direction of each boundary trace to avoid following the same path. The observed ordering of widths is not used as proof of either dependence or independence. Original and new annotations span different sessions and prior exposure to predictions. The sample covariance is therefore an empirical within-operator estimate under these recorded conditions. It cannot quantify a common boundary bias or absolute annotation accuracy.

## Scale chain and propagation

The shared calibration information comes from the [glass-target uncertainty study](../uncertainty_example/README.md): the JD Photo Data SL12-4 target, independently calibrated by the national calibration laboratory (Metrosert), scanner measurements, and printed target 01. Report BTLL-26/084 gives expanded uncertainty 0.005 mm with coverage factor 2 for the measured spans, corresponding to standard uncertainty 0.0025 mm.

The calculation reconstructs the scanner-axis scales from the four calibrated spans and fourteen scanner records. The certificate supplies no covariance between spans. The existing common additive span-error scenario is retained. The certificate contribution is not averaged down with the number of scans. The observed scanner X/Y covariance represents transfer variability and is also retained without division by fourteen. These are explicit propagation assumptions, not a complete scanner-characterization model.

Each image has its own original homography. Physical scanner-X and scanner-Y scale perturbations act on that mapping, so the same shared scale covariance produces different quantity uncertainties for different crack paths and boundaries. Annotation coordinates stay fixed during these perturbations.

Length, mean width and area admit independent analytic sensitivity checks. Maximum width uses the existing normal-chord procedure with 0.05 mm station spacing and a 1 mm tangent window. Which chord supplies the maximum can change with scale. A nonlinear propagation is therefore used rather than selecting an unstable finite-difference derivative. The implementation checks its accelerated geometric calculation against all ten original and repeated annotations.

Scale propagation uses one common Gaussian certificate error and a correlated bivariate Gaussian scanner-transfer error, with independence between these groups. Each of the certificate-only, scanner-only and joint modes uses 4096 scrambled Sobol samples. The joint nonlinear output covariance is used in the combined budget. For maximum width, separate component variances need not sum exactly to the joint nonlinear variance.

Prefixes of 1024, 2048 and 4096 samples give identical combined uncertainties at the displayed precision. The largest 2048-to-4096 change in a scale standard uncertainty is 0.335%. Smooth-quantity results agree with analytic propagation within 0.068%. These are numerical convergence checks, not independent repeated experiments or confidence intervals for integration error. Seeds, modes and full covariance matrices are recorded in `results.json`.

The nonlinear propagation also gives small mean shifts of maximum width: -0.000203 mm for IMG_8184 and +0.000132 mm for IMG_8162, both below 0.61% of the corresponding evaluated standard uncertainty. These shifts are documented and do not recenter the retained estimates.

For the retained estimate q0, the evaluated covariance is

    C_evaluated = C_annotation + C_scale,
    u_evaluated,j = sqrt(C_evaluated,jj).

Annotation and calibration/transfer groups are treated as independent. Covariances between quantities and between physical scale axes are retained. The shared scale would also correlate model and reference results, but this study evaluates reference uncertainty only. It does not propagate uncertainty of the model-minus-reference difference or add model prediction bounds to this budget.

## Retaining the original nominal scale

The Metrosert dimensions imply a small change from the original nominal scanner scales. The corresponding change in each reference is calculated and recorded separately as an **unapplied nominal-scale correction**. It is not reclassified as a random uncertainty component or hidden in the combined standard uncertainty.

The original reference estimates are retained to preserve the existing comparisons. The largest calculated correction is approximately 2.3% of the corresponding annotation standard deviation. This is a documented negligible-correction approximation relative to the evaluated uncertainty, not a claim that all last printed digits would be unchanged if the correction were applied. The four-new-only estimates, model predictions and central-reference comparisons are not substituted or adjusted to improve agreement.

## Scope and remaining components

The evaluated contributions are the glass calibration, observed scanner-transfer variability and repeated annotation variability. The retained mappings assume the same camera settings and the same plane for the target and crack observation. This study does not establish uncertainties for target-to-surface pose or plane differences, local mapping inadequacy, unmeasured individual glass-dot errors, paper dimensional changes, scanner long-term drift or common annotation bias. Target-fit coordinate residuals are not directly assigned as crack-width uncertainty.

All conclusions concern the two specified images and the documented reference procedure. The variability is not transferred to other cracks.

## Reproduction and records

Run `python evaluate.py` from this directory in the complete supplementary-study tree. Install the packages listed in `requirements.txt` in an analysis environment. The script reads the frozen inputs from the sibling `annotation_repeatability` and `uncertainty_example` studies and writes derived files only in this directory.

- `results.json`: adopted references, annotation and scale covariance, uncertainty components, numerical checks and the separate nominal-scale correction.
- `components.csv`: physical-unit component contributions for every image and quantity.
- `verification.json`: geometric reproduction, covariance, propagation and convergence checks.
- `input_checksums.json`: hashes of the exact source inputs.
- `evaluate.py`: complete calculation and verification workflow.

No raw image, annotation, reference or trained model is modified. The study is prepared locally for review.
