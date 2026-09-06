from __future__ import annotations

from typing import Any, ClassVar

from .base import (
    KlingV3ProVideoModel,
    KlingV3StandardVideoModel,
    LTX2DistilledVideoModel,
    LTX2VideoModel,
    LTX23DistilledVideoModel,
    LTX23VideoModel,
    Seedance20FastVideoModel,
    Seedance20VideoModel,
    Veo31FastVideoModel,
    Veo31VideoModel,
    VideoFalModel,
    Wan22TurboVideoModel,
    Wan22VideoModel,
    Wan27VideoModel,
)

__all__ = [
    "ImageToVideoModel",
    "Wan22ImageToVideoModel",
    "Wan22TurboImageToVideoModel",
    "LTX2ImageToVideoModel",
    "LTX2DistilledImageToVideoModel",
    "Seedance20ImageToVideoModel",
    "Seedance20FastImageToVideoModel",
    "KlingV3StandardImageToVideoModel",
    "KlingV3ProImageToVideoModel",
    "Veo31ImageToVideoModel",
    "Veo31FastImageToVideoModel",
    "LTX23ImageToVideoModel",
    "LTX23DistilledImageToVideoModel",
    "Wan27ImageToVideoModel",
]


class ImageToVideoModel(VideoFalModel):
    """Base model for image-to-video generation."""

    image_url_parameter: ClassVar[str | None] = "image_url"
    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters for image-to-video generation."""
        params: dict[str, Any] = super().parameters(**kwargs)
        enable = kwargs.get("enable_prompt_expansion", True)
        params["enable_prompt_expansion"] = enable
        params["expand_prompt"] = enable
        return params


class Wan22ImageToVideoModel(ImageToVideoModel, Wan22VideoModel):
    """Wan 2.2 image-to-video model."""

    endpoint = "fal-ai/wan/v2.2-a14b/image-to-video"


class Wan22TurboImageToVideoModel(ImageToVideoModel, Wan22TurboVideoModel):
    """Wan 2.2 turbo image-to-video model."""

    endpoint = "fal-ai/wan/v2.2-a14b/image-to-video/turbo"


class LTX2ImageToVideoModel(ImageToVideoModel, LTX2VideoModel):
    """LTX-2 19B image-to-video model."""

    endpoint = "fal-ai/ltx-2-19b/image-to-video"


class LTX2DistilledImageToVideoModel(ImageToVideoModel, LTX2DistilledVideoModel):
    """LTX-2 19B distilled image-to-video model."""

    endpoint = "fal-ai/ltx-2-19b/distilled/image-to-video"


class LTX23ImageToVideoModel(ImageToVideoModel, LTX23VideoModel):
    """LTX 2.3 22B image-to-video model."""

    endpoint = "fal-ai/ltx-2.3-22b/image-to-video"


class LTX23DistilledImageToVideoModel(ImageToVideoModel, LTX23DistilledVideoModel):
    """LTX 2.3 22B Distilled image-to-video model."""

    endpoint = "fal-ai/ltx-2.3-22b/distilled/image-to-video"


class Seedance20ImageToVideoModel(ImageToVideoModel, Seedance20VideoModel):
    """Seedance 2.0 image-to-video model."""

    endpoint = "bytedance/seedance-2.0/image-to-video"


class Seedance20FastImageToVideoModel(ImageToVideoModel, Seedance20FastVideoModel):
    """Seedance 2.0 Fast image-to-video model."""

    endpoint = "bytedance/seedance-2.0/fast/image-to-video"


class KlingV3StandardImageToVideoModel(ImageToVideoModel, KlingV3StandardVideoModel):
    """Kling v3 Standard image-to-video model."""

    endpoint = "fal-ai/kling-video/v3/standard/image-to-video"
    # Kling i2v: size is inferred from the input image, don't emit aspect/resolution.
    emit_aspect_ratio = False
    emit_resolution = False


class KlingV3ProImageToVideoModel(ImageToVideoModel, KlingV3ProVideoModel):
    """Kling v3 Pro image-to-video model."""

    endpoint = "fal-ai/kling-video/v3/pro/image-to-video"
    emit_aspect_ratio = False
    emit_resolution = False


class Veo31ImageToVideoModel(ImageToVideoModel, Veo31VideoModel):
    """Veo 3.1 image-to-video model."""

    endpoint = "fal-ai/veo3.1/image-to-video"


class Veo31FastImageToVideoModel(ImageToVideoModel, Veo31FastVideoModel):
    """Veo 3.1 Fast image-to-video model."""

    endpoint = "fal-ai/veo3.1/fast/image-to-video"


class Wan27ImageToVideoModel(ImageToVideoModel, Wan27VideoModel):
    """Wan 2.7 image-to-video model."""

    endpoint = "fal-ai/wan/v2.7/image-to-video"
    # Wan 2.7 i2v infers aspect_ratio from the image but still accepts resolution.
    emit_aspect_ratio = False
