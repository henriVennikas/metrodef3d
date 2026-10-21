# MetroDef3D benchmark model inference

The three models were trained on the **MetroDef3D Simple Concrete Crack Dataset
v1.0**, available on Zenodo: [DOI 10.5281/zenodo.21340378](https://doi.org/10.5281/zenodo.21340378).
They form an initial feasibility study of using synthetic surface-defect images
with explicitly defined geometric reference quantities to train AI/ML
measurement-prediction systems and benchmark their performance. The common images
and reference values support comparison of both measurement predictions and
prediction intervals. The released models provide a reproducible baseline for
this dataset and measurement task. Applications to other synthetic scenes or
real photographs are exploratory extensions of that baseline.

This optional package runs the three retained measurement-prediction models:
the proposed transformer (v024, epoch 49), adapted ConvNeXt-Tiny (v031, epoch 50),
and adapted ResNet-50 (v034/v035, epoch 47). It supplies the original scalar and
asymmetric interval heads, physical-scale preprocessing, frozen validation
calibration, test identities and reference predictions. The package is self-contained and requires no training,
ImageNet weights or automatic model download.

Weights are separate release assets, not Git objects. This package is currently
prepared locally for review; no model release has been published.

## Install and model assets

From the MetroDef3D repository root, in a separate Python environment:

```sh
python3.12 -m venv .venv-models
. .venv-models/bin/activate
python -m pip install './supplementary/simple_concrete_crack_v1/inference[test]'
python -m pytest supplementary/simple_concrete_crack_v1/inference/tests -q
```

For CUDA, install the matching PyTorch 2.8.0 / torchvision 0.23.0 build appropriate
to the GPU before installing this package. Local validation uses Python 3.12,
PyTorch 2.8.0, torchvision 0.23.0, NumPy 2.5.0 and Pillow 12.3.0. CPU and Apple
Metal (`mps`) run float32. The original benchmark used H100 CUDA with bfloat16
autocast. Full precision on another device is not bitwise equivalent.

Extract the three reviewed `metrodef3d-<model>-v1.tar.gz` assets under
`supplementary/simple_concrete_crack_v1/inference/models/`. Each produces `transformer/`, `convnext_tiny/` or `resnet50/`,
containing `weights.pt`, `config.json`, `split_seeds.json` and provenance.
The loader verifies the weight SHA-256 and strictly loads tensors with
`weights_only=True`. There is no optimizer, scheduler or random-generator state.
Use the supplied `SHA256SUMS` to verify the downloaded archives before extraction.
The exact release URL and tag will be added when publication is approved.

## Reproduce the held-out benchmark

Download and extract the [MetroDef3D Simple Concrete Crack Dataset v1.0](https://doi.org/10.5281/zenodo.21340378).
Point `--dataset` at the directory containing all ten `seeds_...` runs, not at
the compressed archives. Its expected layout includes `seeds_0001_1000/json/3.json`,
`img/3.jpg`, `pixel_scale/3.npz` and `visible_defect/3.json` within that run.
Stored old host paths are rebased to the selected local run.

```sh
metrodef-predict --model-dir supplementary/simple_concrete_crack_v1/inference/models/transformer \
  --device cuda --precision bfloat16 --output supplementary/simple_concrete_crack_v1/inference/outputs/transformer-test \
  benchmark --dataset /path/to/extracted/dataset

python supplementary/simple_concrete_crack_v1/inference/tools/compare_benchmark.py \
  --model-dir supplementary/simple_concrete_crack_v1/inference/models/transformer \
  --run supplementary/simple_concrete_crack_v1/inference/outputs/transformer-test \
  --reference supplementary/simple_concrete_crack_v1/inference/reference/transformer \
  --output supplementary/simple_concrete_crack_v1/inference/outputs/transformer-comparison.json
```

Repeat with `convnext_tiny` and `resnet50`. For CPU or Mac GPU use `--device cpu`
or `--device mps` and omit `--precision bfloat16`. Every command requires a new
output directory. `benchmark --limit 3` is a quick smoke check, explicitly marked
as partial and rejected by the full comparison script.

The workflow evaluates all 1,494 frozen test samples, including seed 1625 with
zero reference quantities. MARE uses the 1,493 positive references. Other errors,
coverage and interval scores include all 1,494. Four validation-derived expansion
factors are loaded unchanged; test data never fits calibration. Interval score
uses alpha 0.05 and the relative score denominator floor is 2% of the training
mean. `predictions.csv` contains both raw and calibrated intervals. `metrics.json`
contains all reported scalar and interval metrics. The comparison checks paired
seeds and references exactly and reports numerical differences against archived
predictions. It does not silently accept a partial dataset or drop bad cases.

`python supplementary/simple_concrete_crack_v1/inference/reference/verify_metrics.py` independently checks 84 published
table values using the supplied CSVs. This is a saved-data audit, not model
execution. See `VALIDATION.md` for the actual release inference validation.

## Run a newly generated sample

With the generator installed and Blender available, the current example recipe
starts at seed 12345 and can produce three rendered samples:

```sh
metrodef3d generate --config examples/cracked_plane_blender_simple.yaml \
  --out runs/model_inference_demo --count 3
metrodef-predict --model-dir supplementary/simple_concrete_crack_v1/inference/models/transformer \
  --output supplementary/simple_concrete_crack_v1/inference/outputs/generated-12345 \
  generated --metadata runs/model_inference_demo/json/12345.json
```

The current recipe may differ from the archived dataset recipe. For a controlled
extension of the original population, retain its recipe and generator version
and change only the seed. Generated outputs must include image, visible-defect
JSON and physical-scale NPZ sidecars. A seed outside 1–10,000 avoids the released dataset's
seed range, but alone does not establish a new distribution or experimental
independence from earlier development data.

```sh
metrodef-predict --model-dir supplementary/simple_concrete_crack_v1/inference/models/transformer \
  --output supplementary/simple_concrete_crack_v1/inference/outputs/new-seed \
  generated --metadata /path/to/run/json/12345.json --stream perspective-area
```

The output includes the construction-defined references and frozen-split seed
membership. References are read from the generator sidecar; they are never
estimated from an image. Seed membership only describes the original split: the
same seed with a changed recipe is a changed observation. Rendering appearance,
geometry or camera changes may move an image outside the training distribution.
The workflow needs the scale and visible-defect sidecars; a preview render that
omits these cannot run this measurement model.

## Run a photograph with known physical scale

```sh
metrodef-predict --model-dir supplementary/simple_concrete_crack_v1/inference/models/transformer \
  --output supplementary/simple_concrete_crack_v1/inference/outputs/photograph \
  image --image /path/to/crack.jpeg --scale /path/to/scale.npz --scale-grid original
```

The NPZ contains float arrays `scale_x_mm_per_px` and `scale_y_mm_per_px`, in
mm/pixel along the image's horizontal and vertical directions. With
`--scale-grid original`, both arrays must match the original image dimensions.
RGB is resized over the entire frame to 1024 × 1024 with bilinear interpolation;
scale arrays are bilinearly resized and their directional values multiplied by
original width/1024 and original height/1024 respectively. The model receives
RGB in [0,1] plus `sqrt(scale_x * scale_y)`. No cropping, contrast correction,
ImageNet normalization, lens correction or inferred camera scale is applied.

If a scale map has already been expressed in **mm per 1024-grid pixel**, use
`--scale-grid model`. These arrays must be 1024 × 1024 and are not scaled again.
This is the convention used by the four archived real-image study NPZ files:

```sh
metrodef-predict --model-dir supplementary/simple_concrete_crack_v1/inference/models/transformer \
  --output supplementary/simple_concrete_crack_v1/inference/outputs/IMG_8184 \
  image --image supplementary/simple_concrete_crack_v1/studies/real_image_transfer/IMG_8184/IMG_8184.jpeg \
  --scale supplementary/simple_concrete_crack_v1/studies/real_image_transfer/IMG_8184/IMG_8184_scale.npz --scale-grid model
```

For a uniform, isotropic scale at the original image grid, replace `--scale`
with `--mm-per-pixel 0.05`. A single scalar is unsuitable when perspective causes
substantial spatial variation. Missing, nonfinite, nonpositive or dimensionally
inconsistent scale data is rejected. Apply EXIF orientation to both image and
scale together beforehand; automatic image-only rotation is deliberately avoided.

Non-square images are resized without cropping; directional scaling preserves
physical pixel area, but the models saw square images during training. Large
aspect-ratio changes and unfamiliar appearances require separate assessment.
Physical scale must describe the surface being measured, not an unrelated plane.

## Outputs and interpretation

Each target has a mean prediction, raw lower/upper bounds and bounds expanded
by the frozen synthetic-validation factors. Units are mm (length and widths)
and mm² (area). Predictions are not clipped to positive values; no postprocessing
is added to make them resemble references. Scalar predictions are direct model
outputs, not measurements obtained from a segmentation mask.

`--dense` on `generated` or `image` additionally saves `dense.npz`: defect,
skeleton and boundary **logits**, plus auxiliary `width_mm`, all on the 1024
input grid. Use sigmoid for probabilities. These auxiliary maps are not
independently validated local measurement intervals and do not determine the
four scalar predictions. Enabling them leaves scalar outputs unchanged.

ResNet always uses one image per forward pass, current-image BatchNorm statistics
and disabled dropout. It updates neither weights nor stored BatchNorm buffers.
Ordinary stored-statistics `eval()` is not the reported ResNet configuration.
The package enforces batch one for every model.

Synthetic calibration describes prediction error on the synthetic population;
it does not establish coverage for real photographs or unfamiliar generated
surfaces. Bounds omit physical-scale and annotation uncertainty. The retained
models were trained on the simple crack baseline, and these three runs do not
establish stable architecture rankings. See `supplementary/simple_concrete_crack_v1/studies/model_benchmark`
and `supplementary/simple_concrete_crack_v1/studies/real_image_transfer` reports for protocol and observed limitations.

## Licenses and source

Code and prepared model weights follow MetroDef3D's Apache-2.0 license. Reference
predictions and supplementary study data retain CC BY 4.0. Each weight asset
records its original checkpoint SHA-256, selected epoch and implementation hashes.
CNNs use torchvision backbones initialized without pretrained weights. See NOTICE.
`tools/export_weights.py` documents tensor-only extraction from a trusted original
training checkpoint. The exported tensor equality, not byte-identical serialization,
is the export invariant. Keep config, weights, split and calibration together.
