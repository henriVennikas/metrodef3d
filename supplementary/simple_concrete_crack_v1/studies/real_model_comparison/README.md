# Real-image comparison of retained measurement pipelines

**Historical five-image study.** The current comparison evaluates all four methods on [the same 26 images](../expanded_real_images/all_methods/README.md). The original protocol and results below are retained for provenance.

Study recorded on 7 November 2026. Nothing has been published.

See [full report](REPORT.md), [paired measurements and bounds](comparison.csv), [per-target summary](summary.csv) and [per-image comparison](comparison_heatmap.png). Five existing annotated images were eligible. The author identified them as separate physical cracks on different surfaces. Their purposive selection and annotation limitations are retained in the report. Additional images and the independent glass calibration remain pending.

## Reproduce

Use the optional inference package under `../../inference` and the reviewed model assets. From this study directory, in an environment containing its inference dependencies:

```sh
python verify_inputs.py
python run_learned.py --assets /path/to/reviewed/model-assets --model transformer
python run_learned.py --assets /path/to/reviewed/model-assets --model resnet50
python run_learned.py --assets /path/to/reviewed/model-assets --model convnext_tiny
python run_conventional.py
python summarize.py
python make_report.py
```

The execution scripts refuse to overwrite existing model result directories. Use a separate study copy with fresh result directories for reproduction. Model weights are not duplicated here. Install the conventional pipeline's NumPy, SciPy, scikit-image, NetworkX and Pillow dependencies and Matplotlib for reporting. Exact environments are recorded in `requirements-*.txt` and each run record.

`protocol.json` was frozen before this comparison. It records input hashes, inclusion rules, inference and calibration policies. `specimen_identity.json` records the author's subsequent clarification of physical crack identities. `input_verification.json`, `verification.json` and `transformer_parity.csv` document reference/input checks and numerical parity with the retained transformer results. All four methods receive identical image/scale tensors, checked by hashes.

`inputs/` contains adopted annotations, images, paired scale maps, homography records and references. One ancillary historical preprocessing record contains several image entries. A public copy may redact machine-specific paths, documented in `redactions.json`, without changing numerical data. Original unredacted records remain in the local research archive. This redaction does not alter model inputs or references.

No field references fitted thresholds, learned weights or interval calibration. The factors/radii in `calibration.json` are from the corrected synthetic validation study. Current image scales remain provisional pending the independent glass-target calibration. Model predictions and annotation references share scale, and annotation uncertainty is unquantified.

The repeated-training part of R1.C5 is assessed in [training repeat assessment](training_repeat_assessment.md). No new training was performed.
