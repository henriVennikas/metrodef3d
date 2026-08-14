# Fixed Geometry Background Sensitivity Study

This package holds the fixed geometry sensitivity material reported with the MetroDef3D article. Eight defect geometries outside the public dataset seed range were each evaluated under eight procedural background and illumination conditions and 16 photographed concrete surfaces. The procedural background seeds are also outside the seeds 1--10,000 dataset release. No sensitivity geometry, background realization, or rendered observation was used for model training, validation, or selection. Geometry, camera, physical scale, and reference quantities remain fixed within each group while surface appearance changes. The complete study contains 192 observations.

Public repository location: <https://github.com/henriVennikas/metrodef3d/tree/main/studies/fixed_geometry_background_sensitivity>

The article figure uses defect seed `10316` as an illustrative example. Its reference values are:

| Measurand | Value |
| --- | ---: |
| Centerline length | 118.338913 mm |
| Mean width | 0.575418 mm |
| Maximum width | 0.635080 mm |
| Crack area | 68.094337 mm^2 |

## Contents

- `backgrounds/photographic/`: 16 concrete surface photographs named `001.jpg` through `016.jpg`. Source filenames and embedded metadata have been removed.
- `renders/procedural/`: the eight procedural observations for the seed `10316` example.
- `renders/photographic/`: the 16 photographed surface observations for the seed `10316` example.
- `reference/geometries/`: saved geometry, camera, lighting, and recipe data for all eight defect seeds.
- `reference/scene.json`: the seed `10316` scene retained for the single geometry command below.
- `reference/visible_defect.json`: fixed visible construction reference.
- `reference/pixel_scale.npz`: fixed directional physical pixel-scale maps.
- `results/`: the seed `10316` results used in the article figure and table.
- `results/full_study/`: all 192 calibrated predictions, per-geometry and pooled summaries, and a machine-readable report.
- `results/full_study/per_background_summary.csv`: errors and interval misses for each photographed surface, pooled over all eight geometries.
- `results/full_study/report.html`: interactive overview and per-seed inspection of every procedural and photographed observation.
- `renders/full_study/`: the 192 rendered observations used by the interactive report.
- `manifest.json`: generic background identifiers, dimensions, and SHA-256 checksums.

The photographic observations are not images of real cracks. Each photograph supplies concrete appearance as a Blender base-colour texture, while the crack and its references remain synthetic. The photographs also retain appearance arising from their original acquisition before renderer illumination is applied. The set is therefore intended for controlled appearance sensitivity analysis rather than validation on real cracks.

## Rerendering

From the MetroDef3D repository root:

```sh
PYTHONPATH=src python3 tools/render_photographic_background_pilot.py \
  --reference-metadata studies/fixed_geometry_background_sensitivity/reference/scene.json \
  --photo-dir studies/fixed_geometry_background_sensitivity/backgrounds/photographic \
  --out-dir runs/seed_10316_photographic_reproduction \
  --photos 001.jpg 002.jpg 003.jpg 004.jpg 005.jpg 006.jpg 007.jpg 008.jpg \
           009.jpg 010.jpg 011.jpg 012.jpg 013.jpg 014.jpg 015.jpg 016.jpg \
  --defect-seed 10316 \
  --output-seed-start 10316901 \
  --physical-width-mm 200 \
  --physical-height-mm 200 \
  --samples 32
```

The original study used Blender 5.1.2 and Cycles. Exact rendered pixels can depend on the Blender version and compute backend; construction references and nominal pixel-scale arrays do not depend on the selected photograph.

Repeat the command with the other files in `reference/geometries/` and matching `--defect-seed` and `--output-seed-start` values to reproduce the complete photographed set. The eight study seeds are `10155`, `10316`, `10558`, `10660`, `10694`, `10701`, `10784`, and `10866`.

The supplied prediction CSV files record the article baseline outputs. Another image measurement method can be evaluated on the same observations using the fixed references and can report central error, prediction range, coverage, and interval width under unchanged conditions. See `results/full_study/REPORT.md` for the complete summary and file descriptions.

## Article Figure Selection

The procedural panels S1--S4 in the article correspond to renders `002`, `004`, `001`, and `007`. The photographic panels P1--P4 correspond to renders `002`, `005`, `012`, and `015`. P1 and P2 are lower-error examples and P3 and P4 are higher-error examples when ranked by mean absolute relative error across the four scalar measurands. The accompanying article table reports each central prediction with calibrated upper and lower deviations in tolerance notation.

## License

The photographs, rendered observations, reference data, results, and reports in
this study are licensed under the Creative Commons Attribution 4.0
International licence (`CC-BY-4.0`). The photographed concrete surfaces were
acquired by Henri Vennikas, who holds their copyright. See the repository
[`LICENSE-DATA.md`](../../LICENSE-DATA.md) for the licence scope and suggested
attribution.
