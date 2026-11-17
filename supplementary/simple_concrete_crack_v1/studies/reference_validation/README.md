# Independent reference-export verification

This supplement checks the production reference export used for **MetroDef3D Simple Concrete Crack Dataset v1.0**, [DOI 10.5281/zenodo.21340378](https://doi.org/10.5281/zenodo.21340378).

**The study identified clipping defects. It is not a blanket validation pass.** Start with [REPORT.md](REPORT.md), [summary.json](summary.json) and [diagnostics.png](diagnostics.png). All failures are retained alongside ordinary numerical discrepancies. The released data, trained weights and benchmark predictions remain unchanged.

The independent calculations use prescribed dimensions and world-plane geometry, without invoking the production reference helpers. The actual Blender camera setup and sidecar writer are executed without rendering. The separate [reference-mask diagnostic](../classical_benchmark/README.md) measures extraction from known masks and is not this validation.

## Reproduction

Use a fresh copy of this study directory so the saved evidence remains intact. Python dependencies are listed in [requirements.txt](requirements.txt). Blender 5.1.2 was used. The Blender executable needs permission to start its local runtime; no GPU render, network access or model training is required.

```sh
python -m pytest test_oracles.py -q
python fixtures.py
blender --background --factory-startup --python run_blender.py
python audit_dataset.py --dataset PATH_TO_DATASET --split PATH_TO_SPLIT_JSON
python summarize.py
```

The dataset path is the root containing `seeds_0001_1000/` through `seeds_9001_10000/`. Its original `json/` and `visible_defect/` files are needed. The retained [split manifest](../../inference/reference/transformer/split_seeds.json) identifies the original train/validation/test partitions. The audit reads data only. The scripts write their results inside the study copy and do not update the source dataset or generator.

`run_blender.py` always uses the frozen `production_export.py`. That file contains exact function bodies from the generator, with the imports and schema constants needed to execute them. [Provenance](provenance.json) records hashes and the comparison with the dataset's archived generation script. The clipping-tolerance sweep uses separate in-memory copies only. Regenerating a study for corrected production code requires a new version and a new source manifest; do not replace the frozen implementation in this record.

The 72 fixtures comprise 65 ordinary cases, six near-boundary cases and one exit/re-entry case. Four additional tolerance runs give 76 writer executions. Failed writer calls may leave empty JSON files, exactly as produced by the writer. Their exceptions are recorded in `results/runs.json`. A failed production check must not be converted into an oracle test pass or omitted from the summary.

## Interpretation and limits

- The eight oracle tests verify independent known-answer calculations. They do not mean all production checks passed: seven ordinary fixtures exceeded at least one predeclared numerical criterion, and three boundary stress cases raised exceptions.
- Circular-arc convergence separates a discrete polygon's exact quantities from its smooth mathematical counterpart. Finer sampling is not a universal numerical improvement.
- The released-data audit flags confirmed bridges and retains one unconfirmed candidate. The diagnostic subtraction is not a new reference release. Independent ideal-camera clipping and subtraction do not agree exactly in every case. Both results are retained for correction work.
- Visible polygon area and construction-normal station width are different definitions when a frame clips an opening laterally. The stated maximum width is not automatically a boundary-derived maximum visible opening.
- The study does not check rendered Boolean mesh fidelity, all stochastic topology, image segmentation, physical calibration or real-image measurement uncertainty.

Full per-case values are in [discrepancies.csv](discrepancies.csv), and per-seed findings in [dataset_topology_audit.csv](dataset_topology_audit.csv) and [JSON](dataset_topology_audit.json). [Protocol](protocol.json) records the criteria fixed before executing the fixtures. Source/output hashes are in `checksums.json`.

Software follows the repository [Apache 2.0 licence](../../../../LICENSE). Documentation and study data follow [CC BY 4.0](../../../../LICENSE-DATA.md). No changes have been published by these scripts.

## Subsequent correction

The [component-aware correction study](../reference_correction/README.md) fixes the identified export defects and provides an additive overlay for 142 observations, including the previously unconfirmed case. It also quantifies the effect on the unchanged model predictions and recalibrated bounds. The failure fixtures and results in this directory remain the original verification record.

That overlay is included in **dataset v2**,
[DOI 10.5281/zenodo.24326086](https://doi.org/10.5281/zenodo.24326086).
The [v2 loading guide](../../../../docs/dataset-v2.md) describes reference
selection without changing the original dataset. The audit commands above
continue to test the historical v1.0 exporter and source files.
