import argparse
import sys
from pathlib import Path

from .errors import Metrodef3dError
from .pipeline import generate, generate_many_blender_parallel
from .recipe import load_recipe


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="metrodef3d")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a YAML scene recipe.")
    validate_parser.add_argument("--config", required=True, type=Path)

    generate_parser = subparsers.add_parser("generate", help="Generate a cracked surface sample.")
    generate_parser.add_argument("--config", required=True, type=Path)
    generate_parser.add_argument("--out", required=True, type=Path)
    generate_parser.add_argument("--count", type=int, default=1, help="Number of seed variants to generate.")
    generate_parser.add_argument("--seed-step", type=int, default=1, help="Seed increment between variants.")
    generate_parser.add_argument(
        "--blender-batch-size",
        type=int,
        default=1,
        help="Number of Blender seeds to render per Blender process for Blender backend runs.",
    )
    generate_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel worker processes for Blender backend runs.",
    )

    args = parser.parse_args(argv)
    try:
        recipe = load_recipe(args.config)
        if args.command == "validate":
            print("Recipe is valid: " + str(args.config))
            return 0
        if args.command == "generate":
            if args.count == 1:
                image_path, metadata_path = generate(recipe, args.out)
                print("Wrote image: " + str(image_path))
                print("Wrote metadata: " + str(metadata_path))
            else:
                results = generate_many_blender_parallel(
                    recipe,
                    args.out,
                    args.count,
                    args.seed_step,
                    args.blender_batch_size,
                    args.workers,
                )
                for image_path, metadata_path in results:
                    print("Wrote image: " + str(image_path))
                    print("Wrote metadata: " + str(metadata_path))
            return 0
    except Metrodef3dError as exc:
        print("metrodef3d: " + str(exc), file=sys.stderr)
        return 2
    return 1
