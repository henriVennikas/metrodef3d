# Independent numerical reference-export verification

Study date: 7 November 2026. **This study found export defects. It is not an unconditional validation pass.** All checks, including unsuccessful ones, are retained. No generator, dataset, prediction CSV or model weight was changed.

## Scope and independence

The executed functions are the production Blender camera configuration and visible-reference JSON writer, frozen from the current generator. The dataset's archived seed-8532 script has the same numerical functions. Its only differences in the extracted code are added schema metadata. See `provenance.json` and `archive_source_diff.txt`. Blender 5.1.2 runs the functions without rendering. The sidecar is written and read back for comparison, so six-decimal export rounding is included. This tests prescribed planar geometry through the real export path. It does not establish agreement of rendered Boolean meshes with construction boundaries, validate every stochastic construction, or establish physical measurement traceability.

Expected results are calculated separately in `fixtures.py`: closed-form segment, trapezoid and annular-sector formulas, and double-precision convex intersections in the nominal world plane. The latter enumerates inside vertices and edge intersections and triangulates the resulting convex polygon; it does not call the production UV clipper. Camera footprint equations are derived for a square sensor, a camera tilted about the horizontal axis and zero roll. The independent oracle has eight known-answer tests. These tests are distinct from the production results below.

## Ordinary geometry and camera fixtures

65 fixtures cover constant and linearly varying width, rotation/translation, full and partial visibility, complete exclusion, orthographic and pinhole cameras, tilt 0–30 degrees, nominal FOV 50–150 mm, sampling and image resolution. Across them:

| Quantity | Maximum absolute discrepancy, ordinary fixtures | Cases exceeding predeclared criterion |
|---|---:|---:|
| centerline_length | 0.010034778 mm | 6 |
| mean_width | 0.000140599 mm | 0 |
| max_width | 0.000014000 mm | 0 |
| crack_area | 0.021100000 mm² | 2 |

Predeclared numerical criteria were 0.001 mm for length/width and 0.01 mm² for area. 7 distinct ordinary fixtures exceeded at least one criterion. These criteria were not relaxed after observing the results. They are numerical checks, not uncertainty budgets. The maximum discrepancies are small relative to these fixtures, but prevent a claim of six-decimal numerical accuracy from six-decimal storage alone. Production projection and ray calculations use Blender's finite-precision math objects and round reconstructed coordinates before summing lengths/areas. Finer sampling can increase accumulated round-trip length error; the 0.05 mm straight-line step gives the largest length discrepancy. This is not evidence of monotonically improving accuracy with denser stations.

## Sampling, resolution and tolerance

The circular-arc series uses radius 30 mm, width 2 mm and angle pi/2. For n chords, the exact discrete length is `2 R n sin(theta/(2n))` and the exact polygon area is `R w n sin(theta/n)`. Those discrete quantities are compared with the export. A separate smooth-arc comparison uses `R theta` and `R w theta`; its difference is discretization error, not an error in the definition of the polygon. From 8 to 512 chords, exported length error against the smooth arc decreases from 0.075659 to 0.000015 mm, and area error from 0.604452 to 0.000147 mm². This convergence applies to this prescribed smooth example, not arbitrary stochastic shapes.

Changing square image resolution from 256 to 4096 pixels leaves the four physical quantities unchanged for the selected camera/geometry. Replacing only the UV clipper's near-parallel denominator threshold in isolated in-memory copies with 1e-8, 1e-10, 1e-12 and 1e-14 also leaves that crossing fixture unchanged. Production source retains 1e-12. This sweep is a sensitivity diagnostic, not proof that all nearly tangent configurations are robust. Exact/near-boundary fixtures below expose additional limits.

## Disconnected visibility: confirmed defect

The exit/re-entry fixture has two visible arms. Their total analytical length is 115.175111 mm. The exporter returns 138.032242 mm because the visible stations are stored as one polyline and a 22.857131 mm connecting segment is counted across the clipped-out part. Mean width `area/length` is consequently affected. A correction must retain separate visible components, sum only actual visible segments, and define how component identity is represented in the sidecar. Do not silently relabel the existing release.

A read-only scan of all 10000 released sidecars found 142 source-profile gap candidates. Independent projection of original intermediate vertices confirmed out-of-frame bridges in 141: 92 training, 24 validation and 25 test observations. The confirmed artificial connections account for 0.213–65.798% of their recorded length (median 12.100%). These are percentages of recorded length, not percentages of corrected true length. One candidate remains unconfirmed. The audit deliberately ignores sub-percent adjacent-segment fraction gaps to avoid round-trip noise, so the count is not a proof that every other reference is correct.

`dataset_topology_audit.csv` and `.json` retain per-seed findings, saved-source indices, bridge lengths, a diagnostic bridge subtraction, independent whole-polyline clipping and camera-projection discrepancies. The subtraction is not a released replacement reference. Residual differences between the two calculations are retained and require resolution during correction. This audit confirms the mechanism in existing data but does not regenerate or certify all four measurands for the full dataset.

## Boundary-only visibility: confirmed defect

For a nonzero visible opening whose centreline is wholly outside the image, the exporter marks the polygon as visible and then calls `max()` on an empty width profile. Three stress cases raise this exception, including nominal tangency perturbed by finite-precision projection. The data structure needs an explicit convention for area without a visible centreline. The existing released sidecars cannot establish how many attempted generations failed in this way.

For a centreline retained at the boundary, polygon area can be clipped while construction-normal maximum width remains the width of the retained station. This is a definition distinction, not necessarily an arithmetic defect. For the lateral-clipping strip, mean width is 1.5 mm from area/length and construction maximum width remains 2 mm. A boundary-derived local opening would describe a different measurand.

## Interpretation and follow-up

This validation study records the numerical discrepancies and clipping defects without replacing the released v1 references or recomputing model rankings. The subsequent [reference-correction study](../reference_correction/README.md) documents the versioned correction overlay and its effects on benchmark results and validation calibration. The reference-mask diagnostic from the conventional benchmark is separate and cannot validate these construction references.

## Files and reproduction

- `production_export.py`: unmodified extracted production functions, with imports/schema constants for execution.
- `fixtures.py`, `fixtures.json`, `test_oracles.py`: independent calculations, all fixtures and known-answer tests.
- `run_blender.py`: actual writer execution and isolated tolerance sensitivity.
- `results/`: written sidecars and all run outcomes, including exceptions.
- `discrepancies.csv`, `summary.json`: every comparison and aggregate statistics.
- `audit_dataset.py`, `dataset_topology_audit.*`: read-only release audit.
- `diagnostics.png`: numerical convergence and the disconnected fixture.
- `protocol.json`, `provenance.json`, `checksums.json`: scope, criteria and provenance.

Commands and dependencies are in `README.md`. No publication has been performed by the study scripts.
