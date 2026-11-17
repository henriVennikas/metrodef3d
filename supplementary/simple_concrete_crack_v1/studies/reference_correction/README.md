# Reference correction and benchmark impact

This study documents the reference update from **MetroDef3D Simple Concrete Crack Dataset v1.0**, [DOI 10.5281/zenodo.21340378](https://doi.org/10.5281/zenodo.21340378), to **dataset v2**, [DOI 10.5281/zenodo.24326086](https://doi.org/10.5281/zenodo.24326086). It follows the [independent reference verification](../reference_validation/README.md). The original models were trained, normalized and selected using v1.0 references.

Read [REPORT.md](REPORT.md) for the changes and before/after results. The correction affects 142 observations (92 training, 24 validation, 26 test). The original dataset and retained predictions/weights are untouched. All four methods are evaluated on the same 1494 test identities with unchanged central predictions.

## Use corrected references without changing originals

For dataset use, follow the [v2 loading guide](../../../../docs/dataset-v2.md).
The release package supplies the complete scalar table and a loader that verifies
all original sidecars and the replacements. The smaller study loader below is
retained for reproducing this study.

Corrected sidecars are in [`overlay/visible_defect/`](overlay/visible_defect/), with original and corrected SHA-256 hashes in [`overlay/manifest.json`](overlay/manifest.json). Only listed seeds have replacements. The original metadata JSONs still contain the original values; consumers must explicitly use the overlay.

The frozen overlay manifest names v1.0 as its source dataset and
`component-aware-2` as its export revision. These are provenance identifiers;
the containing release is dataset v2.

```python
from load_overlay import load_visible_reference
reference = load_visible_reference(original_sidecar_path, "overlay")
measurands = reference["measurands"]
```

For corrected sidecars, schema 2 adds `component_ranges`: half-open `[start, stop]` ranges into the flat station arrays. Sum/draw each component separately. Never draw or measure a connecting edge between ranges. `measurand_validity` marks undefined quantities, represented as JSON `null`, for visible polygons without enough centreline support. Fully empty observations retain defined zeros. See the [schema and migration documentation](../../../../docs/reference-export-v2.md). No corrected observation in this dataset overlay has an undefined target.

The loader verifies the original and replacement hashes for a corrected seed, returns the original for an unlisted seed, and writes nothing. It does not update old training normalizations, old calibration, saved predictions or historical reports.

## Reproduce the study

Python dependencies are NumPy and Matplotlib, with pytest for the generator tests. Tested versions are in `requirements.txt`. Blender 5.1.2 runs the camera export without rendering. Use a fresh study copy to preserve saved evidence. `freeze_export.py` refuses to overwrite its frozen code, and regeneration refuses to overwrite an existing overlay.

```sh
# In a fresh study directory, before creating corrected_export.py:
python freeze_export.py --generator-root PATH_TO_GENERATOR
python screen_candidates.py --dataset PATH_TO_DATASET
blender --background --factory-startup --python run_fixture_regression.py -- --fixtures ../reference_validation
blender --background --factory-startup --python regenerate_candidates.py -- --dataset PATH_TO_DATASET --original-export ../reference_validation/production_export.py --split ../../inference/reference/transformer/split_seeds.json
python compare_benchmarks.py --learned-study ../model_benchmark --classical-study ../classical_benchmark
python make_report.py
```

The source dataset must contain its original `seeds_*/json/` and `seeds_*/visible_defect/` directories. The generator source revision must match `source_manifest.json`; use the frozen `corrected_export.py` to reproduce this exact study. The independent fixture inputs and original exporter remain frozen in the adjacent verification study. The `code/` directory retains the changed generator sources, and `source_changes.diff` records the implementation change. Generator tests also cover the preview path. The overlay viewer draws component ranges rather than connecting visible portions.

## Comparison modes

`benchmark_comparison.csv` preserves five modes:

- `original`: historical references and historical calibration, reproduced against saved results.
- `corrected_fixed_calibration`: corrected references with the original calibrated bounds.
- `corrected_recalibrated_same_cohort`: corrected validation references using the original calibration cohort, as an isolation diagnostic.
- `corrected_recalibrated_valid_cohort`: corrected validation references with known-invalid seed 551 excluded from learned-model calibration. The conventional calibration already excluded it.
- `original_valid_cohort`: original references with the valid calibration cohort, to distinguish exclusion effects from reference correction.

No mode uses test data to choose calibration or model settings. The test population is unchanged. Existing training weights, selected checkpoints, normalizations, interval-score floors and conventional tuning settings remain fixed. Recalibration does not repair training targets or constitute a new training run.

`predictions/` contains per-observation corrected-reference test tables for fixed and recalibrated bounds. `calibration_comparison.json` gives all factors/radii and cohort sizes. `reference_changes.csv` distinguishes topology-only changes in the same runtime from small differences when replaying the archived exporter. `benchmark_verification.json` and `verification.json` record integrity and result checks.

The updated comparison uses the references supplied in dataset v2 (`component-aware-2`) and `corrected_recalibrated_valid_cohort` calibration. Historical study results remain unchanged. [Supporting recalculations](manuscript_integration/README.md) document the updated reference-mask diagnostic and real-image bounds. This recalculation does not retrain the retained models or change the frozen calibration bundled with the original inference package.

Software follows [Apache 2.0](../../../../LICENSE). Documentation and study data follow [CC BY 4.0](../../../../LICENSE-DATA.md).
