"""Torchvision backbones adapted to the MetroDef scalar/interval contract.

No pretrained weights or ImageNet preprocessing are used. Both CNNs retain
their native stride-32 backbone. A learned projection and interpolation give
the auxiliary head the same stride-16 grid as the manuscript transformer.
"""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from .model import ResidualConvBlock


class ScalarSegmentationCNN(nn.Module):
    def __init__(
        self, backbone: str, image_size: int, in_channels: int, num_targets: int,
        embed_dim: int = 384, dropout: float = 0.1,
        min_delta: float = 1e-4, interval_mode: str = "asymmetric",
        segmentation_head: bool = True,
    ) -> None:
        super().__init__()
        if backbone not in {"resnet50", "convnext_tiny"}:
            raise ValueError(f"Unsupported CNN backbone: {backbone}")
        if image_size < 32 or image_size % 32:
            raise ValueError("CNN image_size must be at least 32 and divisible by 32.")
        if embed_dim < 16 or embed_dim % 16:
            raise ValueError("embed_dim must be a positive multiple of 16.")
        if interval_mode not in {"asymmetric", "symmetric"}:
            raise ValueError("Unknown interval mode.")
        from torchvision.models import convnext_tiny, resnet50

        self.backbone_name = backbone
        self.image_size = image_size
        self.num_targets = num_targets
        self.min_delta = min_delta
        self.interval_mode = interval_mode
        self.has_segmentation_head = segmentation_head
        if backbone == "resnet50":
            base = resnet50(weights=None)
            base.conv1 = nn.Conv2d(in_channels, 64, 7, stride=2, padding=3, bias=False)
            nn.init.kaiming_normal_(base.conv1.weight, mode="fan_out", nonlinearity="relu")
            self.features = nn.Sequential(*list(base.children())[:-2])
            feature_channels = 2048
        else:
            base = convnext_tiny(weights=None)
            base.features[0][0] = nn.Conv2d(in_channels, 96, 4, stride=4)
            nn.init.trunc_normal_(base.features[0][0].weight, std=0.02)
            nn.init.zeros_(base.features[0][0].bias)
            self.features = base.features
            feature_channels = 768
        self.to_embed = nn.Conv2d(feature_channels, embed_dim, 1)
        self.norm = nn.LayerNorm(embed_dim)
        self.measurand_embeddings = nn.Parameter(torch.empty(1, num_targets, embed_dim))
        self.scalar_head = nn.Sequential(
            nn.Linear(embed_dim * 3, embed_dim), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(embed_dim, 3 if interval_mode == "asymmetric" else 2),
        )
        if segmentation_head:
            self.segmentation_head = nn.Sequential(
                nn.Conv2d(embed_dim, embed_dim // 2, 3, padding=1),
                nn.GroupNorm(8, embed_dim // 2), nn.SiLU(),
                ResidualConvBlock(embed_dim // 2),
                nn.Conv2d(embed_dim // 2, 4, 1),
            )
        # Match the manuscript's head initialization; retain torchvision's
        # backbone initialization, normalization and stochastic-depth defaults.
        nn.init.trunc_normal_(self.measurand_embeddings, std=0.02)
        heads = [self.to_embed, self.scalar_head]
        if segmentation_head:
            heads.append(self.segmentation_head)
        for head in heads:
            for module in head.modules():
                if isinstance(module, nn.Conv2d):
                    nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                elif isinstance(module, nn.Linear):
                    nn.init.trunc_normal_(module.weight, std=0.02)
                if isinstance(module, (nn.Conv2d, nn.Linear)) and module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        if inputs.shape[-2:] != (self.image_size, self.image_size):
            raise ValueError("Input spatial shape does not match configured image_size.")
        features = self.to_embed(self.features(inputs))
        spatial = self.norm(features.flatten(2).transpose(1, 2))
        target_ids = self.measurand_embeddings.expand(inputs.shape[0], -1, -1)
        mean = spatial.mean(1, keepdim=True).expand(-1, self.num_targets, -1)
        maximum = spatial.max(1, keepdim=True).values.expand(-1, self.num_targets, -1)
        raw = self.scalar_head(torch.cat([target_ids, mean, maximum], dim=-1))
        lower = F.softplus(raw[..., 1]) + self.min_delta
        upper = lower if self.interval_mode == "symmetric" else F.softplus(raw[..., 2]) + self.min_delta
        outputs = {"interval": torch.stack([raw[..., 0], lower, upper], dim=-1)}
        if self.has_segmentation_head:
            dense = spatial.transpose(1, 2).reshape_as(features)
            dense = F.interpolate(dense, size=(self.image_size // 16,) * 2,
                                  mode="bilinear", align_corners=False)
            logits = self.segmentation_head(dense)
            logits = F.interpolate(logits, size=inputs.shape[-2:], mode="bilinear", align_corners=False)
            outputs.update(defect_logits=logits[:, 0:1], skeleton_logits=logits[:, 1:2],
                           boundary_logits=logits[:, 2:3], width_mm=F.softplus(logits[:, 3:4]))
        return outputs
