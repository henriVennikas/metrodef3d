# metrodef3d Agent Guide

This repository contains a dataset generator. When assisting someone who has
pulled metrodef3d, prioritize helping them run, configure, inspect, and adapt
the generator for their own experiments. Treat the codebase as usable software
first and a development project second.

## What metrodef3d Does

metrodef3d generates synthetic cracked-surface datasets with ground truth known
by construction. A YAML recipe defines the surface, crack construction, camera,
lighting, material, render settings, and export layout. The CLI validates the
recipe, constructs deterministic geometry from explicit seeds, optionally
renders with Blender, and writes machine-readable metadata beside the images.

The core rule is simple: truth comes from construction metadata, not from
post-hoc image analysis. Do not suggest re-estimating crack length, width, or
area from rendered pixels when the metadata already provides those values.

## Typical User Goals

Help users do these things quickly:

- Validate an example or custom YAML recipe.
- Generate one sample, a small batch, or a larger seeded run.
- Switch between the lightweight preview backend and Blender rendering.
- Change seed range, output directory, camera, resolution, field of view,
  lighting, material, or crack parameters.
- Locate images, JSON metadata, visible-defect truth, pixel-scale sidecars,
  blend files, and YAML copies in a generated run.
- Filter generated datasets using quality manifests when available.
- Understand which metadata fields should be used as ML training targets.

## First Commands To Try

Use the package directly from the source tree unless the user has installed it:

```sh
PYTHONPATH=src python3 -m metrodef3d validate --config examples/cracked_plane.yaml
PYTHONPATH=src python3 -m metrodef3d generate --config examples/cracked_plane.yaml --out runs/example
```

For Blender-backed rendering:

```sh
PYTHONPATH=src python3 -m metrodef3d validate --config examples/cracked_plane_blender.yaml
PYTHONPATH=src python3 -m metrodef3d generate --config examples/cracked_plane_blender.yaml --out runs/blender-example
```

For a small batch:

```sh
PYTHONPATH=src python3 -m metrodef3d generate \
  --config examples/cracked_plane_blender.yaml \
  --out runs/blender-variance \
  --count 10
```

If Blender is not found, ask the user where Blender is installed and set
`render.executable` in the YAML recipe.

## Recipe Guidance

YAML recipes are the main user-facing interface. Prefer changing recipes over
editing Python when the user wants different generated data.

Common fields users may want to adjust:

- `run.seed` or CLI seed/count settings for reproducible variation.
- `render.backend`: use `preview` for quick smoke tests, `blender` for 3D
  rendered images.
- `render.image_format`, resolution, quality, and Blender executable path.
- `surface` dimensions and units.
- `defect` construction model, width range, length, depth/profile, skeleton
  step, random-walk behavior, and variation fields.
- `captures[*].camera` for perspective or orthographic outputs.
- `captures[*].lighting` for illumination setup.
- `material` for surface appearance and shader/noise parameters.

Keep one Blender unit interpreted as one millimeter unless the recipe clearly
states otherwise.

## Output Layout

Generated runs are usually written under `runs/`, which is ignored by git.
Depending on the recipe, a run may contain:

```text
img/<capture_id>/<seed>.jpg
json/<seed>.json
visible_defect/<capture_id>/<seed>.json
pixel_scale/<capture_id>/<seed>.npz
blend/<seed>.blend
yaml/<seed>.yaml
blender_script/<seed>.py
blender_script/chunks/<first_seed>_<last_seed>.py
```

Use `json/<seed>.json` as the canonical sample entry. For per-image scalar
targets, use `outputs.captures[*].visible_defect.measurands`. For a sidecar-only
workflow, use `visible_defect/<capture_id>/<seed>.json`.

## Ground Truth Use

The preferred V1 metrology path is the `ribbon_fbm_width` crack construction
model. Its skeleton and width profile define the truth boundaries directly, so
length, local width, area, and station profiles are construction-defined.

When using perspective captures, use the per-capture visible-defect metadata.
The visible truth may differ between captures because field of view, pose, and
projection can clip different portions of the same constructed defect.

If pixel-scale sidecars are present, use them as geometric context for a
perspective image:

- `scale_x_mm_per_px.npy`: horizontal nominal-surface scale per pixel.
- `scale_y_mm_per_px.npy`: vertical nominal-surface scale per pixel.

Do not assume one global mm/px value for perspective images when per-pixel scale
maps are available.

## Dataset Quality

Some generated datasets may include a `quality_manifest.json`. If present,
respect it. Samples with `exclude_from_training: true` should be skipped for
training and evaluation unless the user explicitly wants to audit failures.

Do not delete corrupt samples by default. They are useful for auditability and
for improving generation/quality-control checks.

## Tools In This Repo

Useful helper scripts:

- `tools/write_dataset_overview.py`: write a README and machine-readable
  dataset summary for a generated run.
- `tools/write_overlay_viewer.py`: create a browser viewer that overlays
  visible-defect truth and pixel-scale maps on generated images.
- `tools/scan_run_quality.py`: scan a run for coarse render/geometry quality
  risks.
- `tools/train_scalar_baseline.py`: train a small CNN sanity-check regressor
  from images to construction measurands.

Prefer these tools when the user asks to inspect or summarize generated data.

## Safe Defaults

- Keep generated data under `runs/` or another explicit output directory.
- Do not commit generated renders, `.blend` batches, model checkpoints, or
  large datasets to git unless the user explicitly asks.
- Preserve seeds and copied YAML recipes so runs are reproducible.
- When changing recipes, validate before launching expensive Blender batches.
- For public sharing, keep the repository focused on code, examples, tools, and
  documentation; publish generated datasets separately with manifests and
  checksums.

## When Code Changes Are Needed

If the user asks to modify the generator itself, keep changes scoped and preserve
the construction-truth principle. Update examples and validation behavior when
changing user-facing recipe fields. Run the lightweight preview smoke path before
attempting expensive Blender work.
