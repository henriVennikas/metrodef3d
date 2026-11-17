# Dimensional Calibration of the Epson V600 Scanner

## JD Photo Data SL12-4 dot-grid study

**Study date:** 4 September 2026  
**Scanner:** Epson Perfection V600 Photo  
**Selected production resolution:** 2540 dpi  
**Analysis software:** OpenCV pipeline in `src/jdgrid/`  
**Target certificate:** `JD194821-001.pdf`

## 1. Purpose

This study characterized the dimensional accuracy and repeatability of the
scanner before imaging painted test plates. The principal questions were:

1. Does the requested scan resolution represent the same physical scale along
   both image axes?
2. Is the scale difference repeatable?
3. Does the error remain fixed to the scanner when the target is rotated?
4. How much variability is introduced by rescanning and by replacing the
   target on the scanner bed?
5. Is a global dimensional calibration justified?

## 2. Calibration target

The reference was a JD Photo Data SL12-4 low-reflective chrome-mask target:

- Plate size: 125 mm x 125 mm
- Plate thickness: 1.5 mm
- Array: 50 x 50 dots on a nominal 2 mm pitch
- Nominal dot diameter: 1 mm
- Three hollow central dots forming an orientation mark
- Imaging class: Class A

The certificate reports the following measured dimensions:

| Feature | Description | Measured dimension |
|---|---|---:|
| A1 | Top horizontal array span | 97.9994 mm |
| A2 | Bottom horizontal array span | 97.9994 mm |
| A3 | Left vertical array span | 97.9992 mm |
| A4 | Right vertical array span | 97.9993 mm |
| A5 | Array diagonal | 138.5915 mm |
| CD1 | Dot diameter | 1.0002 mm |

The certificate gives traceable measurements for the listed spans, diagonal,
and dot diameter. It does not provide an individually measured coordinate for
each of the 2,500 grid positions. Consequently, local residuals include both
scanner error and any unreported local target-placement error.

## 3. Image acquisition

The main study used 2540 dpi TIFF scans. At the requested resolution, the
nominal scale is:

\[
25.4 / 2540 = 0.010\ \text{mm/pixel} = 10\ \mu\text{m/pixel}
\]

The 2540 dpi dataset consisted of:

- Five consecutive scans without moving the R000 target
- Five R000 scans in which the target was removed and replaced (`rp`)
- One R090 scan
- One R180 scan
- Two R270 scans, with the second acquired to check an elevated residual in
  the first R270 scan

Additional single scans at 300, 600, 1200, 1270, and 2400 dpi were used to
compare scale and dot-localization performance across resolutions.

## 4. OpenCV analysis

The analysis pipeline:

1. Reads TIFF resolution metadata without modifying the source image.
2. Detects dark circular features using an expected physical dot diameter.
3. Rejects logos, text, dust, and other non-grid blobs using grid-neighbour
   consistency.
4. Organizes the detected dots into the 50 x 50 lattice.
5. Uses the three hollow central dots to infer R000, R090, R180, or R270
   orientation automatically.
6. Infers the centres of the hollow dots from the surrounding lattice but
   excludes them from residual statistics.
7. Uses the certified outer spans to calculate physical pixel scale.
8. Fits an affine pixel-to-millimetre transformation.
9. Exports `metrics.json`, `dots.csv`, and an annotated QA overlay for every
   scan.

All 2,497 solid dots were detected in every reported scan. The three hollow
orientation locations were correctly identified. The automatically inferred
orientation agreed with every filename.

## 5. Resolution comparison

Representative R000 results were:

| Requested resolution | Measured X scale | Measured Y scale | Affine residual RMS |
|---:|---:|---:|---:|
| 300 dpi | 85.2372 µm/px | 84.7150 µm/px | 14.04 µm |
| 600 dpi | 42.6193 µm/px | 42.3731 µm/px | 12.74 µm |
| 1200 dpi | 21.3092 µm/px | 21.1854 µm/px | 12.44 µm |
| 1270 dpi | 20.1344 µm/px | 20.0210 µm/px | 12.15 µm |
| 2400 dpi | 10.6540 µm/px | 10.5964 µm/px | 12.55 µm |
| 2540 dpi | 10.0669 µm/px | 10.0112 µm/px | 12.40 µm |

The dot-grid residual reached a plateau by approximately 600-1200 dpi. Higher
sampling did not materially improve localization of the large calibration
dots. Selection of 2540 dpi is nevertheless supported by separate empirical
inspection of the painted plates, where approximately 2400 dpi revealed detail
not visible at 1200 dpi. Moving from 2400 to 2540 dpi adds approximately 12%
more pixels while retaining a convenient nominal scale near 10 µm/px.

## 6. Calibrated 2540 dpi scale

Fourteen 2540 dpi scans were combined after mapping the rotated target axes
back to the fixed scanner axes.

| Quantity | Mean | Sample SD | Observed range |
|---|---:|---:|---:|
| Scanner X scale | 10.066935 µm/px | 0.000614 µm/px | 10.065764-10.067759 µm/px |
| Scanner Y scale | 10.012375 µm/px | 0.001553 µm/px | 10.009961-10.015139 µm/px |
| Affine residual RMS | 12.48 µm | 0.73 µm | 11.89-14.94 µm |

The corresponding effective resolutions are:

- Scanner X: 2523.11 dpi
- Scanner Y: 2536.86 dpi

Relative to an exact nominal 10 µm/px scale:

- Scanner X is approximately 0.669% larger in physical distance per pixel.
- Scanner Y is approximately 0.124% larger in physical distance per pixel.
- The mean X/Y scale ratio is 1.005449, corresponding to approximately 0.545%
  anisotropy between the axes.

Using a hardcoded 10 µm/px conversion, a measured span of 10,000 pixels would
be reported as 100.000 mm. The calibrated interpretation is instead:

- 100.669 mm along scanner X
- 100.124 mm along scanner Y

These results agree with the earlier approximate metal-ruler observation while
providing substantially better traceability and precision.

## 7. Evidence from rotated scans

The target-axis results were:

| Target orientation | Scale along target X | Scale along target Y | Residual RMS |
|---|---:|---:|---:|
| R000, mean of five stationary scans | 10.06644 µm/px | 10.01110 µm/px | 12.25 µm |
| R090 | 10.01309 µm/px | 10.06714 µm/px | 12.27 µm |
| R180 | 10.06738 µm/px | 10.01238 µm/px | 12.18 µm |
| R270, first scan | 10.01380 µm/px | 10.06722 µm/px | 14.94 µm |
| R270, repeat | 10.01514 µm/px | 10.06728 µm/px | 12.52 µm |

At R090 and R270, the approximately 10.013 and 10.067 µm/px values exchanged
target axes. At R180 they returned to the same association as R000. This is the
expected result when the scale difference is fixed to the scanner rather than
to the target. It provides strong evidence that scanner-axis calibration is
appropriate.

The first R270 scan had an elevated residual RMS of 14.94 µm. The repeat R270
scan returned to 12.52 µm, consistent with the other orientations. The first
result is therefore treated as a single-scan variation rather than a persistent
R270-specific effect.

## 8. Repeatability

### 8.1 Consecutive scans without moving the target

Five stationary R000 scans gave:

- Grid-centre X-position SD: 0.27 px, approximately 2.8 µm
- Grid-centre Y-position SD: 1.80 px, approximately 18 µm
- Grid-angle SD: 0.0063 degrees
- Mean affine residual RMS: 12.25 µm
- Residual RMS SD: 0.22 µm

The greater variation along one image axis is compatible with the mechanical
motion involved in flatbed scanning.

### 8.2 Removal and replacement of the target

Five replacement scans gave:

- Grid-centre X-position SD: approximately 14.6 px, or 147 µm
- Grid-centre Y-position SD: approximately 11.3 px, or 113 µm
- Grid-angle SD: approximately 0.076 degrees
- Mean affine residual RMS: 12.31 µm
- Residual RMS SD: 0.20 µm

Replacement changed global position and angle, as expected, but did not
materially change scale or residual performance. Digital registration should
therefore be used for exact alignment; the physical fixture is intended to
keep each specimen in the same scanner region rather than provide final
micrometre-level registration.

## 9. Recommended dimensional calibration

The dimensional error should be corrected in software. Original TIFFs should
remain immutable.

For preliminary calculations that only require axis-aligned dimensions, use:

```python
SCANNER_X_UM_PER_PX = 10.066935
SCANNER_Y_UM_PER_PX = 10.012375
```

For an arbitrary line segment:

\[
L = \sqrt{(\Delta x\,p_x)^2 + (\Delta y\,p_y)^2}
\]

For a segmented area containing \(N\) pixels:

\[
A = N p_x p_y
\]

For the final measurement pipeline, detected contours, crack skeletons, and
measurement points should be transformed using the complete affine
pixel-to-millimetre matrix stored in the applicable `metrics.json` file. This
corrects independent X/Y scales, small rotation, shear, and axis
non-orthogonality without resampling the source image.

An optional rectified working copy may be produced at exactly 10 x 10 µm/px for
ML tiling. A 1024 x 1024 tile would then cover exactly 10.24 x 10.24 mm. Final
scientific measurements should remain traceable to the raw scan and its
calibration transformation.

## 10. Limits and uncertainty

The reported standard deviations describe observed repeatability; they are not
yet a complete expanded measurement uncertainty. A final uncertainty budget
should also consider:

- Certified target uncertainty and tolerances
- Unreported local target-dot placement variation
- Dot-centre and crack-edge localization uncertainty
- Scanner warm-up and longer-term drift
- Plate flatness and distance from the scanner glass
- Fixture positioning
- Segmentation-model uncertainty
- Thresholding and morphological post-processing

A flexible local nonlinear warp is not currently recommended. Because the
certificate does not provide individually calibrated coordinates for every
dot, a high-order correction fitted to one target scan could imprint target
imperfections or scan noise into the correction. The global affine calibration
is well supported by the repeated and rotated scans.

## 11. Conclusions

1. The scanner has a repeatable and significant difference between its two
   dimensional scales.
2. Target rotation causes the measured scale values to exchange axes,
   confirming that the anisotropy is scanner-fixed.
3. At 2540 dpi, the best current combined scale estimates are 10.066935 µm/px
   along scanner X and 10.012375 µm/px along scanner Y.
4. Global X/Y or full affine dimensional correction is justified and should be
   applied in software.
5. Local nonlinear warping should be deferred unless a regularized correction
   can be validated on independent scans.
6. Target replacement affects position and rotation but not the fundamental
   calibrated scale; digital registration remains necessary.
7. A 2540 dpi master acquisition combined with on-demand 1024-pixel ML tiles
   provides a practical balance between retained surface detail, convenient
   physical sampling, and manageable dataset size.

## 12. Reproduction

Analyze one or more target scans with:

```sh
.venv/bin/analyze-jd-grid imaging/jd/*.tif
```

Per-scan results are written under `analysis/<scan-name>/`. The source code,
dependency list, and operating instructions are maintained in the project
root and `src/jdgrid/`.
