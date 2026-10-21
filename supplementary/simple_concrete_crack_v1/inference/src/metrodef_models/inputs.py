"""Explicit RGB/physical-scale input contracts and portable generator sidecars."""
from pathlib import Path, PurePosixPath
import json
import numpy as np
from PIL import Image
import torch


def image_input(image_path, size=1024, scale_path=None, mm_per_pixel=None, scale_grid='original'):
    if (scale_path is None) == (mm_per_pixel is None):
        raise ValueError('Supply exactly one of a scale NPZ or mm/pixel')
    with Image.open(image_path) as im:
        if im.getexif().get(274, 1) != 1:
            raise ValueError('Apply EXIF orientation to image and scale together before inference')
        width, height = im.size
        rgb = np.asarray(im.convert('RGB').resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32) / 255.
    if scale_grid not in ['original', 'model']:
        raise ValueError('scale_grid must be original or model')
    shape = (height, width) if scale_grid == 'original' else (size, size)
    if scale_path is not None:
        with np.load(scale_path, allow_pickle=False) as data:
            sx = np.asarray(data['scale_x_mm_per_px'], dtype=np.float32)
            sy = np.asarray(data['scale_y_mm_per_px'], dtype=np.float32)
            if 'valid_surface' in data and not np.all(data['valid_surface']):
                raise ValueError('Scale contains invalid surface pixels')
        if sx.shape != shape or sy.shape != shape:
            raise ValueError(f'Scale arrays must match declared grid {shape}, got {sx.shape}, {sy.shape}')
    else:
        sx = np.full(shape, mm_per_pixel, dtype=np.float32)
        sy = sx.copy()
    if not np.isfinite(sx).all() or not np.isfinite(sy).all() or np.any(sx <= 0) or np.any(sy <= 0):
        raise ValueError('Physical scales must be finite and strictly positive')
    if scale_grid == 'original':
        sx = np.asarray(Image.fromarray(sx).resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32) * (width / size)
        sy = np.asarray(Image.fromarray(sy).resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32) * (height / size)
    average = np.sqrt(sx * sy).astype(np.float32)
    values = np.concatenate([rgb.transpose(2, 0, 1), average[None]], axis=0)
    return torch.from_numpy(values.copy()).unsqueeze(0)


def resolve_sidecar(metadata, recorded):
    """Rebase a recorded generator path under this run, never an old host path."""
    root = Path(metadata).resolve().parent.parent
    parts = PurePosixPath(recorded).parts
    # Original and current generator both record the run name before img/json/etc.
    matches = [i for i, part in enumerate(parts) if part == root.name]
    if matches:
        candidate = root.joinpath(*parts[matches[-1]+1:]).resolve()
    elif not PurePosixPath(recorded).is_absolute():
        candidate = root.joinpath(*parts).resolve()
    else:
        candidate = None
    if candidate is not None and candidate.is_relative_to(root) and candidate.is_file():
        return candidate
    # A user may rename a run directory after extraction. Anchor only known
    # sidecar directories, preserving any capture subdirectory below them.
    alternatives = set()
    for i, part in enumerate(parts):
        if part in {'img', 'pixel_scale', 'visible_defect'}:
            path = root.joinpath(*parts[i:]).resolve()
            if path.is_relative_to(root) and path.is_file():
                alternatives.add(path)
    if len(alternatives) != 1:
        raise ValueError(f'Missing, ambiguous or out-of-run sidecar: {recorded}')
    return alternatives.pop()


def generated_input(metadata, size=1024, stream='perspective-area'):
    d = json.loads(Path(metadata).read_text())
    captures = [c for c in d['outputs']['captures'] if c['capture_id'] == stream]
    if len(captures) != 1:
        raise ValueError(f'Expected exactly one capture named {stream}')
    cap = captures[0]
    image = resolve_sidecar(metadata, cap['image'])
    scale = resolve_sidecar(metadata, cap['pixel_scale_sidecar'])
    visible = json.loads(resolve_sidecar(metadata, cap['visible_defect_sidecar']).read_text())
    values = image_input(image, size, scale_path=scale, scale_grid='original')
    return values, visible['measurands'], image


def metadata_index(root):
    paths = sorted(Path(root).glob('**/json/*.json'))
    index = {}
    for p in paths:
        if not p.stem.isdigit():
            continue
        seed = int(p.stem)
        if seed in index:
            raise ValueError(f'Ambiguous seed {seed}; provide one dataset/run root')
        index[seed] = p
    return index
