# Selected real-image measurement examples

Four exploratory examples accompany
the synthetic benchmark: IMG_8184 (painted plastered stone wall), IMG_8162 (rough
concrete surface), IMG_8169 (exposed-aggregate appearance, partial shadow), and
IMG_8139 (regular concrete floor).
These are selected scenes, not a random sample of field conditions.

## Contents

Each image folder includes the original crack photograph, its separate scale-grid
photograph, an image-named annotation JSON, an annotation overlay, physical scale
maps, grid-fit coordinates and QA, predictions and bounds, a model probability
map/mask, reference calculations, width sections and a recomputation script.
`comparison.csv` combines all sixteen scalar results; `comparison_figure.pdf`
shows photographs, references and model masks. The JSON manifest identifies the
image pairs and source hashes. The chosen mask for IMG_8162 is supplied as
`IMG_8162_annotation.json`.

## Reference definitions

The visible surface opening includes interpreted recessed crack edges. Native
pixel-centre annotation vertices are transformed using the paired-grid planar
homography. Length is centreline polyline length, area is polygon area, and mean
width is area/length. Maximum width is estimated from perpendicular intersections
at 0.05 mm stations using a centred 1 mm chord for local direction; the closest
intersections enclosing the centreline are used. The reference JSON includes
checks at 0.5/2 mm chords and 0.025/0.1 mm station spacings. These ranges are method
sensitivity, not uncertainty intervals. IMG_8169 is particularly sensitive:
maximum-width estimates span 1.009–1.611 mm under these settings. IMG_8139
has a baseline maximum of 1.092 mm. Varying the chord gives 1.041–1.168 mm,
and varying station spacing gives 1.082–1.089 mm. Its boundary encloses debris.
No hand-placed width-probe measurements were made for IMG_8139.

Hand-placed width probes are supplied for IMG_8184, IMG_8162 and IMG_8169
only. These are descriptive checks. Their spacing/perpendicularity
is not enforced; neither their SD nor the reference-method sensitivity is a
complete measurement uncertainty. No multi-annotator study is reported.

## Scale and image formation

An iPhone 15 Pro Max supplied 3024² images. The paired paper-grid photograph was
taken at approximately the same camera position/settings. Paper target 01 has
50×50 positions, nominal 2 mm pitch, 1 mm dots and three orientation rings. Its
measured coordinates are in `calibration/print_target_01_points.npz` (`scanner_mm`).
Scanner scale factors 0.010066935 and 0.010012375 mm/pixel derive from the Epson
V600 glass-target comparison at 2540 dpi. The glass target's certified spans
provide dimensional scale references, not certified coordinates for every dot.
The [calibration supplement](calibration/README.md) includes the original
certificate, fourteen scanner records, scale-factor calculations and transfer
limitations. Certificate tolerances are not stated calibration uncertainties.

The image-to-physical mapping uses the measured paper coordinates. Rings anchor
indices in cropped grids. Held-out grid-fit RMS residuals for IMG_8184, IMG_8162,
IMG_8169 and IMG_8139 are 0.1286, 0.1086, 0.0908 and 0.0617 mm. Homography residuals do not quantify complete
crack-measurement uncertainty. Camera pose repeatability, target-to-surface offset,
paper flatness, lens distortion, surface relief and interpretation of edges remain
unquantified. Both the model and annotation use the same image/scale information.

## Inference and interpretation

The frozen synthetic-trained transformer (epoch 49) takes full-frame RGB resized
to 1024² and a geometric-mean physical scale channel. Scale maps include the
3024/1024 factor and pixel-centre alignment. There is no crop, contrast correction,
real-image training or interval fitting to these references. CPU float32,
batch one, dropout off. Checkpoint SHA256:
`c07657297350c1ace1e1eb797e83b1f30069cfb1511c3637a7352c2be1139952`.

Predictions are direct scalar-head outputs. The displayed auxiliary mask uses
probability ≥0.5 and does not calculate those scalar measurements. Interval
widening remains fitted to synthetic validation. Real-image coverage is not
established, and the bounds exclude unquantified real-image reference and scale
uncertainty. IMG_8184 and IMG_8162 show deviations below 10% for all four
quantities. Their continuous, well-defined single cracks are closer to the training
appearance. IMG_8169 and IMG_8139 have visually disjoint openings containing debris
and more variable width profiles. These are plausible contributors to the larger
discrepancies, but the scenes do not isolate their effects. IMG_8169 has all four
references outside the bounds. For IMG_8139, length is underestimated by 51.7%,
mean width overestimated by 78.7%, maximum width overestimated by 19.4%, and area
underestimated by 8.2%. Only its area reference lies within the bounds. Closer area
agreement does not imply agreement for the other quantities. This is exploratory
application beyond the synthetic benchmark, not population-level field validation.

## Reproduce reference calculations

With Python, NumPy and Pillow:

```sh
python IMG_8169/recompute_reference.py
```

The script checks the reference geometry and recalculates comparison files from
saved predictions; it does not run or train a model. Keep an original copy if
editing annotation geometry. The supplied data allow inspection and alternative
boundary, skeleton and measurement procedures. Retained model inference is provided in the
[inference package](../../inference/README.md). Code follows Apache-2.0; images, annotations and result data
are provided under CC BY 4.0. Nothing is published
by executing these local scripts.

Regenerate the four-row photograph/reference/model overview with
`python make_comparison_figure.py`. The rows follow the manifest order.
