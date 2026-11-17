# Dataset studies and supporting material

These studies document the models, measurement methods and inference workflows
for the first MetroDef3D dataset:

**[MetroDef3D Simple Concrete Crack Dataset supplementary material](../supplementary/simple_concrete_crack_v1/README.md)**

Dataset v2 uses [DOI 10.5281/zenodo.24326086](https://doi.org/10.5281/zenodo.24326086).
See the [v2 loading instructions](../docs/dataset-v2.md) for current reference
values. The retained models were trained and selected using v1.0; historical
benchmark records remain labelled with that version.

- [Original v1.0 three-model measurement benchmark](../supplementary/simple_concrete_crack_v1/studies/model_benchmark/README.md)
- [Conventional image-processing benchmark](../supplementary/simple_concrete_crack_v1/studies/classical_benchmark/README.md)
- [Independent reference-export verification and clipping findings](../supplementary/simple_concrete_crack_v1/studies/reference_validation/README.md)
- [v2 reference correction overlay and benchmark impact](../supplementary/simple_concrete_crack_v1/studies/reference_correction/README.md)
- [Real-image transfer study and reference measurements](../supplementary/simple_concrete_crack_v1/studies/real_image_transfer/README.md)
- [Fixed-geometry background sensitivity study](../supplementary/simple_concrete_crack_v1/studies/fixed_geometry_background_sensitivity/README.md)
- [Retained models and inference workflows](../supplementary/simple_concrete_crack_v1/inference/README.md)

This index links to the dataset studies in `supplementary/simple_concrete_crack_v1/`. Each study provides its own methods, results and reproduction instructions.

- [Common real-image comparison of all four methods](../supplementary/simple_concrete_crack_v1/studies/expanded_real_images/all_methods/README.md): all 26 annotated images, paired results, bounds and descriptive summaries. The earlier five-image study is retained as an archive. Local study supplement.

- [Scale and annotation uncertainty example](../supplementary/simple_concrete_crack_v1/studies/uncertainty_example/README.md): Metrosert glass-target measurements, scanner/paper/photo transfer, five annotations and shared-scale model sensitivity. Local study supplement.

- [Expanded real-image evaluation and rotation sensitivity](../supplementary/simple_concrete_crack_v1/studies/expanded_real_images/README.md): 26 original-orientation observations evaluated by all four methods, frozen annotations and scale maps, plus a separate four-real/ten-synthetic rotation panel. Local study supplement.

- [Repeated annotation comparison](../supplementary/simple_concrete_crack_v1/studies/annotation_repeatability/README.md): four new passes plus the adopted original for IMG_8184 and IMG_8162, with IMG_8579 as a separate comparison. Includes within-operator spread and annotation-order sensitivity. Local study supplement.

- [Evaluated uncertainty of individual real-image references](../supplementary/simple_concrete_crack_v1/studies/reference_uncertainty/README.md): image-specific scale propagation and single-annotation variability for IMG_8184 and IMG_8162, retaining the original reference values.
