"""Frozen MetroDef3D scalar and interval inference. No training or fitting."""
from pathlib import Path
from contextlib import nullcontext
import hashlib
import json
import numpy as np
import torch
from .model import ScalarSegmentationTransformer
from .benchmark_models import ScalarSegmentationCNN


def build_model(config):
    keys = ['image_size', 'in_channels', 'embed_dim', 'dropout', 'min_delta',
            'interval_mode', 'segmentation_head']
    kwargs = {k: config[k] for k in keys}
    kwargs['num_targets'] = len(config['targets'])
    if config['model'] == 'ScalarSegmentationTransformer':
        kwargs.update({k: config[k] for k in ['token_stride', 'depth', 'num_heads', 'mlp_ratio']})
        return ScalarSegmentationTransformer(**kwargs)
    if config['model'] == 'ScalarSegmentationCNN':
        return ScalarSegmentationCNN(backbone=config['backbone'], **kwargs)
    raise ValueError('Unknown model architecture')


class Predictor:
    def __init__(self, model_dir, device='cpu', precision='float32', dense=False):
        root = Path(model_dir)
        self.config = json.loads((root / 'config.json').read_text())
        self.split = json.loads((root / 'split_seeds.json').read_text())
        weights = root / 'weights.pt'
        if hashlib.sha256(weights.read_bytes()).hexdigest() != self.config['weights_sha256']:
            raise ValueError('Checkpoint SHA-256 mismatch')
        self.device = torch.device(device)
        if precision not in ['float32', 'bfloat16']:
            raise ValueError('Unknown precision')
        if precision == 'bfloat16' and self.device.type != 'cuda':
            raise ValueError('Benchmark bfloat16 policy requires CUDA')
        self.precision = precision
        self.model = build_model(self.config)
        self.model.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True), strict=True)
        self.model.to(self.device).eval()
        self.model.has_segmentation_head = dense
        if self.config['batchnorm_policy'] == 'per_image':
            for module in self.model.modules():
                if isinstance(module, torch.nn.BatchNorm2d):
                    module.train(True)
                    module.track_running_stats = False
        self.dense = dense

    def membership(self, seed):
        for part, seeds in self.split.items():
            if seed in seeds:
                return part
        return 'excluded' if seed in self.config['exclude_seeds'] else 'outside_frozen_split'

    @torch.inference_mode()
    def predict(self, inputs):
        size = self.config['image_size']
        if tuple(inputs.shape) != (1, 4, size, size):
            raise ValueError(f'Expected batch one [1,4,{size},{size}]')
        if not torch.isfinite(inputs).all() or (inputs[:, 3] <= 0).any():
            raise ValueError('Input and scale must be finite, with strictly positive scale')
        if (inputs[:, :3] < 0).any() or (inputs[:, :3] > 1).any():
            raise ValueError('RGB must lie in [0,1]')
        ctx = torch.autocast('cuda', dtype=torch.bfloat16) if self.precision == 'bfloat16' else nullcontext()
        with ctx:
            outputs = self.model(inputs.to(self.device))
        raw = outputs['interval'].detach().cpu().float().numpy()[0]
        # Preserve the original float32 denormalisation order.
        mean = np.asarray(self.config['target_mean'], dtype=np.float32)
        std = np.asarray(self.config['target_std'], dtype=np.float32)
        mu = raw[:, 0] * std + mean
        lower = (raw[:, 0] - raw[:, 1]) * std + mean
        upper = (raw[:, 0] + raw[:, 2]) * std + mean
        result = {}
        for i, target in enumerate(self.config['targets']):
            m, l, u = map(float, (mu[i], lower[i], upper[i]))
            factor = self.config['interval_scales'][target]
            result[target] = dict(mu=m, lower=l, upper=u,
                calibrated_lower=m-(m-l)*factor, calibrated_upper=m+(u-m)*factor,
                unit='mm2' if target == 'crack_area' else 'mm')
        dense = {k: v.detach().cpu().float().numpy()[0] for k, v in outputs.items() if k != 'interval'}
        return result, dense
