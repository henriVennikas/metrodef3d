# Four methods on the common 26-image set

The transformer, ResNet-50, ConvNeXt-Tiny and conventional image-processing pipeline are evaluated on all 26 images in the [frozen real-image set](../README.md). See the [comparison report](REPORT.md), [paired values and bounds](comparison.csv), [descriptive summaries](summary.csv) and [verification record](verification.json).

The models were trained on [MetroDef3D Simple Concrete Crack Dataset v1.0](https://doi.org/10.5281/zenodo.21340378). This is a feasibility demonstration of synthetic-reference training and benchmarking, with exploratory application to real surfaces. The selected real images do not establish population performance or a stable architecture ranking. Some photographs share a physical fracture. All methods use the same observations, adopted annotations and scale maps. No settings were fitted to these real images.

## Inputs and interpretation

`../inputs/<image>/` contains each surface photograph, paired target image, adopted annotation, references, target-fit records and directional scale arrays. The arrays already express millimetres per pixel on the 1024-square model grid. Every method uses full-frame bilinear RGB resizing without cropping or contrast adjustment. Learned models use the geometric mean of the directional scales as their fourth input channel. The conventional pipeline uses both directional scales for geometric measurement, under the documented local-orthogonality assumption.

The original adopted annotations and image scales are retained for all methods. The later Metrosert propagation and repeated annotations belong to separate [uncertainty](../../uncertainty_example/README.md) and [annotation-repeatability](../../annotation_repeatability/README.md) studies. They are not silently substituted into this common comparison. Model prediction bounds exclude those reference uncertainties.

`protocol.json` records the complete image list and source/code hashes before this run. Model weights are checked by hash. Transformer epoch 49, ResNet-50 epoch 47 and ConvNeXt-Tiny epoch 50 are retained. Inference uses CPU float32 and batch one. ResNet-50 uses per-image BatchNorm with dropout disabled. The conventional processing sequence and settings are unchanged from the synthetic validation selection. `calibration.json` retains the synthetic calibration history. Only its `corrected_refs_valid_cohort` entries are used here.

The conventional masks and extracted paths are included under `results/conventional/`. All methods' individual outputs, configurations and execution records are under `results/`. Interval scores use the 95% interval score with a factor of 40 on misses. Relative scores are divided by each image's own reference before aggregation. Inclusions and widths should be interpreted together, particularly for the conventional pipeline's fixed residual radii.

## Reproduce

The frozen inference source is included in `source/`. Install the learned-model and conventional dependencies in the corresponding requirements files. The model assets are described in the [inference workflow](../../../inference/README.md). Weights are not duplicated in this study.

In a separate study copy with empty `results/` model directories, run:

```sh
python run_learned.py --assets /path/to/reviewed/model-assets --model transformer
python run_learned.py --assets /path/to/reviewed/model-assets --model resnet50
python run_learned.py --assets /path/to/reviewed/model-assets --model convnext_tiny
python run_conventional.py
python summarize.py
```

Execution scripts refuse to overwrite existing results. `summarize.py` can be rerun on the saved outputs. It verifies common inputs, frozen sources and references, calibration arithmetic, model-state checks and parity with historical predictions before rebuilding the tables and report. The [previous five-image comparison](../../real_model_comparison/README.md) is preserved as an earlier study. The current common comparison covers all 26 images.
