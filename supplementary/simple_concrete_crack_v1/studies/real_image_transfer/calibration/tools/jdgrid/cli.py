from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .core import analyze


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Analyze JD Photo Data SL12-4 grid scans")
    p.add_argument("scans", nargs="+", type=Path, help="TIFF scan(s) to analyze")
    p.add_argument("--output-root", type=Path, default=Path("analysis"))
    p.add_argument("--dpi", type=float, help="override missing/incorrect TIFF DPI metadata")
    p.add_argument("--rotation-cw", type=int, choices=(0, 90, 180, 270), default=None,
                   help="override rotation inferred from the three hollow dots")
    return p


def main() -> int:
    args = parser().parse_args()
    failures = 0
    for scan in args.scans:
        output_dir = args.output_root / scan.stem
        try:
            result = analyze(scan, output_dir, args.dpi, args.rotation_cw)
            scale = result.metrics["calibrated_scale"]
            residual = result.metrics["affine_residual_um"]
            print(
                f"{scan}: {scale['x_um_per_px']:.6f} um/px X, "
                f"{scale['y_um_per_px']:.6f} um/px Y; "
                f"affine residual RMS {residual['rms_radial']:.3f} um -> {output_dir}"
            )
        except Exception as exc:
            failures += 1
            print(f"ERROR {scan}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
