from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel
from .base import (
    LTX2DistilledVideoModel,
    LTX2VideoModel,
    LTX23DistilledVideoModel,
    LTX23VideoModel,
    WanFun22A14BVideoModel,
    WanVACE14BVideoModel,
)

__all__ = [
    "DepthVideoModel",
    "LTX2DistilledDepthVideoModel",
    "LTX2DepthVideoModel",
    "WanVACE14BDepthVideoModel",
    "WanFun22A14BDepthVideoModel",
    "LTX23RefV2VDepthVideoModel",
    "LTX23DistilledRefV2VDepthVideoModel",
]


class DepthVideoModel(VisualFalModel):
    """Base model for depth-conditioned video generation."""

    video_url_parameter: ClassVar[str | None] = "video_url"
    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters for depth-conditioned video generation."""
        params: dict[str, Any] = super().parameters(**kwargs)
        prompt = kwargs.get("prompt", "")
        if prompt:
            params["prompt"] = prompt
        enable = kwargs.get("enable_prompt_expansion", True)
        params["enable_prompt_expansion"] = enable
        params["expand_prompt"] = enable

        video_url = kwargs.get("video_url")
        if video_url:
            params["video_url"] = video_url

        num_frames = kwargs.get("num_frames")
        if num_frames:
            params["num_frames"] = num_frames

        image_url = kwargs.get("image_url")
        if image_url:
            params["image_url"] = image_url

        resolution = kwargs.get("resolution")
        if resolution:
            params["resolution"] = resolution

        return params


class LTX2DistilledDepthVideoModel(DepthVideoModel, LTX2DistilledVideoModel):
    """LTX-2 19B Distilled depth-conditioned video model."""

    endpoint = "fal-ai/ltx-2-19b/distilled/video-to-video"
    description = "Faster depth video — fewer steps, good for simple camera moves"
    static_parameters: ClassVar[dict[str, Any]] = {"ic_lora": "depth"}


class LTX2DepthVideoModel(DepthVideoModel, LTX2VideoModel):
    """LTX-2 19B depth-conditioned video model using IC-LoRA."""

    endpoint = "fal-ai/ltx-2-19b/video-to-video"
    description = "Depth-conditioned video generation via IC-LoRA"
    static_parameters: ClassVar[dict[str, Any]] = {"ic_lora": "depth"}


class WanVACE14BDepthVideoModel(DepthVideoModel, WanVACE14BVideoModel):
    """Wan-VACE 14B depth-conditioned video model."""

    endpoint = "fal-ai/wan-vace-14b/depth"
    description = "Depth-conditioned video generation"


class WanFun22A14BDepthVideoModel(DepthVideoModel, WanFun22A14BVideoModel):
    """Wan-Fun 2.2 A14B depth-conditioned video model."""

    endpoint = "fal-ai/wan-22-vace-fun-a14b/depth"
    description = "Depth-conditioned video generation"


class LTX23RefV2VDepthVideoModel(DepthVideoModel, LTX23VideoModel):
    """LTX 2.3 22B reference video-to-video with union IC-LoRA."""

    display_name = "LTX 2.3 22B Ref V2V"
    endpoint = "fal-ai/ltx-2.3-22b/reference-video-to-video"
    description = "Reference video-to-video with union IC-LoRA"
    static_parameters: ClassVar[dict[str, Any]] = {"ic_lora": "union"}


class LTX23DistilledRefV2VDepthVideoModel(DepthVideoModel, LTX23DistilledVideoModel):
    """LTX 2.3 22B Distilled reference video-to-video with union IC-LoRA."""

    display_name = "LTX 2.3 22B Distilled Ref V2V"
    endpoint = "fal-ai/ltx-2.3-22b/distilled/reference-video-to-video"
    description = "Faster reference video-to-video with union IC-LoRA"
    static_parameters: ClassVar[dict[str, Any]] = {"ic_lora": "union"}
