# Numerical uncertainty example for IMG_8579

## Result and scope

The mean of five annotation-derived mean widths is **1.176132 mm** after updating the physical scale from Metrosert measurements. The evaluated standard uncertainty is **0.038403 mm** for that mean. This is a component budget for the image-derived reference, conditional on the stated transfer and repeat assumptions. It is not the total uncertainty of a physical crack measurement or of the learned model.

The original annotation and four new passes give an observed sample standard deviation of **0.085871 mm** in mean width. For a single annotation this spread is the estimated annotation-variability component. If the reported reference is the mean of five independent repeats, that component is **0.038403 mm = s/√5**. The five-pass set includes two annotation sessions and prior exposure to predictions. Correlation or a common boundary bias can therefore remain. The reference uncertainty is not reduced by counting multiple uses of the same scale calibration as independent measurements.

IMG_8579 was selected because its original annotation gave close transformer agreement. It is one controlled opening between split paving-stone parts, not a representative sample of field cracks. The five original-coordinate annotations use the same visible-opening convention. The new traces were drawn from blank canvases without earlier overlays. They are not claimed to be fully blinded because the operator had previously viewed predictions. All five traces are retained, including the differences from the original. The unused fifth fresh-annotation slot is excluded.

## Measurement chain

1. **Glass target.** Metrosert report BTLL-26/084, dated 16 November 2026, identifies JD target serial 194821. The measured outer centre-to-centre spans A1–A4 are 98.010, 98.010, 98.003 and 98.001 mm. Each listed result has expanded uncertainty 5 µm with k=2, giving standard uncertainty 2.5 µm. The report states SI traceability and reports means of three measurements. These reported uncertainties apply to the listed quantities, not all 2500 dot coordinates. The diagonal and dot diameters are not used to set the two scanner scales.
2. **Scanner.** Fourteen earlier 2540-dpi glass scans contain repeated stationary scans, repositioning and four orientations. The measured opposing edge spans determine the target-axis scales. The orientations map these back to the fixed scanner axes. Replacing the manufacturer's dimensions with Metrosert's dimensions gives mean scanner scales **0.0100678510 and 0.0100128278 mm/px**. The changes relative to the previous rounded scale values are **+0.009099% and +0.004523%**. This retrospective transfer assumes that the glass dimensions and scanner characteristics remained applicable between the earlier scans and the later calibration. Long-term drift was not separately measured.
3. **Paper target 01.** Its detected dot coordinates in the original scanner image are multiplied by the updated scanner-axis scales. Actual measured paper coordinates are retained. Nominal print dimensions do not determine scale, and printer dimensional deviations are not added again as uncertainty after measuring the printed target.
4. **Photograph.** A planar homography maps 1194 detected points in IMG_8578 to the measured paper coordinates. The paired IMG_8579 surface image uses the same mapping under the fixed-camera, common-plane assumption. Its physical directional pixel scales are evaluated at the 1024-square model resolution. RGB is resized as before, with no crop or contrast adjustment.
5. **Annotations.** Length is the transformed centreline polyline length. Area is the physical boundary polygon area. Mean width is area/length. Maximum width is the largest normal boundary chord at 0.05 mm station spacing and a 1 mm tangent window. Every annotation is recalculated using the same mapping and definitions.

The numerical scale change is a correction, not an uncertainty term. Earlier image references and predictions are preserved. The separate new records show the corrected values and the unchanged model's response to the new scale.

## Five annotations with the updated scale

| Annotation | Length (mm) | Mean width (mm) | Maximum width (mm) | Area (mm²) |
|---|---:|---:|---:|---:|
| Original | 72.935384 | 1.049586 | 1.298942 | 76.551985 |
| Repeat 1 | 73.002321 | 1.148303 | 1.838895 | 83.828813 |
| Repeat 2 | 72.544947 | 1.237258 | 1.544660 | 89.756842 |
| Repeat 3 | 72.867548 | 1.270834 | 1.716629 | 92.602549 |
| Repeat 4 | 73.039237 | 1.174680 | 1.497566 | 85.797725 |

The mean reference and standard uncertainties for all four quantities are in the machine-readable results. The original trace remains separate from the four new passes.

## Evaluated mean-width components

| Component | Standard contribution to the five-annotation mean width (mm) | Treatment |
|---|---:|---|
| Metrosert glass spans | 0.0000300 | 2.5 µm standard uncertainty on each measured span, common additive error scenario |
| Scanner-to-paper transfer | 0.0000741 | Observed joint scanner-axis covariance across 14 scans |
| Annotation mean | 0.0384026 | Sample SD / √5, conditional on independent repeats |
| Combined evaluated components | **0.0384027** | Covariance-aware propagation and independence between the annotation and scale groups |

The certificate does not provide correlations between measured spans. The main calculation assumes a fully positively correlated additive error across A1–A4. This avoids reducing a shared certificate contribution by averaging spans or scans. It is an explicit correlation scenario, not a universal worst case for prediction-minus-reference differences. The 14-scan transfer covariance retains the X/Y relationship and is not divided by 14: it describes observed transfer variability for a subsequent scan, rather than only precision of a mean scanner calibration. It does not establish scanner long-term stability or all local distortion.

Let r be the annotation reference and e = (e_x,e_y) the relative physical-axis scale perturbations. For the mean reference, the evaluated covariance is

    C_r = C_annotation / 5 + J_r (C_glass + C_scan) J_rᵀ.

The full four-quantity annotation covariance is retained. In particular, mean width and area are strongly related because mean width is calculated as area/length. They are not propagated as unrelated annotation inputs. Values, matrices and numerical sensitivities are in `results/reference_budget.json`.

No 95% expanded interval is asserted for this small annotation sample. Multiplying this standard uncertainty by two would not, by itself, establish 95% coverage with five potentially dependent annotations.

## Mapping sensitivity and remaining components

The photo fit has approximately **0.114 mm RMS residual**, with approximately **0.117 mm held-out RMS residual**. These are coordinate discrepancies, not calibrated uncertainty of crack width. They include possible mapping inadequacy, optical distortion, printed-dot localization and transferred-coordinate errors. Assigning the coordinate RMS directly to mean width would mix different quantities and ignore spatial dependence.

Deleting each of 25 spatial blocks of target correspondences and refitting changes the five-annotation mean width by at most **0.000876 mm**. Corresponding maxima are 0.04187 mm for length and 0.07706 mm² for area. These are deterministic fit-sensitivity checks, not a standard uncertainty or a bound on all mapping errors. They are therefore reported separately from the component sum.

Other unquantified contributions are common annotation boundary bias, local glass-dot position errors beyond the measured spans, scanner local distortion and long-term drift, paper dimensional changes, lens/mapping model inadequacy and any target-to-surface plane or pose mismatch. Annotation variability is conditioned on this one photograph and does not estimate reacquisition variability. No values are invented for these terms. The example addresses the influence of documented components without claiming a complete measurement-chain budget.

The original and new passes give different boundary choices. The four-new-only analysis is retained alongside the five-pass result. Their original-scale relative sample SDs were approximately 0.31%, 4.65%, 9.55% and 4.47% for length, mean width, maximum width and area. This difference is a reason to retain the single-image and session qualifications, not to discard the original annotation.

## Shared scale in model and reference

With the updated scale, the retained transformer predicts mean width **1.115677 mm**. Its corrected-synthetic-validation bounds are **[1.068228, 1.171743] mm**. The difference from the five-annotation mean is **−0.060456 mm**. Both model and reference use the same image-scale information, so treating their scale uncertainties as independent would be incorrect.

The model is evaluated at nominal scale and at ±0.5% and ±1% perturbations of each physical scanner axis. These step sizes estimate a local derivative. They are sensitivity probes, not claimed uncertainty magnitudes. The RGB channels, model weights, buffers, normalization and interval factors are fixed. Model derivatives from the two step sizes agree within 0.98% across all quantities and within 0.008% for mean width. No training or field fitting occurs.

For difference d = prediction − reference, the shared-scale term is

    C_d,scale = (J_model − J_reference) C_scale (J_model − J_reference)ᵀ.

For mean width, the scale-only standard components are 0.0000799 mm for the reference, 0.0000889 mm for the model output, and **0.0000617 mm for their difference**. Including the annotation-mean component gives **0.038403 mm** for the evaluated contributions to that difference. This does not include the model's unknown real-domain error. The empirical asymmetric model bounds are not converted to standard uncertainty or added in quadrature.

The mean reference lies 0.00439 mm above the synthetic upper prediction bound, while the evaluated reference uncertainty is larger than that separation. This demonstrates that an interval-inclusion decision based solely on a point annotation omits reference variability. It does not establish coverage or prove model-reference agreement.

## Reproduction and verification

`propagate_reference.py` verifies the frozen input hashes and each scanner span against saved dot coordinates. It updates the glass-to-scanner-to-paper-to-photo chain, recalculates all five annotations, saves component covariances, and performs spatial block deletion. It reproduces the previous annotation values before the scale update. Rectangle, tapered-strip and rotated-geometry checks validate the extraction functions, and a uniform-scale check verifies linear scaling for length and width and quadratic scaling for area.

One anisotropic derivative probe moves a final sampling station within approximately 0.0012 mm of a centreline endpoint that extends slightly outside its polygon. Such endpoint stations are recorded by the geometry routine and excluded from valid width chords. The check rejects any outside station more than 0.05 mm from an endpoint. No annotation coordinates are altered. This has no effect on the primary area/length mean-width calculation.

`run_model_sensitivity.py` verifies weights and unchanged model state and RGB across all ten evaluations. `summarize.py` combines shared-scale sensitivities, creates the figures and saves verification. The previous and updated model results remain distinct. No rotations, additional training or replacement of historical comparison results were performed.

Source input hashes, public checkpoint hashes and package versions accompany the results. Large raw scanner TIFFs remain in the local test-plates archive; the measured scan coordinates, spans and paired photographs needed to reproduce this transfer are included here.

The statistical treatment follows [JCGM 100:2008, §4.2](https://www.iso.org/sites/JCGM/GUM/JCGM100/C045315e-html/C045315e_FILES/MAIN_C045315e/04_e.html) and [§5](https://www.iso.org/sites/JCGM/GUM/JCGM100/C045315e-html/C045315e_FILES/MAIN_C045315e/05_e.html), with the conditional independence and correlation assumptions explicitly separated from measured quantities.
