from ..base import VisualFalModel

__all__ = [
    "ImageUpscalingModel",
    "SeedVR29BImageUpscalingModel",
    "AuraSRImageUpscalingModel",
    "ClarityImageUpscalingModel",
]


class ImageUpscalingModel(VisualFalModel):
    """Base model for image upscaling."""

    pass


class SeedVR29BImageUpscalingModel(ImageUpscalingModel):
    """SeedVR2 9B image upscaling model."""

    endpoint = "fal-ai/seedvr/upscale/image"
    display_name = "SeedVR2 9B"
    image_url_parameter = "image_url"


class AuraSRImageUpscalingModel(ImageUpscalingModel):
    """AuraSR image upscaling model."""

    endpoint = "fal-ai/aura-sr"
    display_name = "AuraSR"
    image_url_parameter = "image_url"


class ClarityImageUpscalingModel(ImageUpscalingModel):
    """Clarity Upscaler image upscaling model."""

    endpoint = "fal-ai/clarity-upscaler"
    display_name = "Clarity Upscaler"
    image_url_parameter = "image_url"
