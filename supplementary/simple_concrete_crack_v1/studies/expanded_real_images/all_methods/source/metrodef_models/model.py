from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class ViTScalarRegressor(nn.Module):
    def __init__(
        self,
        image_size: int,
        patch_size: int,
        in_channels: int,
        num_targets: int,
        embed_dim: int = 384,
        depth: int = 6,
        num_heads: int = 6,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
        min_delta: float = 1.0e-4,
    ) -> None:
        super().__init__()
        if image_size % patch_size != 0:
            raise ValueError("image_size must be divisible by patch_size.")
        self.image_size = image_size
        self.patch_size = patch_size
        self.num_targets = num_targets
        self.min_delta = min_delta

        patch_count = (image_size // patch_size) ** 2
        self.patch_embed = nn.Conv2d(in_channels, embed_dim, kernel_size=patch_size, stride=patch_size)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, patch_count + 1, embed_dim))
        self.pos_drop = nn.Dropout(dropout)

        layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=int(embed_dim * mlp_ratio),
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=depth)
        self.norm = nn.LayerNorm(embed_dim)
        self.head = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, num_targets * 3),
        )
        self._init_weights()

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        patches = self.patch_embed(inputs).flatten(2).transpose(1, 2)
        cls = self.cls_token.expand(inputs.shape[0], -1, -1)
        tokens = torch.cat([cls, patches], dim=1)
        tokens = self.pos_drop(tokens + self.pos_embed)
        encoded = self.encoder(tokens)
        pooled = self.norm(encoded[:, 0])
        raw = self.head(pooled).reshape(inputs.shape[0], self.num_targets, 3)

        mu = raw[..., 0]
        lower_delta = F.softplus(raw[..., 1]) + self.min_delta
        upper_delta = F.softplus(raw[..., 2]) + self.min_delta
        return torch.stack([mu, lower_delta, upper_delta], dim=-1)

    def _init_weights(self) -> None:
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.trunc_normal_(module.weight, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)


class ViTScalarVisibilityRegressor(nn.Module):
    def __init__(
        self,
        image_size: int,
        patch_size: int,
        in_channels: int,
        num_targets: int,
        embed_dim: int = 384,
        depth: int = 6,
        num_heads: int = 6,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
        min_delta: float = 1.0e-4,
    ) -> None:
        super().__init__()
        if image_size % patch_size != 0:
            raise ValueError("image_size must be divisible by patch_size.")
        self.image_size = image_size
        self.patch_size = patch_size
        self.num_targets = num_targets
        self.min_delta = min_delta

        patch_count = (image_size // patch_size) ** 2
        self.patch_embed = nn.Conv2d(in_channels, embed_dim, kernel_size=patch_size, stride=patch_size)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, patch_count + 1, embed_dim))
        self.pos_drop = nn.Dropout(dropout)

        layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=int(embed_dim * mlp_ratio),
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=depth)
        self.norm = nn.LayerNorm(embed_dim)
        self.interval_head = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, num_targets * 3),
        )
        self.visibility_head = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim // 2, 1),
        )
        self._init_weights()

    def forward(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        patches = self.patch_embed(inputs).flatten(2).transpose(1, 2)
        cls = self.cls_token.expand(inputs.shape[0], -1, -1)
        tokens = torch.cat([cls, patches], dim=1)
        tokens = self.pos_drop(tokens + self.pos_embed)
        encoded = self.encoder(tokens)
        pooled = self.norm(encoded[:, 0])
        raw = self.interval_head(pooled).reshape(inputs.shape[0], self.num_targets, 3)

        mu = raw[..., 0]
        lower_delta = F.softplus(raw[..., 1]) + self.min_delta
        upper_delta = F.softplus(raw[..., 2]) + self.min_delta
        return {
            "interval": torch.stack([mu, lower_delta, upper_delta], dim=-1),
            "visibility_logit": self.visibility_head(pooled).squeeze(-1),
        }

    def _init_weights(self) -> None:
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.trunc_normal_(module.weight, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)


class ResidualConvBlock(nn.Module):
    def __init__(self, channels: int, groups: int = 8) -> None:
        super().__init__()
        groups = min(groups, channels)
        self.net = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.GroupNorm(groups, channels),
            nn.SiLU(),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.GroupNorm(groups, channels),
        )
        self.activation = nn.SiLU()

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.activation(inputs + self.net(inputs))


class MetricTransformerMultiTask(nn.Module):
    def __init__(
        self,
        image_size: int,
        in_channels: int,
        num_targets: int,
        token_stride: int = 32,
        embed_dim: int = 256,
        depth: int = 4,
        num_heads: int = 8,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if image_size % token_stride != 0:
            raise ValueError("image_size must be divisible by token_stride.")
        if token_stride < 4 or token_stride & (token_stride - 1):
            raise ValueError("token_stride must be a power of two and at least 4.")
        self.image_size = int(image_size)
        self.token_stride = int(token_stride)
        self.num_targets = int(num_targets)
        self.grid_size = self.image_size // self.token_stride

        layers = []
        current_channels = in_channels
        stem_channels = max(32, embed_dim // 4)
        stride = 1
        while stride < token_stride:
            next_channels = min(embed_dim, stem_channels * stride)
            layers.extend(
                [
                    nn.Conv2d(current_channels, next_channels, kernel_size=3, stride=2, padding=1),
                    nn.GroupNorm(min(8, next_channels), next_channels),
                    nn.SiLU(),
                    ResidualConvBlock(next_channels),
                ]
            )
            current_channels = next_channels
            stride *= 2
        self.stem = nn.Sequential(*layers)
        self.to_embed = nn.Conv2d(current_channels, embed_dim, kernel_size=1)

        patch_count = self.grid_size * self.grid_size
        self.measurand_tokens = nn.Parameter(torch.zeros(1, num_targets, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, patch_count + num_targets, embed_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=int(embed_dim * mlp_ratio),
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=depth)
        self.norm = nn.LayerNorm(embed_dim)
        self.scalar_head = nn.Sequential(
            nn.Linear(embed_dim * 3, embed_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, 2),
        )
        self.visibility_head = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim // 2, 1),
        )
        self.dense_head = nn.Sequential(
            nn.Conv2d(embed_dim, embed_dim // 2, kernel_size=3, padding=1),
            nn.GroupNorm(min(8, embed_dim // 2), embed_dim // 2),
            nn.SiLU(),
            ResidualConvBlock(embed_dim // 2),
            nn.Conv2d(embed_dim // 2, 3, kernel_size=1),
        )
        self._init_weights()

    def forward(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self.to_embed(self.stem(inputs))
        batch, channels, height, width = features.shape
        spatial_tokens = features.flatten(2).transpose(1, 2)
        measurand_tokens = self.measurand_tokens.expand(batch, -1, -1)
        tokens = torch.cat([measurand_tokens, spatial_tokens], dim=1) + self.pos_embed
        encoded = self.norm(self.encoder(tokens))
        measurand = encoded[:, : self.num_targets]
        spatial = encoded[:, self.num_targets :]

        spatial_mean = spatial.mean(dim=1, keepdim=True).expand(-1, self.num_targets, -1)
        spatial_max = spatial.max(dim=1, keepdim=True).values.expand(-1, self.num_targets, -1)
        scalar_raw = self.scalar_head(torch.cat([measurand, spatial_mean, spatial_max], dim=-1))

        visibility_features = torch.cat([spatial.mean(dim=1), spatial.max(dim=1).values], dim=-1)
        visibility_logit = self.visibility_head(visibility_features).squeeze(-1)

        dense_features = spatial.transpose(1, 2).reshape(batch, channels, height, width)
        dense = self.dense_head(dense_features)
        dense = F.interpolate(dense, size=(inputs.shape[-2], inputs.shape[-1]), mode="bilinear", align_corners=False)
        return {
            "scalar_mean": scalar_raw[..., 0],
            "scalar_log_var": scalar_raw[..., 1].clamp(min=-8.0, max=6.0),
            "visibility_logit": visibility_logit,
            "defect_logits": dense[:, 0:1],
            "skeleton_logits": dense[:, 1:2],
            "width_mm": F.softplus(dense[:, 2:3]),
        }

    def _init_weights(self) -> None:
        nn.init.trunc_normal_(self.measurand_tokens, std=0.02)
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.trunc_normal_(module.weight, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)


class ScalarSegmentationTransformer(nn.Module):
    def __init__(
        self,
        image_size: int,
        in_channels: int,
        num_targets: int,
        token_stride: int = 32,
        embed_dim: int = 384,
        depth: int = 6,
        num_heads: int = 8,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
        min_delta: float = 1.0e-4,
        interval_mode: str = "asymmetric",
        segmentation_head: bool = True,
    ) -> None:
        super().__init__()
        if image_size % token_stride != 0:
            raise ValueError("image_size must be divisible by token_stride.")
        if token_stride < 4 or token_stride & (token_stride - 1):
            raise ValueError("token_stride must be a power of two and at least 4.")
        if interval_mode not in ("asymmetric", "symmetric"):
            raise ValueError("interval_mode must be 'asymmetric' or 'symmetric'.")
        self.image_size = int(image_size)
        self.token_stride = int(token_stride)
        self.num_targets = int(num_targets)
        self.grid_size = self.image_size // self.token_stride
        self.min_delta = float(min_delta)
        self.interval_mode = interval_mode
        self.has_segmentation_head = bool(segmentation_head)

        layers = []
        current_channels = in_channels
        stem_channels = max(32, embed_dim // 4)
        stride = 1
        while stride < token_stride:
            next_channels = min(embed_dim, stem_channels * stride)
            layers.extend(
                [
                    nn.Conv2d(current_channels, next_channels, kernel_size=3, stride=2, padding=1),
                    nn.GroupNorm(min(8, next_channels), next_channels),
                    nn.SiLU(),
                    ResidualConvBlock(next_channels),
                ]
            )
            current_channels = next_channels
            stride *= 2
        self.stem = nn.Sequential(*layers)
        self.to_embed = nn.Conv2d(current_channels, embed_dim, kernel_size=1)

        patch_count = self.grid_size * self.grid_size
        self.measurand_tokens = nn.Parameter(torch.zeros(1, num_targets, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, patch_count + num_targets, embed_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=int(embed_dim * mlp_ratio),
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=depth)
        self.norm = nn.LayerNorm(embed_dim)
        self.scalar_head = nn.Sequential(
            nn.Linear(embed_dim * 3, embed_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, 3 if self.interval_mode == "asymmetric" else 2),
        )
        if self.has_segmentation_head:
            self.segmentation_head = nn.Sequential(
                nn.Conv2d(embed_dim, embed_dim // 2, kernel_size=3, padding=1),
                nn.GroupNorm(min(8, embed_dim // 2), embed_dim // 2),
                nn.SiLU(),
                ResidualConvBlock(embed_dim // 2),
                nn.Conv2d(embed_dim // 2, 4, kernel_size=1),
            )
        self._init_weights()

    def forward(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self.to_embed(self.stem(inputs))
        batch, channels, height, width = features.shape
        spatial_tokens = features.flatten(2).transpose(1, 2)
        measurand_tokens = self.measurand_tokens.expand(batch, -1, -1)
        tokens = torch.cat([measurand_tokens, spatial_tokens], dim=1) + self.pos_embed
        encoded = self.norm(self.encoder(tokens))
        measurand = encoded[:, : self.num_targets]
        spatial = encoded[:, self.num_targets :]

        spatial_mean = spatial.mean(dim=1, keepdim=True).expand(-1, self.num_targets, -1)
        spatial_max = spatial.max(dim=1, keepdim=True).values.expand(-1, self.num_targets, -1)
        raw = self.scalar_head(torch.cat([measurand, spatial_mean, spatial_max], dim=-1))
        mu = raw[..., 0]
        lower_delta = F.softplus(raw[..., 1]) + self.min_delta
        if self.interval_mode == "symmetric":
            upper_delta = lower_delta
        else:
            upper_delta = F.softplus(raw[..., 2]) + self.min_delta
        interval = torch.stack([mu, lower_delta, upper_delta], dim=-1)

        outputs = {"interval": interval}
        if self.has_segmentation_head:
            dense_features = spatial.transpose(1, 2).reshape(batch, channels, height, width)
            logits = self.segmentation_head(dense_features)
            logits = F.interpolate(logits, size=(inputs.shape[-2], inputs.shape[-1]), mode="bilinear", align_corners=False)
            outputs.update(
                {
                    "defect_logits": logits[:, 0:1],
                    "skeleton_logits": logits[:, 1:2],
                    "boundary_logits": logits[:, 2:3],
                    "width_mm": F.softplus(logits[:, 3:4]),
                }
            )
        return outputs

    def _init_weights(self) -> None:
        nn.init.trunc_normal_(self.measurand_tokens, std=0.02)
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.trunc_normal_(module.weight, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
