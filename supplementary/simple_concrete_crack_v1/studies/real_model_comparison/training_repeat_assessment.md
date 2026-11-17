# Training-repeat assessment

Prepared 7 November 2026. Planning only. No training or paid compute was started.

The real-image comparison addresses the field-comparison part of R1.C5. It does not estimate training-seed variability. Bootstrapping five field images or rerunning deterministic inference would not resolve that part of the comment.

## Comparable repeat design

Use three fresh training seeds per architecture on the corrected reference version, with fixed partitions, the documented per-architecture settings, 50 epochs, one checkpoint-selection rule and the same corrected validation interval calibration. Exclude invalid validation seed 551 consistently. Retain ResNet's per-image BatchNorm validation/inference policy. Use validation only for selection/calibration. Do not alter hyperparameters after inspecting test results.

The retained historical runs were trained and selected with the old references. They should remain historical comparators rather than be pooled unqualified with two corrected-label runs as three exchangeable repeats. A clean three-seed corrected-label comparison requires nine new runs. Using the old labels for all repeats would answer a different question and would require explicitly retaining a known reference defect during training.

Before launch, verify that the corrected sidecar overlay reaches scalar targets and normalization, and audit whether the dense supervision is affected by disconnected visibility. Freeze the reference version, exclusions, target statistics, seeds and source hashes. Run a short loading/forward check before any long job. No implementation or numerical estimates in this note imply these prerequisites have been completed.

Report each run's selected epoch, per-measurand errors, interval performance and runtime, with between-run spread. Three seeds provide a modest initial assessment, not proof of a stable universal architecture ranking. Field inference can then reuse the frozen images and references, including all retained difficult cases.

## Runtime basis

Historical H100 observations:

- Transformer: approximately 7 hours, inferred from historical file times rather than a recorded total.
- ConvNeXt-Tiny: 8 h 28 min for 50 epochs, including setup and final evaluation.
- Corrected-inference ResNet lineage: 8 h 34 min for the ten-epoch diagnostic plus forty-epoch continuation, including diagnostic overhead. The earlier original fifty-epoch ResNet run took 8 h 48 min. These are planning references, not exact timings for a fresh corrected-label run.

Allow roughly **24–27 GPU-hours per three-model seed set**, or **72–81 GPU-hours for nine fresh runs**, before additional verification, queue delays or retries. This is around three to three-and-a-half days sequentially on similar hardware. Actual availability and current price have not been checked. No cost or pod-lifecycle action is authorized by this assessment.

If that budget is unsuitable, retain the single-run limitation explicitly in the response and distinguish the now-completed field comparison from the uncompleted repeated-training request. The existing results cannot be described as statistically robust architecture rankings.
