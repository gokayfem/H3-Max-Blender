from typing import Any

from ..base import VisualFalModel
from .base import (
    GPTImage2,
    GPTImage15,
    NanoBanana,
    NanoBanana2,
    NanoBananaPro,
    Seedream5Lite,
    Seedream45,
)

__all__ = [
    "GPTImage15Model",
    "GPTImage2Model",
    "NanoBanana2SketchGuidedImageGenerationModel",
    "NanoBananaProSketchGuidedImageGenerationModel",
    "NanoBananaSketchGuidedImageGenerationModel",
    "Seedream45Model",
    "Seedream5LiteModel",
    "SketchGuidedImageGenerationModel",
]


class SketchGuidedImageGenerationModel(VisualFalModel):
    """Base class for sketch-guided image generation models that transform sketches into images."""

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        prompt = params.pop("prompt", "")
        # system_prompt comes from kwargs, not params (parent doesn't pass it through)
        system_prompt = kwargs.get("system_prompt", "")
        if system_prompt and prompt:
            prompt = f"{system_prompt}\n\nFollow the user's prompt: {prompt}"
        elif system_prompt and not prompt:
            prompt = system_prompt
        params["prompt"] = prompt
        return params


class NanoBananaSketchGuidedImageGenerationModel(
    SketchGuidedImageGenerationModel, NanoBanana
):
    """Sketch-guided image generation using the Nano Banana model."""

    endpoint = "fal-ai/nano-banana/edit"


class NanoBananaProSketchGuidedImageGenerationModel(
    SketchGuidedImageGenerationModel, NanoBananaPro
):
    """Sketch-guided image generation using the Nano Banana Pro model."""

    endpoint = "fal-ai/nano-banana-pro/edit"


class NanoBanana2SketchGuidedImageGenerationModel(
    SketchGuidedImageGenerationModel, NanoBanana2
):
    """Sketch-guided image generation using the Nano Banana 2 model."""

    endpoint = "fal-ai/nano-banana-2/edit"


class GPTImage15Model(SketchGuidedImageGenerationModel, GPTImage15):
    """GPT Image 1.5 model."""

    endpoint = "fal-ai/gpt-image-1.5/edit"


class Seedream45Model(SketchGuidedImageGenerationModel, Seedream45):
    """Seedream 4.5 model."""

    endpoint = "fal-ai/bytedance/seedream/v4.5/edit"


class Seedream5LiteModel(SketchGuidedImageGenerationModel, Seedream5Lite):
    """Seedream 5 Lite model."""

    endpoint = "fal-ai/bytedance/seedream/v5/lite/edit"


class GPTImage2Model(SketchGuidedImageGenerationModel, GPTImage2):
    """GPT Image 2 model."""

    endpoint = "openai/gpt-image-2/edit"
