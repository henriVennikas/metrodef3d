"""Portable release workflows; never fits calibration or trains a model."""
import argparse
import csv
import json
import platform
import time
from pathlib import Path
import numpy as np
import torch
from .engine import Predictor
from .inputs import generated_input, image_input, metadata_index
from .evaluation import metrics


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir', type=Path, required=True)
    p.add_argument('--device', choices=['cpu','mps','cuda'], default='cpu')
    p.add_argument('--precision', choices=['float32','bfloat16'], default='float32')
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--output', type=Path, required=True, help='New output directory (must not exist)')
    sub = p.add_subparsers(dest='command', required=True)
    b = sub.add_parser('benchmark')
    b.add_argument('--dataset', type=Path, required=True)
    b.add_argument('--limit', type=int, help='Smoke test only; not full benchmark reproduction')
    g = sub.add_parser('generated')
    g.add_argument('--metadata', type=Path, required=True)
    g.add_argument('--stream', default='perspective-area')
    g.add_argument('--dense', action='store_true')
    i = sub.add_parser('image')
    i.add_argument('--image', type=Path, required=True)
    group = i.add_mutually_exclusive_group(required=True)
    group.add_argument('--scale', type=Path)
    group.add_argument('--mm-per-pixel', type=float)
    i.add_argument('--scale-grid', choices=['original','model'], default='original')
    i.add_argument('--dense', action='store_true')
    args = p.parse_args()
    if args.command == 'benchmark' and args.limit is not None and args.limit <= 0:
        p.error('--limit must be positive')
    if args.threads <= 0:
        p.error('--threads must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.threads)
    predictor = Predictor(args.model_dir,args.device,args.precision,getattr(args,'dense',False))
    env = dict(python=platform.python_version(), torch=torch.__version__, platform=platform.platform(),
               device=args.device, precision=args.precision, threads=args.threads,
               model_id=predictor.config['model_id'], weights_sha256=predictor.config['weights_sha256'])
    dump(args.output/'environment.json',env)
    start = time.monotonic()
    size = predictor.config['image_size']
    if args.command == 'benchmark':
        index = metadata_index(args.dataset)
        seeds = sorted(predictor.split['test'])
        if args.limit:
            seeds = seeds[:args.limit]
        missing = set(seeds)-index.keys()
        if missing:
            raise ValueError(f'Missing test metadata for {sorted(missing)}')
        rows = []
        with (args.output/'predictions.csv').open('w',newline='') as handle:
            writer = None
            for count, seed in enumerate(seeds,1):
                inputs, reference, _ = generated_input(index[seed],size)
                values, _ = predictor.predict(inputs)
                row = {'seed':seed,'stream':'perspective-area'}
                for t, v in values.items():
                    row[t+'_actual'] = float(np.float32(reference[t]))
                    row.update({t+'_'+k:v[k] for k in ['mu','lower','upper','calibrated_lower','calibrated_upper']})
                if writer is None:
                    writer=csv.DictWriter(handle,fieldnames=list(row));writer.writeheader()
                writer.writerow(row);handle.flush();rows.append(row)
                if count % 25 == 0 or count == len(seeds):
                    progress=dict(completed=count,total=len(seeds),elapsed_seconds=time.monotonic()-start)
                    dump(args.output/'progress.json',progress);print(json.dumps(progress),flush=True)
        dump(args.output/'metrics.json',metrics(rows,predictor.config))
        dump(args.output/'status.json',dict(status='complete',full_test_partition=len(seeds)==len(predictor.split['test']),
             samples=len(seeds),elapsed_seconds=time.monotonic()-start))
    else:
        if args.command == 'generated':
            inputs, reference, _ = generated_input(args.metadata,size,args.stream)
            seed=int(args.metadata.stem)
            context=dict(seed=seed,seed_membership=predictor.membership(seed),reference=reference)
        else:
            inputs=image_input(args.image,size,args.scale,args.mm_per_pixel,args.scale_grid)
            context=dict(image=args.image.name,scale_grid=args.scale_grid,
                scale_source=args.scale.name if args.scale else args.mm_per_pixel,
                note='Exploratory inference. Synthetic calibration does not establish coverage on real images. Bounds exclude scale and annotation uncertainty.')
        predictions,dense=predictor.predict(inputs)
        dump(args.output/'predictions.json',dict(context=context,predictions=predictions,elapsed_seconds=time.monotonic()-start))
        if dense:
            np.savez_compressed(args.output/'dense.npz',**dense)


if __name__ == '__main__':
    main()
