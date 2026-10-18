# Physical scale reference for the real-crack photographs

This supplement documents the glass-target → scanner → paper-target → photograph
scale chain used for IMG_8184, IMG_8162, IMG_8169 and IMG_8139. It records the
measurements and assumptions behind the supplied scale maps. It does not assign
a complete expanded uncertainty to the crack measurements or annotations.

## Glass reference

The reference is a JD Photo Data SL12-4 low-reflective chrome-mask target,
125 × 125 × 1.5 mm, with a 50 × 50 grid, nominal 2 mm centre pitch, 1 mm dots and
three central orientation rings. The original two-page
[certificate of conformity](JD194821-001.pdf), number **008/194821-001**, is dated
22 May 2026. It records measurement at 21 °C and 50% humidity and states that the
calibration equipment is traceable to NIST.

| Feature | Measured value (mm) | Certificate tolerance (µm) |
|---|---:|---:|
| A1, top outer-centre span | 97.9994 | ±3.00 |
| A2, bottom outer-centre span | 97.9994 | ±3.00 |
| A3, left outer-centre span | 97.9992 | ±3.00 |
| A4, right outer-centre span | 97.9993 | ±3.00 |
| A5, diagonal | 138.5915 | ±3.00 |
| CD1, dot diameter | 1.0002 | ±0.50 |

The certificate labels these limits **tolerances**. It supplies no expanded
calibration uncertainty or coverage factor. The tolerances are therefore not
used as a stated uncertainty. It also does not certify each of the 2500 dot
coordinates. The reference-coordinate columns in the scanner CSV files describe
an idealized lattice based on the certified outer spans, not individually
certified dot positions.

## Scanner characterization

An Epson Perfection V600 Photo was characterized on 4 September 2026 at 2540 dpi.
Fourteen scans comprise five stationary R000 scans, five R000 scans after target
removal/replacement (`rp`), one R090, one R180 and two R270 scans. Each record
contains 2497 detected solid dots; the three ring centres are inferred from the
lattice and excluded from residual statistics.

For each edge, scale is its certified length divided by the detected pixel
span. Opposing edges are averaged. The target axes are mapped back to scanner
axes for rotations of 90° and 270°, then the fourteen results are averaged.
A5 is retained as a recorded diagonal result and CD1 identifies the dot size;
neither sets the two axis factors used here.

| Quantity | Mean | Sample SD | Minimum–maximum |
|---|---:|---:|---:|
| Scanner X (µm/px) | 10.066935 | 0.000614 | 10.065764–10.067759 |
| Scanner Y (µm/px) | 10.012375 | 0.001553 | 10.009961–10.015139 |
| Affine radial residual RMS (µm) | 12.48 | 0.73 | 11.89–14.94 |

The scale difference follows the scanner axes when the target rotates. The
applied factors are **0.010066935 and 0.010012375 mm/px**. They differ from the
nominal 0.010 mm/px by approximately 0.669% and 0.124%. Affine residuals combine
scanner effects, localization and unreported local target geometry. Their RMS
and the sample SDs above are not expanded uncertainty estimates. No local
nonlinear scanner correction was applied to the paper target.

Per-scan `metrics.json` and detected-centre `dots.csv` files are supplied under
`scanner_scans/`. `scanner_summary.csv` lists the fixed-scanner-axis results.
Recompute these summary statistics without additional dependencies:

```sh
python recompute_scanner_summary.py
```

## Transfer to paper target 01

The field images use paper target 01, scanned at the same nominal 2540 dpi on
28 September 2026. Detection at half sampling was followed by darkness-weighted
centre refinement on the original pixels. Fixed scanner-axis coordinates are
obtained by multiplying each pixel coordinate by its corresponding axis factor.
The paper pattern is not forced to its nominal dimensions.

`print_target_01_points.npz` contains the original pixel centres, the resulting
`scanner_mm` coordinates and the solid-dot detection mask. The QA image shows
the detected centres. `print_target_01.json` records the dimensional results:

- Mean opposing outer-centre spans: 98.040807 × 97.981008 mm, versus 98 × 98 mm nominal.
- Fitted lattice pitch: 2.000533 × 1.997929 mm.
- Affine lattice residual RMS: 26.30 µm.

The per-point coordinates, rather than a single nominal pitch, define the
paper reference. The residual includes print nonuniformity and scanner effects;
it is not an expanded uncertainty. Stability between scan sessions and scanner
bed positions is assumed in this transfer and was not independently quantified.

## Transfer to photographs

A fixed stand held the phone while each scale-target and crack photograph pair
was acquired without deliberately changing the camera settings or position.
The target was then removed for the crack photograph. Grid detection and the
measured paper coordinates provide a planar image-to-physical homography.
Image-specific fit coordinates, QA and scale maps are in the parent case folders.

Held-out grid-fit RMS residuals are 0.1286, 0.1086, 0.0908 and 0.0617 mm for
IMG_8184, IMG_8162, IMG_8169 and IMG_8139, respectively. These assess the grid
mapping, not complete crack-measurement uncertainty. The local scale maps account
for resizing from 3024² to 1024² pixels and pixel-centre alignment. Both model
predictions and image-derived references use this scale information.

Camera displacement between paired photographs, target-to-surface offset, paper
flatness, lens distortion, surface relief and manual boundary interpretation
remain unquantified. The manufacturer's traceability statement and the recorded
transfer calculations document the dimensional reference chain. They do not by
themselves establish a complete uncertainty budget for field crack measurements.
The model prediction intervals characterize model errors and exclude these
scale and reference-annotation contributions.

## Reproduction scope and provenance

The saved detections and metrics permit inspection of the scanner comparison
and recomputation of its scale factors. The original TIFF scans remain in the
acquisition archive and are not duplicated in this compact supplement. Therefore
pixel-level detection cannot be repeated from this supplement alone. The detector
source is retained in `tools/jdgrid/`; the portable paper-target script is in
`tools/measure_paper_targets.py`. With the original TIFFs and dependencies from
`requirements.txt`, run:

```sh
PYTHONPATH=tools python -m jdgrid.cli /path/to/glass_scans/*.tif --output-root /path/to/new_results
python tools/measure_paper_targets.py /path/to/paper_scans --output /path/to/new_paper_results
```

The scanner records and detector are preserved from the September study. The
paper script changes only input/output path handling. Certificate, source and
result hashes are listed in the parent `checksums.json`. The certificate is an
unaltered third-party document; its inclusion does not relicense it under the
repository's code or study-data licenses.
