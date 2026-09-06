from __future__ import annotations

from typing import Any

from ..base import VisualFalModel


class TilingTextureModel(VisualFalModel):
    """Base model for seamlessly tiling texture generation."""

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters, forwarding output format and tiling mode."""
        params = super().parameters(**kwargs)
        for key in ("output_format", "tiling_mode"):
            if key in kwargs:
                params[key] = kwargs[key]
        return params


class ZImageTurboTilingTextureModel(TilingTextureModel):
    """Z-Image Turbo tiling texture model."""

    endpoint = "fal-ai/z-image/turbo/tiling"
    display_name = "Z-Image Turbo Tiling"
    prompt_expansion_parameter = "enable_prompt_expansion"
