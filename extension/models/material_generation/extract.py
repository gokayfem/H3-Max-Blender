from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel


class MaterialExtractionModel(VisualFalModel):
    """Base model for extracting a tileable PBR material from a photo."""

    size_parameter: ClassVar[str | None] = "image_size"
    image_url_parameter: ClassVar[str | None] = "image_url"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters, forwarding extraction-specific options."""
        params = super().parameters(**kwargs)
        for key in ("output_format", "tiling_mode"):
            if key in kwargs:
                params[key] = kwargs[key]
        if "strength" in kwargs:
            params["strength"] = kwargs["strength"]
        if "upscale_factor" in kwargs:
            try:
                params["upscale_factor"] = int(kwargs["upscale_factor"])
            except ValueError:
                print(f"fal.ai: Invalid upscale factor: {kwargs['upscale_factor']}")
        return params


class PatinaMaterialExtractionModel(MaterialExtractionModel):
    """Patina material extraction model."""

    endpoint = "fal-ai/patina/material/extract"
    display_name = "Patina Material Extract"
    prompt_expansion_parameter = "enable_prompt_expansion"
