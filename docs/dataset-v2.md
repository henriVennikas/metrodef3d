# Load the Simple Concrete Crack Dataset v2

**MetroDef3D Simple Concrete Crack Dataset v2** is identified by
[DOI 10.5281/zenodo.24326086](https://doi.org/10.5281/zenodo.24326086).
It contains the same 10,000 observations as
[v1.0](https://doi.org/10.5281/zenodo.21340378), with an additive update to their
geometric references. Images, physical pixel-scale maps, seed identities and
original files are unchanged.

The v2 reference table and overlay describe the **`perspective-area` capture
stream**. The table is keyed by seed; it has no separate capture-stream column.
These references must not be assigned to another camera view of the same seed.

The update supplies 142 replacement visible-defect sidecars. Visible centreline
components are measured separately instead of being joined across portions
outside the camera frame. Mean width follows from visible polygon area divided
by this length. The other 9,858 observations use their original sidecars.
The [correction study](../supplementary/simple_concrete_crack_v1/studies/reference_correction/README.md)
documents the changes, numerical scope and benchmark impact.

## Files and extraction

The complete v2 dataset consists of **eleven unchanged base archive parts plus
`metrodef3d_simple_concrete_crack_v2_update.zip`**. Obtain these from the v2
Zenodo record when available. An existing verified v1.0 download supplies the
same base archives and does not need to be downloaded again.

Check the downloads against the record's `SHA256SUMS.txt`, then extract all base
archives into one directory and the update ZIP alongside them. Keep the original
files intact. The extracted layout is:

```text
data/
  metrodef3d/runs/prod_010k_cuda_20260705/
    seeds_0001_1000/
      img/83.jpg
      json/83.json
      pixel_scale/83.npz
      visible_defect/83.json
    ...
    seeds_9001_10000/
  metrodef3d_simple_concrete_crack_v2_update/
    reference_loader.py
    reference_values.csv
    DATASET_MANIFEST.json
    SHA256SUMS.txt
    overlay/
    provenance/
    quality/
    splits/
```

Archive filenames and original embedded metadata can still contain `v1_0`.
They identify preserved base files. `DATASET_MANIFEST.json` in the update package
identifies the combined dataset as v2 and records reference precedence.

## Verify and load references

The update loader requires Python 3.9 or later and only the standard library.
Run these commands from the extracted update directory:

```sh
# Check the update's internal files; use sha256sum on Linux.
shasum -a 256 -c SHA256SUMS.txt

python3 -B reference_loader.py \
  --dataset-root ../metrodef3d/runs/prod_010k_cuda_20260705 \
  --verify-all

python3 -B reference_loader.py \
  --dataset-root ../metrodef3d/runs/prod_010k_cuda_20260705 \
  --seed 83
```

`--verify-all` checks the original sidecars and all 142 replacements against
their recorded hashes. Missing or modified files raise an error. The loader
does not silently fall back to an old reference or write to the base dataset.

In Python, with the update directory on the module search path:

```python
from reference_loader import ReferenceDataset

dataset = ReferenceDataset(
    "/path/to/data/metrodef3d/runs/prod_010k_cuda_20260705",
    update_root="/path/to/data/metrodef3d_simple_concrete_crack_v2_update",
)
reference = dataset.load(83)
values = reference["measurands"]
length_mm = values["centerline_length"]
mean_width_mm = values["mean_width"]
maximum_width_mm = values["max_width"]
area_mm2 = values["crack_area"]

for component in dataset.iter_components(83):
    points_mm = component["centerline"]
    points_px = component["centerline_pixels"]
    # Draw or measure each component separately, without joining components.
```

**Do not load v2 targets directly from the original `json/<seed>.json` files.**
Their embedded `outputs.captures[].visible_defect` values remain v1.0. The
original sidecars also remain historical for the 142 replaced seeds. Use the
loader for geometry and scalar references, or `reference_values.csv` for the
complete scalar table. Original metadata still describes the unchanged images
and pixel-scale maps.

The replacement sidecars use schema 2 and `component_ranges`, while unchanged
sidecars retain schema 1. The loader handles both. Dataset v2, sidecar schema 2,
export revision `component-aware-2` and generator version `0.1.1` are separate
identifiers. See the [geometry conventions](reference-export-v2.md).

## Quality and partitions

The scalar table contains all 10,000 seeds, including excluded observations.
For a new study, exclude rows where either `quality_excluded` or
`additional_quality_excluded` is `true`. These flags combine the original 40
exclusions with the additional failed Boolean-cut seed 551, leaving 9,959
eligible observations. Keep those rows in the source data for inspection.

The retained split still records 6,972 training, 1,494 validation and 1,494 test
identities. Seed 551 remains listed in its historical validation partition but
has the additional exclusion flag. Reproduction of an existing experiment
requires its stated population and calibration protocol. Do not silently change
the historical split. Fully empty observations have defined zero references;
exclude zero denominators from relative-error calculations, not from all metrics.
Schema 2 also permits undefined quantities, marked by `null` and validity flags.
None of this update's references has an undefined scalar target.

## Existing models and benchmark reproduction

The retained transformer, ResNet-50 and ConvNeXt-Tiny were trained, normalized
and selected using **v1.0 references**. They have not been retrained on v2.
Their original predictions, calibration files and validation reports remain
historical records.

The [inference package](../supplementary/simple_concrete_crack_v1/inference/README.md)
reproduces that original benchmark. Its `benchmark` command does not apply the
v2 overlay. Merely pointing it at base archives downloaded from the v2 record
still loads original references and calibration.

For the updated benchmark, the
[correction study](../supplementary/simple_concrete_crack_v1/studies/reference_correction/README.md)
evaluates the fixed predictions against v2 references. It separately records
validation-only interval recalibration, excluding seed 551. The test identities
and central predictions are unchanged. The v2 package also includes
`tools/verify_benchmark.py` to check the saved comparison arithmetic; this is
not model inference or retraining. Identify the reference version and interval
calibration mode when reporting results.

The existing `supplementary/simple_concrete_crack_v1/` path is retained as the
dataset-family location. It contains both original v1.0 experiments and v2
reference-update studies; its name does not select the reference version.

## Citation and licences

Cite [dataset v2](https://doi.org/10.5281/zenodo.24326086) for the updated
references. Retain the [v1.0 DOI](https://doi.org/10.5281/zenodo.21340378) when
describing the original training data or reproducing historical results.
Data and documentation use [CC BY 4.0](../LICENSE-DATA.md); software uses
[Apache 2.0](../LICENSE).
