from typing import Any, ClassVar

from ..base import VisualFalModel
from .base import (
    FLUX1Dev,
    FLUX2Klein9B,
    GPTImage2,
    GPTImage15,
    NanoBanana,
    NanoBanana2,
    NanoBananaPro,
    Seedream5Lite,
    Seedream45,
    ZImageTurbo,
)

__all__ = [
    "FLUX1DevImageRefinementModel",
    "FLUX2Klein9BImageRefinementModel",
    "GPTImage15ImageRefinementModel",
    "GPTImage2ImageRefinementModel",
    "ImageRefinementModel",
    "NanoBanana2ImageRefinementModel",
    "NanoBananaImageRefinementModel",
    "NanoBananaProImageRefinementModel",
    "Seedream45ImageRefinementModel",
    "Seedream5LiteImageRefinementModel",
    "ZImageTurboImageRefinementModel",
]


class ImageRefinementModel(VisualFalModel):
    """Base class for image refinement models that edit images using prompts."""

    # Whether the model supports system prompts (edit models do, img2img models don't)
    supports_system_prompt: ClassVar[bool] = True

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        prompt = params.pop("prompt", "")

        # Only apply system_prompt for models that support it (edit models)
        if cls.supports_system_prompt:
            system_prompt = kwargs.get("system_prompt", "")
            if system_prompt and prompt and not prompt.startswith(system_prompt):
                prompt = f"{system_prompt}\n\nFollow the user's prompt: {prompt}"
            elif system_prompt and not prompt:
                prompt = system_prompt

        params["prompt"] = prompt
        return params


class NanoBananaImageRefinementModel(ImageRefinementModel, NanoBanana):
    """Image refinement using the Nano Banana model."""

    endpoint = "fal-ai/nano-banana/edit"


class NanoBananaProImageRefinementModel(ImageRefinementModel, NanoBananaPro):
    """Image refinement using the Nano Banana Pro model."""

    endpoint = "fal-ai/nano-banana-pro/edit"


class NanoBanana2ImageRefinementModel(ImageRefinementModel, NanoBanana2):
    """Image refinement using the Nano Banana 2 model."""

    endpoint = "fal-ai/nano-banana-2/edit"


class ZImageTurboImageRefinementModel(ImageRefinementModel, ZImageTurbo):
    """Image refinement using the Z-Image Turbo model (img2img, no system prompt)."""

    endpoint = "fal-ai/z-image/turbo/image-to-image"
    supports_system_prompt = False  # img2img model, not an edit model


class GPTImage15ImageRefinementModel(ImageRefinementModel, GPTImage15):
    """Image refinement using the GPT Image 1.5 model."""

    endpoint = "fal-ai/gpt-image-1.5/edit"


class GPTImage2ImageRefinementModel(ImageRefinementModel, GPTImage2):
    """Image refinement using the GPT Image 2 model."""

    endpoint = "openai/gpt-image-2/edit"


class Seedream45ImageRefinementModel(ImageRefinementModel, Seedream45):
    """Image refinement using the Seedream 4.5 model."""

    endpoint = "fal-ai/bytedance/seedream/v4.5/edit"


class Seedream5LiteImageRefinementModel(ImageRefinementModel, Seedream5Lite):
    """Image refinement using the Seedream 5 Lite model."""

    endpoint = "fal-ai/bytedance/seedream/v5/lite/edit"


class FLUX1DevImageRefinementModel(ImageRefinementModel, FLUX1Dev):
    """Image refinement using the FLUX.1 [dev] model (img2img, no system prompt)."""

    endpoint = "fal-ai/flux/dev/image-to-image"
    supports_system_prompt = False  # img2img model, not an edit model

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Return parameters with strength for img2img blending."""
        params = super().parameters(**kwargs)
        params["strength"] = kwargs.get("strength", 0.5)
        return params


class FLUX2Klein9BImageRefinementModel(ImageRefinementModel, FLUX2Klein9B):
    """Image refinement using the FLUX.2 Klein 9B edit model."""

    endpoint = "fal-ai/flux-2/klein/9b/edit"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Return parameters with strength for edit blending."""
        params = super().parameters(**kwargs)
        params["strength"] = kwargs.get("strength", 0.5)
        return params
