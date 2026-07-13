# metrodef3d Agent Guide

## Project Mission

metrodef3d is a greenfield dataset generator for metrologically grounded
surface defect data. Its purpose is to create stochastic surface defects whose
measurands are known by construction, so any generated sample can be repeated,
inspected, and used as ground truth for vision, metrology, and defect-detection
experiments.

The project builds on the idea behind the original `metrodef` repository, but it
must not copy that implementation. Treat `henriVennikas/metrodef` as conceptual
reference only: useful for intent, terminology, and lessons learned, not as a
codebase to port.

The major new capability in metrodef3d is Blender-backed 3D rendering. Defects
should be constructed on known 3D surfaces and rendered under configurable
camera, pose, field-of-view, material, and illumination conditions.

## V1 Target

The first working milestone is an end-to-end cracked surface sample:

- Read a YAML scene recipe.
- Generate a known 3D surface.
- Construct one stochastic crack on that surface with seeded randomness.
- Render the scene headlessly with Blender.
- Export a rendered image.
- Export JSON metadata containing the seed, scene parameters, camera,
  illumination, material, defect construction parameters, known measurands, and
  output paths.

V1 should prove the full pipeline before expanding the defect taxonomy. Masks,
depth maps, mesh exports, geometry bundles, and richer annotation products are
important later extensions, but they are not required for the first proof.

## Default Architecture

Use a Python package plus CLI as the default project shape.

The CLI should be planned around commands like:

```sh
metrodef3d generate --config scene.yaml --out runs/example
metrodef3d validate --config scene.yaml
```

YAML scene recipes are the stable user-facing experiment interface. They should
describe at least:

- Seed and run identity.
- Surface geometry.
- Defect type and construction parameters.
- Camera model, pose, resolution, and field of view.
- Lighting and illumination variation.
- Material and render settings.
- Export settings.

Keep the internal design separated by responsibility:

- Geometry construction: deterministic construction of surfaces and defects from
  validated parameters and seeded randomness.
- Scene assembly: conversion of constructed geometry into a Blender scene.
- Rendering: headless Blender execution and render configuration.
- Export: images, metadata, and later annotation products.
- Validation: recipe checks and clear error reporting before expensive rendering.

## Design Principles

- Treat defects as measurable geometry first and visual appearance second.
- Make every stochastic choice reproducible from explicit seeds.
- Preserve construction truth in metadata instead of trying to recover truth from
  rendered pixels.
- Prefer small, composable generators over monolithic scene scripts.
- Keep Blender-specific code behind a narrow integration boundary where possible.
- Make invalid configurations fail early with clear messages.
- Avoid hidden global state in random generation, rendering settings, and output
  paths.
- Keep examples minimal but complete enough to run end to end.

## V1 Crack Definition

The first defect family is cracks. A crack generator should expose
construction-defined parameters such as:

- Surface placement.
- Crack path or centerline.
- Length.
- Width model.
- Depth or profile model.
- Branching model, if enabled.
- Path noise or roughness model.
- Seed values or sub-seeds used to derive stochastic variation.

The rendered crack may use materials, displacement, beveling, or geometry
operations as needed, but the exported metadata must preserve the construction
values that define the intended measurands.

Do not allow the v1 crack to become only a visual texture. Its geometric
definition is the source of truth.

## Outputs

Each generated v1 sample should write an output directory containing:

- A rendered image.
- A JSON metadata file.

The JSON metadata should include:

- Generator version or commit identity when available.
- Input recipe path or embedded resolved recipe.
- Seed and derived seed information.
- Surface parameters.
- Crack construction parameters and measurands.
- Camera parameters.
- Lighting parameters.
- Material parameters.
- Render settings.
- Relative or absolute output paths.

Later output products may include segmentation masks, depth maps, normal maps,
mesh files, curve files, and complete geometry packages.

## Testing Expectations

Future implementation work should add focused tests as the corresponding
behavior appears:

- Determinism test: the same config and seed produce identical metadata and
  stable geometry parameters.
- CLI smoke test: a minimal YAML recipe generates a valid output directory.
- Blender smoke test: a headless render completes and writes a non-empty image.
- Metadata test: exported JSON contains all required construction measurands for
  the crack.
- Validation test: invalid recipes fail with clear, actionable errors.

Blender-dependent tests may be marked or separated so quick unit tests remain
usable without launching Blender.

## Development Notes For Agents

- Start with the smallest end-to-end slice that proves the pipeline.
- Prefer implementation choices that keep measurands explicit and inspectable.
- Do not introduce broad abstractions before there are multiple concrete
  generators or render paths that need them.
- Do not copy files or algorithms from the old `metrodef` repository. If a
  concept is reused, re-express it deliberately in metrodef3d's architecture.
- Keep repo changes scoped. If adding code, include the minimal example recipe
  and tests needed to demonstrate the behavior.
- When editing user-facing interfaces, update examples and validation behavior
  together.
