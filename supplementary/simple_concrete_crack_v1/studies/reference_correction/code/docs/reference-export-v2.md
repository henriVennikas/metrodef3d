# Visible-reference export revision 2

Local generator version 0.1.1 writes visible-defect schema version 2. This corrects component handling when a centreline leaves and re-enters the camera frame. It does not change crack construction, camera settings, images or pixel-scale arrays.

## Components

`component_ranges` is a list of half-open `[start, stop]` index ranges into the flattened centreline, boundary, pixel-coordinate, width/depth-profile and source-profile arrays. Length is the sum of the polyline lengths **within** each range. Never connect the end of one range to the start of another. The overlay viewer follows these ranges. Original schema-1 files can still be displayed as their historical single polyline, but must not be treated as corrected data.

`reference_export_revision` is `component-aware-2`. The flat arrays remain available for alignment and inspection; the component ranges are required for connectivity. Counts and schema metadata are not physical measurands.

## Undefined quantities

A polygon can remain visible even when no centreline station is visible. Its area and zero visible-centreline length are retained. Mean width is undefined when the visible length is zero. Maximum width and depth are undefined without retained profile stations. These values are JSON `null`, accompanied by false entries in `measurand_validity`. Consumers must reject or explicitly handle an undefined quantity; do not convert it to zero. A fully empty observation still has defined zero quantities. A tangential station can have defined profile extrema but undefined mean width.

The Blender path computes area from the clipped polygon and uses the construction-normal width profile for maximum width. Lateral clipping therefore does not redefine maximum width as a boundary-derived opening. The preview fallback retains its historical integrated-profile area convention, now summed component by component. It is not a replacement for Blender-generated polygon references. This patch also makes an absent boundary polygon return an empty world/pixel pair consistently.

## Numerical scope and migration

Projection, UV clipping, reconstruction, six-decimal rounding and polygon-area arithmetic are unchanged. The previously measured small numerical discrepancies remain documented. This fix addresses connectivity and undefined-profile handling, not all numerical conditioning or geometry/render consistency.

Original datasets are immutable. The [local correction study](../supplementary/simple_concrete_crack_v1/studies/reference_correction/README.md) provides separately written corrected sidecars, original hashes, old/new quantities and benchmark impact. The [earlier verification](../supplementary/simple_concrete_crack_v1/studies/reference_validation/README.md) remains a dated record of the uncorrected behavior. No model retraining or public release is implied by this code change.
