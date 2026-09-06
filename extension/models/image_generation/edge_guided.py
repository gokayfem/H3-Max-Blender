from typing import Any

from ..base import VisualFalModel
from .base import FLUX1Dev, ZImageTurbo

__all__ = [
    "EdgeGuidedImageGenerationModel",
    "ZImageTurboEdgeGuidedImageGenerationModel",
    "FLUX1DevEdgeGuidedImageGenerationModel",
]


class EdgeGuidedImageGenerationModel(VisualFalModel):
    """Base class for edge-guided image generation models."""

    pass


class ZImageTurboEdgeGuidedImageGenerationModel(
    EdgeGuidedImageGenerationModel, ZImageTurbo
):
    """Edge-guided image generation using the Z-Image Turbo model."""

    endpoint = "fal-ai/z-image/turbo/controlnet"


class FLUX1DevEdgeGuidedImageGenerationModel(EdgeGuidedImageGenerationModel, FLUX1Dev):
    """Edge-guided image generation using the FLUX.1 [dev] model with ControlNet unions."""

    endpoint = "fal-ai/flux-general"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["controlnet_unions"] = [
            {
                "path": "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro",
                "controls": [
                    {
                        "control_image_url": params.pop("image_url", None),
                        "control_mode": "canny",
                    }
                ],
            },
        ]
        return params
