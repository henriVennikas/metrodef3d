#!/usr/bin/env python3
"""Train a small image-to-measurand baseline on a metrodef3d run directory."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset


DEFAULT_TARGETS = ("centerline_length", "mean_width", "max_width", "crack_area")


@dataclass(frozen=True)
class Sample:
    seed: int
    image_path: Path
    targets: Tuple[float, ...]


class CrackScalarDataset(Dataset):
    def __init__(
        self,
        samples: Sequence[Sample],
        image_size: int,
        target_mean: np.ndarray,
        target_std: np.ndarray,
    ) -> None:
        self.samples = list(samples)
        self.image_size = image_size
        self.target_mean = target_mean.astype(np.float32)
        self.target_std = np.maximum(target_std.astype(np.float32), 1.0e-6)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        sample = self.samples[index]
        with Image.open(sample.image_path) as image:
            image = image.convert("RGB")
            image = image.resize((self.image_size, self.image_size), Image.Resampling.BILINEAR)
            array = np.asarray(image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1)
        targets = np.asarray(sample.targets, dtype=np.float32)
        normalized = (targets - self.target_mean) / self.target_std
        return tensor, torch.from_numpy(normalized), torch.from_numpy(targets), sample.seed


class SmallCnnRegressor(nn.Module):
    def __init__(self, outputs: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            _conv_block(3, 32),
            _conv_block(32, 64),
            _conv_block(64, 128),
            _conv_block(128, 192),
            _conv_block(192, 256),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256, 192),
            nn.ReLU(inplace=True),
            nn.Dropout(0.15),
            nn.Linear(192, outputs),
        )

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(image))


def _conv_block(in_channels: int, out_channels: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(kernel_size=2),
    )


def main() -> int:
    args = parse_args()
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    run_dir = args.run_dir.resolve()
    samples = load_samples(run_dir, args.capture_id, args.targets)
    if args.max_samples:
        samples = samples[: args.max_samples]
    if len(samples) < 10:
        raise SystemExit("Need at least 10 samples for a useful train/validation split.")

    train_samples, val_samples = split_by_seed(samples, args.val_fraction, args.seed)
    train_targets = np.asarray([sample.targets for sample in train_samples], dtype=np.float32)
    target_mean = train_targets.mean(axis=0)
    target_std = train_targets.std(axis=0)

    train_loader = DataLoader(
        CrackScalarDataset(train_samples, args.image_size, target_mean, target_std),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        CrackScalarDataset(val_samples, args.image_size, target_mean, target_std),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = SmallCnnRegressor(len(args.targets)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs, 1))
    criterion = nn.SmoothL1Loss()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = out_dir / "history.csv"
    best_path = out_dir / "best_model.pt"
    summary_path = out_dir / "summary.json"

    best_score = math.inf
    history_rows = []
    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        metrics = evaluate(model, val_loader, device, target_mean, target_std, args.targets)
        scheduler.step()
        row = {"epoch": epoch, "train_loss": train_loss, **flatten_metrics(metrics)}
        history_rows.append(row)
        score = float(metrics["mean"]["mae"])
        print(
            f"epoch {epoch:03d} train_loss={train_loss:.5f} "
            f"val_mae_mean={score:.5f} val_r2_mean={metrics['mean']['r2']:.4f}",
            flush=True,
        )
        if score < best_score:
            best_score = score
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "targets": list(args.targets),
                    "target_mean": target_mean.tolist(),
                    "target_std": target_std.tolist(),
                    "image_size": args.image_size,
                    "capture_id": args.capture_id,
                },
                best_path,
            )

    write_history(history_path, history_rows)
    final_metrics = evaluate(model, val_loader, device, target_mean, target_std, args.targets)
    summary = {
        "run_dir": str(run_dir),
        "capture_id": args.capture_id,
        "targets": list(args.targets),
        "device": str(device),
        "image_size": args.image_size,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "target_mean": target_mean.tolist(),
        "target_std": target_std.tolist(),
        "best_mean_mae": best_score,
        "final_metrics": final_metrics,
        "outputs": {
            "history": str(history_path),
            "best_model": str(best_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--capture-id", default="perspective-area")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--targets", nargs="+", default=list(DEFAULT_TARGETS))
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2.0e-4)
    parser.add_argument("--weight-decay", type=float, default=1.0e-4)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260701)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def load_samples(run_dir: Path, capture_id: str, targets: Sequence[str]) -> List[Sample]:
    repo_root = run_dir.parents[1] if run_dir.name and run_dir.parent.name == "runs" else Path.cwd()
    samples = []
    for json_path in sorted((run_dir / "json").glob("*.json"), key=lambda path: int(path.stem)):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        seed = int(data["run"]["seed"])
        capture = next(
            (entry for entry in data["outputs"]["captures"] if entry.get("capture_id") == capture_id),
            None,
        )
        if capture is None:
            continue
        image_path = resolve_output_path(repo_root, run_dir, capture["image"])
        measurands = capture["visible_defect"]["measurands"]
        values = tuple(float(measurands[target]) for target in targets)
        samples.append(Sample(seed=seed, image_path=image_path, targets=values))
    return samples


def resolve_output_path(repo_root: Path, run_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    repo_path = repo_root / path
    if repo_path.exists():
        return repo_path
    return run_dir / path


def split_by_seed(samples: Sequence[Sample], val_fraction: float, seed: int) -> Tuple[List[Sample], List[Sample]]:
    ordered = list(samples)
    rng = random.Random(seed)
    rng.shuffle(ordered)
    val_count = max(1, int(round(len(ordered) * val_fraction)))
    val_set = {sample.seed for sample in ordered[:val_count]}
    train_samples = [sample for sample in samples if sample.seed not in val_set]
    val_samples = [sample for sample in samples if sample.seed in val_set]
    return train_samples, val_samples


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total = 0.0
    count = 0
    for images, normalized_targets, _raw_targets, _seeds in loader:
        images = images.to(device, non_blocking=True)
        normalized_targets = normalized_targets.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        predictions = model(images)
        loss = criterion(predictions, normalized_targets)
        loss.backward()
        optimizer.step()
        batch = images.shape[0]
        total += float(loss.item()) * batch
        count += batch
    return total / max(count, 1)


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    target_mean: np.ndarray,
    target_std: np.ndarray,
    target_names: Sequence[str],
) -> Dict[str, Dict[str, float]]:
    model.eval()
    predictions = []
    targets = []
    mean = torch.as_tensor(target_mean, dtype=torch.float32, device=device)
    std = torch.as_tensor(target_std, dtype=torch.float32, device=device)
    for images, _normalized_targets, raw_targets, _seeds in loader:
        images = images.to(device, non_blocking=True)
        pred = model(images) * std + mean
        predictions.append(pred.cpu().numpy())
        targets.append(raw_targets.numpy())
    pred_array = np.concatenate(predictions, axis=0)
    target_array = np.concatenate(targets, axis=0)
    metrics: Dict[str, Dict[str, float]] = {}
    maes = []
    rmses = []
    r2s = []
    for index, name in enumerate(target_names):
        error = pred_array[:, index] - target_array[:, index]
        mae = float(np.mean(np.abs(error)))
        rmse = float(np.sqrt(np.mean(error**2)))
        variance = float(np.sum((target_array[:, index] - np.mean(target_array[:, index])) ** 2))
        residual = float(np.sum(error**2))
        r2 = 1.0 - residual / variance if variance > 0 else 0.0
        metrics[name] = {"mae": mae, "rmse": rmse, "r2": r2}
        maes.append(mae)
        rmses.append(rmse)
        r2s.append(r2)
    metrics["mean"] = {
        "mae": float(np.mean(maes)),
        "rmse": float(np.mean(rmses)),
        "r2": float(np.mean(r2s)),
    }
    return metrics


def flatten_metrics(metrics: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    flat = {}
    for target, values in metrics.items():
        for metric, value in values.items():
            flat[f"{target}_{metric}"] = float(value)
    return flat


def write_history(path: Path, rows: Sequence[Dict[str, float]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
